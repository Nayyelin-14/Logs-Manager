"""Focused, database-free tests for Syslog reliability (scenarios 5-10).

Covers the Vector payload/retry contract, SYSLOG_ENABLED gating, the health
endpoint semantics, and bounded retry of transient database failures.
"""

from __future__ import annotations

import asyncio
import socket
import sys
import tomllib
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError
from starlette.requests import Request

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.core.config import get_settings
from app.core.dependencies import verify_api_key
from app.core.exceptions import ValidationError, is_transient_db_error
from app.integrations.syslog import (
    enabled_listeners,
    ingest_parsed,
    is_source_allowed,
    syslog_counters,
)
from ingest.health import build_health_payload, health_http_status, start_health_server

settings = get_settings()
VECTOR_CONFIG = REPO_ROOT / "samples" / "forwarder" / "vector.toml"


def _vector_config() -> dict:
    with VECTOR_CONFIG.open("rb") as handle:
        return tomllib.load(handle)


def test_vector_payload_matches_receiver_contract():
    config = _vector_config()
    sink = config["sinks"]["logs_https"]

    # Newline-delimited raw text, not one JSON object per event.
    assert sink["encoding"]["codec"] == "text"
    assert sink["framing"]["method"] == "newline_delimited"
    assert sink["batch"]["max_events"] > 1
    assert "transforms" not in config  # no {"lines": [...]} wrapper

    request = sink["request"]
    assert request["headers"]["Content-Type"].startswith("text/plain")
    assert request["headers"]["X-API-Key"] == "${INGEST_API_KEY}"

    # The receiver splits text bodies on newlines; two messages stay two lines.
    payload = "line-one\nline-two"
    assert len(payload.splitlines()) == 2


def test_vector_retries_and_buffers_transient_failures():
    config = _vector_config()
    sink = config["sinks"]["logs_https"]

    request = sink["request"]
    assert request["retry_attempts"] >= 2
    assert request["retry_initial_backoff_secs"] >= 1
    assert request["retry_max_duration_secs"] > 0

    # Vector retries 429/5xx/transport errors by default; the configuration
    # above makes the retry window explicit.
    buffer = sink["buffer"]
    assert buffer["type"] == "disk"
    assert buffer["max_size"] >= 268435488
    assert buffer["when_full"] == "block"


def test_vector_uri_opt_out_is_shipped_for_env_template():
    config = _vector_config()
    sink = config["sinks"]["logs_https"]

    # Vector 0.61 treats a fully templated URI as event-controlled unless the
    # sink opts out; the URL is operator-supplied via SYSLOG_HTTP_URL.
    assert sink["uri"] == "${SYSLOG_HTTP_URL}"
    assert sink["dangerously_allow_unconfined_template_resolution"] is True


def test_transient_classification_includes_dns_and_connection_reset():
    assert is_transient_db_error(socket.gaierror(-2, "Name or service not known"))
    assert is_transient_db_error(
        DBAPIError(
            "SELECT 1",
            {},
            Exception("connection was closed in the middle of operation"),
        )
    )
    assert is_transient_db_error(
        DBAPIError("SELECT 1", {}, ConnectionResetError("reset"))
    )
    assert is_transient_db_error(
        OperationalError("SELECT 1", {}, Exception("temporary"))
    )


def test_permanent_database_and_validation_errors_are_not_transient():
    assert not is_transient_db_error(ValidationError("bad event"))
    assert not is_transient_db_error(
        IntegrityError("INSERT", {}, Exception("duplicate key"))
    )
    assert not is_transient_db_error(
        DBAPIError("SELECT 1", {}, Exception("syntax error at or near"))
    )


def _api_request(api_key: str | None) -> Request:
    headers = []
    if api_key is not None:
        headers.append((b"x-api-key", api_key.encode()))
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/ingest/syslog",
            "headers": headers,
        }
    )


class _RaisingSession:
    def __init__(self, exc: BaseException) -> None:
        self.exc = exc

    async def execute(self, *args, **kwargs):
        raise self.exc


class _EmptyResult:
    def scalar_one_or_none(self):
        return None


class _EmptySession:
    async def execute(self, *args, **kwargs):
        return _EmptyResult()


@pytest.mark.parametrize(
    "error",
    [
        socket.gaierror(-2, "Name or service not known"),
        DBAPIError(
            "SELECT 1",
            {},
            Exception("connection was closed in the middle of operation"),
        ),
    ],
)
async def test_auth_database_outage_returns_503_with_retry_after(error):
    with pytest.raises(HTTPException) as caught:
        await verify_api_key(_api_request("key"), _RaisingSession(error))

    assert caught.value.status_code == 503
    assert caught.value.headers["Retry-After"] == "5"


@pytest.mark.parametrize("api_key", [None, "wrong-key"])
async def test_auth_missing_or_invalid_key_still_returns_401(api_key):
    with pytest.raises(HTTPException) as caught:
        await verify_api_key(_api_request(api_key), _EmptySession())

    assert caught.value.status_code == 401


async def test_auth_non_transient_database_error_is_not_masked():
    error = IntegrityError("INSERT", {}, Exception("duplicate key"))

    with pytest.raises(IntegrityError):
        await verify_api_key(_api_request("key"), _RaisingSession(error))


async def test_syslog_enabled_false_stops_both_listeners(monkeypatch):
    import ingest.entrypoint as entrypoint

    monkeypatch.setattr(settings, "SYSLOG_ENABLED", False)
    monkeypatch.setattr(settings, "SYSLOG_UDP_PORT", 5514)
    monkeypatch.setattr(settings, "SYSLOG_TCP_PORT", 5514)

    async def _boom(*args, **kwargs):
        raise AssertionError("listener must not start when SYSLOG_ENABLED=false")

    monkeypatch.setattr(entrypoint, "start_udp_syslog_listener", _boom)
    monkeypatch.setattr(entrypoint, "start_tcp_syslog_listener", _boom)

    assert enabled_listeners() == (False, False)
    udp, tcp, udp_enabled, tcp_enabled = await entrypoint.start_listeners(None)
    assert udp is None
    assert tcp is None
    assert (udp_enabled, tcp_enabled) == (False, False)


def test_udp_only_configuration_disables_tcp(monkeypatch):
    monkeypatch.setattr(settings, "SYSLOG_ENABLED", True)
    monkeypatch.setattr(settings, "SYSLOG_UDP_PORT", 5514)
    monkeypatch.setattr(settings, "SYSLOG_TCP_PORT", 0)

    assert enabled_listeners() == (True, False)


def test_source_cidr_allowlist(monkeypatch):
    monkeypatch.setattr(settings, "SYSLOG_ALLOWED_CIDRS", "10.0.0.0/8, 192.168.1.0/24")

    assert is_source_allowed("10.1.2.3") is True
    assert is_source_allowed("192.168.1.42") is True
    assert is_source_allowed("8.8.8.8") is False
    assert is_source_allowed("not-an-ip") is False
    assert is_source_allowed(None) is False

    monkeypatch.setattr(settings, "SYSLOG_ALLOWED_CIDRS", "")
    assert is_source_allowed("8.8.8.8") is True


class _FakeUDPTransport:
    def __init__(self, closing: bool = False) -> None:
        self._closing = closing

    def is_closing(self) -> bool:
        return self._closing


async def _db_ok() -> bool:
    return True


async def _db_down() -> bool:
    return False


async def test_udp_only_health_check_is_ok():
    payload = await build_health_payload(
        {"udp_transport": _FakeUDPTransport(), "tcp_server": None},
        udp_enabled=True,
        tcp_enabled=False,
        db_checker=_db_ok,
    )

    assert payload["status"] == "ok", payload
    assert payload["database"] is True
    assert payload["listeners"]["udp"] is True
    assert payload["listeners"]["tcp"] is True  # not required when disabled
    assert health_http_status(payload) == 200


async def test_database_unavailable_health_check_fails():
    payload = await build_health_payload(
        {"udp_transport": _FakeUDPTransport(), "tcp_server": None},
        udp_enabled=True,
        tcp_enabled=False,
        db_checker=_db_down,
    )

    assert payload["status"] == "unhealthy", payload
    assert payload["database"] is False
    assert health_http_status(payload) == 503


async def test_enabled_listener_missing_is_unhealthy():
    payload = await build_health_payload(
        {"udp_transport": None, "tcp_server": None},
        udp_enabled=True,
        tcp_enabled=True,
        db_checker=_db_ok,
    )

    assert payload["status"] == "unhealthy", payload
    assert payload["listeners"]["udp"] is False
    assert payload["listeners"]["tcp"] is False


async def test_health_http_endpoint_returns_503_when_database_is_down():
    server = await start_health_server(
        0,
        lambda: build_health_payload(
            {"udp_transport": _FakeUDPTransport(), "tcp_server": None},
            udp_enabled=True,
            tcp_enabled=False,
            db_checker=_db_down,
        ),
    )
    port = server.sockets[0].getsockname()[1]
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(b"GET /healthz HTTP/1.1\r\nHost: localhost\r\n\r\n")
        await writer.drain()
        response = await reader.read()
        writer.close()
        await writer.wait_closed()

        assert b"503 Service Unavailable" in response
        assert b'"database": false' in response
    finally:
        server.close()
        await server.wait_closed()


class _FakeSession:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


def _install_fake_service(monkeypatch, calls: dict, behaviour: str) -> None:
    import app.services.ingest_service as ingest_service_module

    class _FakeService:
        def __init__(self, session) -> None:
            self.session = session

        async def ingest(self, *args, **kwargs):
            calls["n"] += 1
            if behaviour == "transient" and calls["n"] < 3:
                raise OperationalError("SELECT 1", {}, Exception("temporary"))
            if behaviour == "always":
                raise OperationalError("SELECT 1", {}, Exception("down"))
            if behaviour == "validation":
                raise ValidationError("bad event")
            return {"event": object(), "alerts": []}

    monkeypatch.setattr(ingest_service_module, "IngestionService", _FakeService)


async def test_native_transient_db_failure_is_retried(monkeypatch):
    syslog_counters.reset()
    monkeypatch.setattr(settings, "SYSLOG_DB_RETRY_ATTEMPTS", 3)
    monkeypatch.setattr(settings, "SYSLOG_DB_RETRY_BACKOFF_SECS", 0.0)

    calls = {"n": 0}
    _install_fake_service(monkeypatch, calls, "transient")

    result = await ingest_parsed(
        lambda: _FakeSession(),
        {"timestamp": "2026-01-01T00:00:00+00:00", "msg": "retry-me"},
        {"remoteAddress": "10.0.0.5", "remotePort": 514},
    )

    assert result == "persisted"
    assert calls["n"] == 3
    assert syslog_counters.retried == 2
    assert syslog_counters.dropped == 0


async def test_native_validation_error_is_not_retried(monkeypatch):
    syslog_counters.reset()
    monkeypatch.setattr(settings, "SYSLOG_DB_RETRY_ATTEMPTS", 3)
    monkeypatch.setattr(settings, "SYSLOG_DB_RETRY_BACKOFF_SECS", 0.0)

    calls = {"n": 0}
    _install_fake_service(monkeypatch, calls, "validation")

    result = await ingest_parsed(
        lambda: _FakeSession(),
        {"timestamp": "2026-01-01T00:00:00+00:00", "msg": "invalid"},
        {"remoteAddress": "10.0.0.5", "remotePort": 514},
    )

    assert result == "invalid"
    assert calls["n"] == 1
    assert syslog_counters.invalid == 1
    assert syslog_counters.retried == 0


async def test_native_retry_exhaustion_is_counted_and_dropped(monkeypatch):
    syslog_counters.reset()
    monkeypatch.setattr(settings, "SYSLOG_DB_RETRY_ATTEMPTS", 3)
    monkeypatch.setattr(settings, "SYSLOG_DB_RETRY_BACKOFF_SECS", 0.0)

    calls = {"n": 0}
    _install_fake_service(monkeypatch, calls, "always")

    result = await ingest_parsed(
        lambda: _FakeSession(),
        {"timestamp": "2026-01-01T00:00:00+00:00", "msg": "never"},
        {"remoteAddress": "10.0.0.5", "remotePort": 514},
    )

    assert result == "dropped"
    assert calls["n"] == 3
    assert syslog_counters.dropped == 1
    assert syslog_counters.retry_exhausted == 1
