"""Ingestion contract: JSON, batch, file upload, and syslog over HTTP.

The SaaS deployment has no native syslog listener, so every sample source must
arrive through one of these HTTP paths. The checks use unique markers and read
the persisted row back where the response alone cannot prove normalization.
"""

from __future__ import annotations

import asyncio
import json
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.core.config import get_settings
from app.core.database import async_session_maker
from app.core.exceptions import ValidationError
from app.integrations.syslog import parse_syslog_message
from app.ingest.batch import (
    detect_format,
    looks_like_syslog_line,
    parse_batch_records,
    parse_csv_row,
    parse_json,
    validate_upload,
)
from app.models.events import Event
from app.services.ingest_service import IngestionService

from conftest import ADMIN_EMAIL, ADMIN_PASSWORD, login

SYSLOG_PATH = "/api/ingest/syslog"
MARKER = "phase5-ingest"


def _headers(api_key: str) -> dict:
    return {"X-API-Key": api_key, "Content-Type": "application/json"}


async def _events_for_tenant(tenant: str, limit: int = 100) -> list[Event]:
    async with async_session_maker() as session:
        result = await session.execute(
            select(Event)
            .where(Event.tenant == tenant)
            .order_by(Event.ingested_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


def _contains_marker(rows: list[Event], marker: str) -> bool:
    return any(marker in json.dumps(row.raw, default=str) for row in rows)


def _syslog_line(marker: str, action: str = "DENY") -> str:
    return (
        "<134>Oct 30 22:14:15 fw01 vendor=Fortinet product=FortiGate "
        f"action={action} src=10.0.0.5 dst=8.8.8.8 spt=54321 dpt=53 "
        f'proto=UDP msg="{marker}" policy=block-dns event=traffic'
    )


def test_single_event_ingest_normalizes_and_scopes_to_api_key(client, api_key):
    src_ip = "198.51.100.21"
    event = {
        "source": "firewall",
        "event_type": "traffic_blocked",
        "action": "DENY",
        "src_ip": src_ip,
        "dst_ip": "203.0.113.9",
        "protocol": "udp",
        "severity": 5,
        "vendor": "unit-test",
        "product": "ngfw",
        "description": MARKER,
    }

    response = client.post("/api/ingest", json=event, headers=_headers(api_key))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["ingested"] == 1
    assert body["eventId"]

    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    logs = client.get("/api/events", params={"src_ip": src_ip}).json()["logs"]
    assert len(logs) == 1
    assert logs[0]["tenant"] == "demoa"
    assert logs[0]["source"] == "firewall"
    assert logs[0]["severity"] == 5
    assert logs[0]["id"] == body["eventId"]


def test_batch_ingest_counts_per_record_and_keeps_good_rows(client, api_key):
    events = [
        {"source": "api", "event_type": f"{MARKER}_batch_{i}", "severity": 3, "action": "LOGIN"}
        for i in range(3)
    ]
    response = client.post(
        "/api/ingest/batch", json={"events": events}, headers=_headers(api_key)
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["parsed"], body["ingested"], body["rejected"]) == (3, 3, 0)

    bad = {
        "events": [
            {"source": "api", "event_type": f"{MARKER}_good"},
            {"source": "api", "event_type": f"{MARKER}_bad", "@timestamp": "not-a-date"},
        ]
    }
    response = client.post("/api/ingest/batch", json=bad, headers=_headers(api_key))
    assert response.status_code == 422, response.text


def test_ingest_rejects_malformed_payloads(client, api_key):
    headers = _headers(api_key)

    response = client.post("/api/ingest", content=b"", headers=headers)
    assert response.status_code == 400, response.text

    response = client.post("/api/ingest", content=b"not json", headers=headers)
    assert response.status_code == 400, response.text

    response = client.post("/api/ingest", json={}, headers=headers)
    assert response.status_code == 422, response.text

    response = client.post(
        "/api/ingest",
        json={"tenant": "demoa", "source": "api", "event_type": "x", "@timestamp": "bad"},
        headers=headers,
    )
    assert response.status_code == 422, response.text

    response = client.post(
        "/api/ingest",
        json={"source": "skynet", "event_type": "x"},
        headers=headers,
    )
    assert response.status_code == 400, response.text
    assert "Unsupported source" in response.json()["detail"]


def test_ingest_enforces_api_keys_and_tenant_binding(client, api_key):
    response = client.post("/api/ingest", json={"source": "api", "event_type": "no_key"})
    assert response.status_code == 401, response.text

    response = client.post(
        "/api/ingest",
        json={"source": "api", "event_type": "unknown_key"},
        headers=_headers("unknown-key-that-does-not-exist"),
    )
    assert response.status_code == 401, response.text

    response = client.post(
        "/api/ingest",
        json={"source": "api", "event_type": "cross_tenant", "tenant": "demob"},
        headers=_headers(api_key),
    )
    assert response.status_code == 403, response.text
    assert "demob" in response.json()["detail"]


def test_file_upload_parses_jsonl_and_csv(client, api_key):
    jsonl = (
        json.dumps({"source": "api", "event_type": f"{MARKER}_file_0"})
        + "\n{not valid json\n"
        + json.dumps({"source": "api", "event_type": f"{MARKER}_file_1"})
        + "\n"
    ).encode()
    response = client.post(
        "/api/ingest/file",
        files={"file": ("probe.jsonl", jsonl, "application/x-ndjson")},
        headers={"X-API-Key": api_key},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["format"] == "jsonl"
    assert (body["parsed"], body["ingested"], body["rejected"]) == (3, 2, 1)
    assert any("Invalid JSON" in error["error"] for error in body["errors"])

    csv_content = (
        "source,event_type,severity,src_ip,action\n"
        f"api,{MARKER}_csv,4,198.51.100.31,LOGIN\n"
        f"api,{MARKER}_csv2,6,198.51.100.32,LOGIN\n"
    ).encode()
    response = client.post(
        "/api/ingest/file",
        files={"file": ("probe.csv", csv_content, "text/csv")},
        headers={"X-API-Key": api_key},
    )
    assert response.status_code == 200, response.text
    assert response.json()["format"] == "csv"
    assert response.json()["ingested"] == 2

    # Format detection and the standalone batch helpers used by the upload path.
    assert detect_format("[]", "probe.jsonl", "") == "jsonl"
    assert detect_format("[]", "probe.ndjson", "") == "jsonl"
    assert detect_format("{}", "probe.json", "") == "json"
    assert detect_format("a,b", "probe.csv", "") == "csv"
    assert detect_format("a,b", "probe.log", "text/csv") == "csv"
    assert detect_format('{"a":1}', "probe.txt", "application/json") == "json"
    assert detect_format("", "probe", "application/x-ndjson") == "jsonl"
    assert detect_format("a,b", "probe.log", "text/plain") == "csv"
    assert detect_format("just one line", "probe.log", "text/plain") == "jsonl"

    syslog_text = (
        "<34>Oct 11 22:14:15 host app: first\n"
        "<34>Oct 11 22:14:16 host app: second"
    )
    assert detect_format(syslog_text, "probe.log", "text/plain") == "syslog"
    assert looks_like_syslog_line("<34>Oct 11 22:14:15 host")
    assert looks_like_syslog_line("Oct 11 22:14:15 host app: hi")
    assert looks_like_syslog_line("1 2003-10-11T22:14:15Z host app - - hi")
    assert not looks_like_syslog_line("   ")

    events, rejected, fmt = parse_batch_records(
        b'{"events":[{"a":1}, "bad"]}', "probe.json", "application/json"
    )
    assert (fmt, events, rejected) == ("json", [{"a": 1}], [])

    events, rejected, fmt = parse_batch_records(b'{"a":1}\n[1]\n', "probe.jsonl", "")
    assert fmt == "jsonl"
    assert events == [{"a": 1}]
    assert len(rejected) == 1

    events, rejected, fmt = parse_batch_records(syslog_text.encode(), "probe.log", "text/plain")
    assert fmt == "syslog"
    assert len(events) == 2 and rejected == []

    assert parse_csv_row('a,"b,c",d') == ["a", "b,c", "d"]
    assert parse_json('[{"a":1}, 2]') == [{"a": 1}]
    with pytest.raises(ValidationError):
        parse_json("not json")
    with pytest.raises(ValidationError):
        parse_json("42")
    with pytest.raises(ValidationError):
        parse_batch_records(b"", "probe.json", "")
    with pytest.raises(ValidationError):
        parse_batch_records(b"\xff\xfe", "probe.json", "")
    with pytest.raises(ValidationError):
        parse_batch_records(b"[1, 2]", "probe.json", "")

    validate_upload("probe.json", 1)
    for filename, size in (("noext", 1), ("probe.exe", 1), ("probe.json", 0)):
        with pytest.raises(ValidationError):
            validate_upload(filename, size)


def test_file_upload_rejects_bad_files(client, api_key):
    headers = {"X-API-Key": api_key}

    response = client.post(
        "/api/ingest/file",
        files={"file": ("payload.exe", b"MZ....", "application/octet-stream")},
        headers=headers,
    )
    assert response.status_code == 400, response.text
    assert "Unsupported file type" in response.json()["detail"]

    response = client.post(
        "/api/ingest/file",
        files={"file": ("empty.json", b"", "application/json")},
        headers=headers,
    )
    assert response.status_code == 400, response.text

    settings = get_settings()
    original = settings.INGEST_MAX_FILE_BYTES
    settings.INGEST_MAX_FILE_BYTES = 64
    try:
        response = client.post(
            "/api/ingest/file",
            files={"file": ("big.json", b"[" + b" " * 128 + b"]", "application/json")},
            headers=headers,
        )
        assert response.status_code == 413, response.text
    finally:
        settings.INGEST_MAX_FILE_BYTES = original


def test_http_syslog_accepts_rfc3164_and_rfc5424(client, api_key_demoa):
    rfc3164_marker = f"httpsyslog-rfc3164-{uuid.uuid4().hex}"
    response = client.post(
        SYSLOG_PATH,
        headers={"X-API-Key": api_key_demoa, "Content-Type": "text/plain"},
        content=_syslog_line(rfc3164_marker).encode(),
    )
    assert response.status_code == 202, response.text
    assert response.json() == {"accepted": 1, "rejected": 0, "errors": []}

    rfc5424_marker = f"httpsyslog-rfc5424-{uuid.uuid4().hex}"
    line = (
        f"<165>1 2026-11-09T10:00:00Z mymachine.example.com su - ID47 - "
        f'msg="{rfc5424_marker}"'
    )
    response = client.post(
        SYSLOG_PATH,
        headers={"X-API-Key": api_key_demoa},
        json={"lines": [line]},
    )
    assert response.status_code == 202, response.text
    assert response.json()["accepted"] == 1

    rows = asyncio.run(_events_for_tenant("demoa"))
    assert _contains_marker(rows, rfc3164_marker), "RFC3164 line was not stored"
    assert _contains_marker(rows, rfc5424_marker), "RFC5424 line was not stored"
    stored = next(row for row in rows if rfc3164_marker in json.dumps(row.raw, default=str))
    assert str(stored.source) == "firewall"
    assert "transport=http-syslog" in (stored._tags or [])


def test_http_syslog_partial_failure_and_limits(client, api_key_demoa):
    marker = f"httpsyslog-partial-{uuid.uuid4().hex}"
    response = client.post(
        SYSLOG_PATH,
        headers={"X-API-Key": api_key_demoa},
        json={"lines": [_syslog_line(marker), 123]},
    )
    assert response.status_code == 202, response.text
    body = response.json()
    assert (body["accepted"], body["rejected"]) == (1, 1)
    assert body["errors"][0]["line"] == 1

    settings = get_settings()
    original_bytes = settings.INGEST_HTTP_SYSLOG_MAX_BYTES
    original_lines = settings.INGEST_HTTP_SYSLOG_MAX_LINES
    try:
        settings.INGEST_HTTP_SYSLOG_MAX_BYTES = 128
        response = client.post(
            SYSLOG_PATH,
            headers={"X-API-Key": api_key_demoa, "Content-Type": "text/plain"},
            content=("x" * 512).encode(),
        )
        assert response.status_code == 413, response.text

        settings.INGEST_HTTP_SYSLOG_MAX_LINES = 2
        response = client.post(
            SYSLOG_PATH,
            headers={"X-API-Key": api_key_demoa},
            json={"lines": [_syslog_line(f"limit-{i}") for i in range(3)]},
        )
        assert response.status_code == 413, response.text
    finally:
        settings.INGEST_HTTP_SYSLOG_MAX_BYTES = original_bytes
        settings.INGEST_HTTP_SYSLOG_MAX_LINES = original_lines


def test_http_syslog_rejects_missing_key_and_cross_tenant(client, api_key_demoa):
    response = client.post(
        SYSLOG_PATH,
        headers={"Content-Type": "text/plain"},
        content=_syslog_line("no-key").encode(),
    )
    assert response.status_code == 401, response.text

    response = client.post(
        SYSLOG_PATH,
        headers={"X-API-Key": "not-a-real-key", "Content-Type": "text/plain"},
        content=_syslog_line("bad-key").encode(),
    )
    assert response.status_code == 401, response.text

    response = client.post(
        f"{SYSLOG_PATH}?tenant=demob",
        headers={"X-API-Key": api_key_demoa, "Content-Type": "text/plain"},
        content=_syslog_line("cross-tenant").encode(),
    )
    assert response.status_code == 403, response.text

    response = client.post(
        SYSLOG_PATH,
        headers={"X-API-Key": api_key_demoa},
        json={"tenant": "demob", "lines": [_syslog_line("cross-tenant-body")]},
    )
    assert response.status_code == 403, response.text


def test_http_syslog_rate_limit_returns_429(client, api_key_demoa, monkeypatch):
    """Assignment requirement: HTTP syslog ingestion is rate limited."""
    monkeypatch.setattr(get_settings(), "INGEST_RATE_LIMIT", "2/minute", raising=False)
    headers = {"X-API-Key": api_key_demoa, "Content-Type": "text/plain"}

    first = client.post(SYSLOG_PATH, headers=headers, content=_syslog_line("rl-1").encode())
    second = client.post(SYSLOG_PATH, headers=headers, content=_syslog_line("rl-2").encode())
    third = client.post(SYSLOG_PATH, headers=headers, content=_syslog_line("rl-3").encode())

    assert first.status_code == 202, first.text
    assert second.status_code == 202, second.text
    assert third.status_code == 429, third.text
    assert third.headers.get("Retry-After")


def test_ingest_rate_limit_per_api_key_returns_429(client, api_key, monkeypatch):
    """Assignment requirement: JSON ingest is rate limited per API key."""
    monkeypatch.setattr(get_settings(), "INGEST_RATE_LIMIT", "2/minute", raising=False)
    payload = {"source": "api", "event_type": "rate_limit_probe", "severity": 3}

    statuses = [
        client.post("/api/ingest", json=payload, headers=_headers(api_key)).status_code
        for _ in range(3)
    ]

    assert statuses == [200, 200, 429], statuses


def test_native_listener_parser_accepts_assignment_firewall_line():
    """Assignment requirement: the UDP/TCP listener parser handles syslog."""
    parsed = parse_syslog_message(
        '<134>Aug 20 12:44:56 fw01 vendor=demo product=ngfw action=deny '
        'src=10.0.1.10 dst=8.8.8.8 spt=5353 dpt=53 proto=udp '
        'msg="DNS blocked" policy=Block-DNS'
    )

    assert parsed is not None
    assert parsed["priority"] == 134
    assert parsed["host"] == "fw01"
    assert parsed["action"] == "deny"
    assert parsed["src"] == "10.0.1.10"
    assert parsed["dst"] == "8.8.8.8"
    assert parsed["spt"] == "5353"
    assert parsed["dpt"] == "53"
    assert parsed["proto"] == "udp"
    assert parsed["policy"] == "Block-DNS"


def test_http_syslog_transient_db_failure_returns_503(client, api_key_demoa, monkeypatch):
    """Assignment requirement: a transient DB failure is retryable, not a 202."""
    marker_one = f"dbfail-one-{uuid.uuid4().hex}"
    marker_two = f"dbfail-two-{uuid.uuid4().hex}"

    async def _fail(self, *args, **kwargs):
        raise OperationalError("INSERT", {}, Exception("connection refused"))

    monkeypatch.setattr(IngestionService, "ingest_batch_atomic", _fail)

    response = client.post(
        SYSLOG_PATH,
        headers={"X-API-Key": api_key_demoa},
        json={"lines": [_syslog_line(marker_one), _syslog_line(marker_two)]},
    )

    assert response.status_code == 503, response.text
    assert response.headers.get("retry-after") == "5"
    body = response.json()
    assert body["accepted"] == 0
    assert body["rejected"] == 2
    assert body["errors"][0]["error"].startswith("temporary storage failure")

    rows = asyncio.run(_events_for_tenant("demoa"))
    assert not _contains_marker(rows, marker_one)
    assert not _contains_marker(rows, marker_two)
