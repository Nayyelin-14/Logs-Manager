"""Syslog-over-HTTPS ingestion tests.

These cover the SaaS transport added on top of the existing UDP/TCP syslog
listener. The listener itself is regression-tested at the protocol level so the
shared parser/ingestion path is proven to still store rows.
"""

from __future__ import annotations

import asyncio
import json
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import async_session_maker
from app.core.limiting import limiter
from app.main import app
from app.models.events import Event
from app.core.config import get_settings

SYSLOG_PATH = "/api/ingest/syslog"


def _line(marker: str, action: str = "DENY") -> str:
    return (
        f'<134>Oct 30 22:14:15 fw01 vendor=Fortinet product=FortiGate '
        f'action={action} src=10.0.0.5 dst=8.8.8.8 spt=54321 dpt=53 '
        f'proto=UDP msg="{marker}" policy=block-dns event=traffic'
    )


async def _events_for_tenant(tenant: str, limit: int = 50) -> list[Event]:
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


def test_rfc3164_text_line_accepted_and_stored(client, api_key_demoa):
    marker = f"httpsyslog-rfc3164-{uuid.uuid4().hex}"
    response = client.post(
        SYSLOG_PATH,
        headers={"X-API-Key": api_key_demoa, "Content-Type": "text/plain"},
        content=_line(marker).encode(),
    )
    assert response.status_code == 202, response.text
    assert response.json() == {"accepted": 1, "rejected": 0, "errors": []}

    rows = asyncio.run(_events_for_tenant("demoa"))
    row = next((r for r in rows if marker in json.dumps(r.raw, default=str)), None)
    assert row is not None, "RFC3164 line was not stored"
    assert str(row.source) == "firewall"
    assert "transport=http-syslog" in (row._tags or [])


def test_rfc5424_json_line_accepted_and_stored(client, api_key_demoa):
    marker = f"httpsyslog-rfc5424-{uuid.uuid4().hex}"
    line = (
        f"<165>1 2026-11-09T10:00:00Z mymachine.example.com su - ID47 - "
        f"msg=\"{marker}\""
    )
    response = client.post(
        SYSLOG_PATH,
        headers={"X-API-Key": api_key_demoa},
        json={"lines": [line]},
    )
    assert response.status_code == 202, response.text
    assert response.json()["accepted"] == 1

    rows = asyncio.run(_events_for_tenant("demoa"))
    row = next((r for r in rows if marker in json.dumps(r.raw, default=str)), None)
    assert row is not None, "RFC5424 line was not stored"
    assert "transport=http-syslog" in (row._tags or [])


def test_key_value_firewall_line(client, api_key_demoa):
    marker = f"httpsyslog-fw-{uuid.uuid4().hex}"
    line = (
        '<134>Oct 30 22:14:15 fw01 vendor=Fortinet product=FortiGate '
        'action=DENY src=10.0.0.5 dst=8.8.8.8 spt=54321 dpt=53 proto=UDP '
        f'msg="{marker}" policy=block-dns if=wan1 event=traffic '
        'mac=00:11:22:33:44:55 reason=policy'
    )
    response = client.post(
        SYSLOG_PATH,
        headers={"X-API-Key": api_key_demoa, "Content-Type": "text/plain"},
        content=line.encode(),
    )
    assert response.status_code == 202, response.text

    rows = asyncio.run(_events_for_tenant("demoa"))
    row = next((r for r in rows if marker in json.dumps(r.raw, default=str)), None)
    assert row is not None
    assert row.src_ip == "10.0.0.5"
    assert row.action == "deny"


def test_router_source_line_uses_network_source(client, api_key_demoa):
    marker = f"httpsyslog-router-{uuid.uuid4().hex}"
    line = (
        f'<190>Oct 30 22:15:01 router01 source=network vendor=Cisco product=IOS '
        f'action=ALLOW src=192.168.1.10 dst=1.1.1.1 msg="{marker}" event=traffic'
    )
    response = client.post(
        SYSLOG_PATH,
        headers={"X-API-Key": api_key_demoa, "Content-Type": "text/plain"},
        content=line.encode(),
    )
    assert response.status_code == 202, response.text

    rows = asyncio.run(_events_for_tenant("demoa"))
    row = next((r for r in rows if marker in json.dumps(r.raw, default=str)), None)
    assert row is not None
    assert str(row.source) == "network"


def test_partial_failure_returns_rejected_line(client, api_key_demoa):
    marker = f"httpsyslog-partial-{uuid.uuid4().hex}"
    response = client.post(
        SYSLOG_PATH,
        headers={"X-API-Key": api_key_demoa},
        json={"lines": [_line(marker), 123]},
    )
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["accepted"] == 1
    assert body["rejected"] == 1
    assert body["errors"][0]["line"] == 1


def test_requires_api_key(client):
    response = client.post(
        SYSLOG_PATH,
        headers={"Content-Type": "text/plain"},
        content=_line("no-key").encode(),
    )
    assert response.status_code == 401


def test_rejects_invalid_api_key(client):
    response = client.post(
        SYSLOG_PATH,
        headers={"X-API-Key": "not-a-real-key", "Content-Type": "text/plain"},
        content=_line("bad-key").encode(),
    )
    assert response.status_code == 401


def test_cross_tenant_query_is_forbidden(client, api_key_demoa):
    response = client.post(
        f"{SYSLOG_PATH}?tenant=demob",
        headers={"X-API-Key": api_key_demoa, "Content-Type": "text/plain"},
        content=_line("cross-tenant").encode(),
    )
    assert response.status_code == 403


def test_cross_tenant_json_body_is_forbidden(client, api_key_demoa):
    response = client.post(
        SYSLOG_PATH,
        headers={"X-API-Key": api_key_demoa},
        json={"tenant": "demob", "lines": [_line("cross-tenant-body")]},
    )
    assert response.status_code == 403


def test_body_size_limit(client, api_key_demoa, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "INGEST_HTTP_SYSLOG_MAX_BYTES", 128)
    response = client.post(
        SYSLOG_PATH,
        headers={"X-API-Key": api_key_demoa, "Content-Type": "text/plain"},
        content=("x" * 512).encode(),
    )
    assert response.status_code == 413


def test_line_limit(client, api_key_demoa, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "INGEST_HTTP_SYSLOG_MAX_LINES", 2)
    response = client.post(
        SYSLOG_PATH,
        headers={"X-API-Key": api_key_demoa},
        json={"lines": [_line("limit-1"), _line("limit-2"), _line("limit-3")]},
    )
    assert response.status_code == 413


def test_route_is_present_and_not_shadowed():
    paths = app.openapi()["paths"]
    assert SYSLOG_PATH in paths, "syslog route missing from OpenAPI"
    assert "post" in paths[SYSLOG_PATH], "syslog route is not POST"


def test_rate_limit_returns_429(api_key_demoa, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "INGEST_RATE_LIMIT", "2/minute")
    limiter.reset()
    try:
        with TestClient(app) as rate_client:
            responses = [
                rate_client.post(
                    SYSLOG_PATH,
                    headers={
                        "X-API-Key": api_key_demoa,
                        "Content-Type": "text/plain",
                    },
                    content=_line(f"rate-{i}").encode(),
                )
                for i in range(3)
            ]
        assert [r.status_code for r in responses[:2]] == [202, 202]
        assert responses[2].status_code == 429
    finally:
        limiter.reset()


@pytest.mark.asyncio
async def test_udp_listener_protocol_still_stores_rows(test_database):
    from app.integrations.syslog import SyslogUDPProtocol

    marker = f"udp-regression-{uuid.uuid4().hex}"
    protocol = SyslogUDPProtocol(async_session_maker)
    await protocol._handle(
        f'<134>action=DENY msg="{marker}"'.encode(),
        ("127.0.0.1", 12345),
    )

    tenant = get_settings().SYSLOG_TENANT.strip().lower()
    rows = await _events_for_tenant(tenant)
    assert _contains_marker(rows, marker), "UDP listener path stopped storing rows"


@pytest.mark.asyncio
async def test_tcp_listener_protocol_still_stores_rows(test_database):
    from app.integrations.syslog import SyslogTCPProtocol

    marker = f"tcp-regression-{uuid.uuid4().hex}"
    protocol = SyslogTCPProtocol(async_session_maker)
    await protocol._ingest_line(
        f'<134>action=DENY msg="{marker}"',
        ("127.0.0.1", 12345),
    )

    tenant = get_settings().SYSLOG_TENANT.strip().lower()
    rows = await _events_for_tenant(tenant)
    assert _contains_marker(rows, marker), "TCP listener path stopped storing rows"
