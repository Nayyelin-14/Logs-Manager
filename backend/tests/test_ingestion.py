"""Ingestion acceptance tests.

Covers the assignment's ingestion requirements with a small number of
end-to-end checks:

* HTTP JSON ingestion is normalized and persisted.
* Batch and file ingestion (JSON Lines / CSV) count accepted and rejected rows.
* The four representative sample sources (AWS, M365, AD, CrowdStrike) ingest
  through their supported path and keep the normalized fields.
* Syslog is accepted over HTTP in both RFC3164 and RFC5424 form.
* The UDP and TCP listeners still persist rows.
* Invalid sources, missing API keys, and cross-tenant keys are rejected.
"""

from __future__ import annotations

import asyncio
import json
import pathlib
import uuid

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import async_session_maker
from app.models.events import Event

from conftest import ADMIN_EMAIL, ADMIN_PASSWORD, login

SAMPLES_DIR = pathlib.Path(__file__).resolve().parents[2] / "samples"
SYSLOG_PATH = "/api/ingest/syslog"

SAMPLE_CASES = [
    (
        "aws_cloudtrail.json",
        "aws",
        "CreateUser",
        "alice",
        "203.0.113.10",
    ),
    (
        "m365_audit.json",
        "m365",
        "UserLoggedIn",
        "alice@example.com",
        "203.0.113.20",
    ),
    (
        "ad_4625.json",
        "ad",
        "ad_logon_failed",
        "alice",
        "10.0.0.77",
    ),
    (
        "crowdstrike.json",
        "crowdstrike",
        "MalwareDetected",
        "alice",
        "10.0.0.42",
    ),
]


def _headers(api_key: str) -> dict:
    return {"X-API-Key": api_key, "Content-Type": "application/json"}


def _firewall_event(src_ip: str) -> dict:
    return {
        "source": "firewall",
        "event_type": "traffic_blocked",
        "action": "DENY",
        "src_ip": src_ip,
        "dst_ip": "203.0.113.9",
        "protocol": "udp",
        "severity": 5,
        "vendor": "unit-test",
        "product": "ngfw",
        "description": "ingestion-acceptance",
    }


def _line(marker: str, action: str = "DENY") -> str:
    return (
        f"<134>Oct 30 22:14:15 fw01 vendor=Fortinet product=FortiGate "
        f"action={action} src=10.0.0.5 dst=8.8.8.8 spt=54321 dpt=53 "
        f'proto=UDP msg="{marker}" policy=block-dns event=traffic'
    )


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


def test_http_json_ingest_normalizes_and_persists(client, api_key):
    src_ip = "198.51.100.21"
    response = client.post(
        "/api/ingest", json=_firewall_event(src_ip), headers=_headers(api_key)
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["ingested"] == 1
    assert body["eventId"]

    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    logs = client.get("/api/get-logs", params={"src_ip": src_ip}).json()["logs"]
    assert len(logs) == 1
    log = logs[0]
    assert log["tenant"] == "demoa"
    assert log["source"] == "firewall"
    assert log["eventType"] == "firewall_deny"
    assert log["action"] == "deny"
    assert log["srcIp"] == src_ip


def test_batch_ingest_counts_per_record(client, api_key):
    events = [
        {
            "source": "api",
            "event_type": f"batch_probe_{i}",
            "user": f"batch_user_{i}",
            "severity": 3,
            "action": "LOGIN",
        }
        for i in range(3)
    ]
    response = client.post(
        "/api/ingest/batch", json={"events": events}, headers=_headers(api_key)
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["parsed"] == 3
    assert body["ingested"] == 3
    assert body["rejected"] == 0


def test_file_ingest_jsonl_and_csv(client, api_key):
    jsonl = (
        json.dumps({"source": "api", "event_type": "file_probe_0", "user": "file0"})
        + "\n"
        + "{not valid json\n"
        + json.dumps({"source": "api", "event_type": "file_probe_1", "user": "file1"})
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
    assert body["parsed"] == 3
    assert body["ingested"] == 2
    assert body["rejected"] == 1
    assert any("Invalid JSON" in error.get("error", "") for error in body["errors"])

    csv = (
        "source,event_type,severity,src_ip,action\n"
        "api,csv_probe_0,4,198.51.100.31,LOGIN\n"
        "api,csv_probe_1,6,198.51.100.32,LOGIN\n"
    ).encode()
    response = client.post(
        "/api/ingest/file",
        files={"file": ("probe.csv", csv, "text/csv")},
        headers={"X-API-Key": api_key},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["format"] == "csv"
    assert body["ingested"] == 2
    assert body["rejected"] == 0


def test_representative_sample_sources_ingest_and_normalize(client, api_key):
    event_ids: list[tuple[str, tuple]] = []

    for filename, source, event_type, user, src_ip in SAMPLE_CASES:
        sample = json.loads((SAMPLES_DIR / filename).read_text())
        response = client.post("/api/ingest", json=sample, headers=_headers(api_key))
        assert response.status_code == 200, f"{filename}: {response.text}"
        body = response.json()
        assert body["success"] is True
        assert body["eventId"]
        event_ids.append(
            (body["eventId"], (filename, source, event_type, user, src_ip))
        )

    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    for event_id, (filename, source, event_type, user, src_ip) in event_ids:
        response = client.get(f"/api/events/{event_id}")
        assert response.status_code == 200, f"{filename}: {response.text}"
        event = response.json()
        assert event["tenant"] == "demoa"
        assert event["source"] == source, filename
        assert event["eventType"] == event_type, filename
        assert event["user"] == user, filename
        assert event["srcIp"] == src_ip, filename


def test_syslog_http_accepts_rfc3164_and_rfc5424(client, api_key_demoa):
    rfc3164_marker = f"httpsyslog-rfc3164-{uuid.uuid4().hex}"
    response = client.post(
        SYSLOG_PATH,
        headers={"X-API-Key": api_key_demoa, "Content-Type": "text/plain"},
        content=_line(rfc3164_marker).encode(),
    )
    assert response.status_code == 202, response.text
    assert response.json()["accepted"] == 1

    rfc5424_marker = f"httpsyslog-rfc5424-{uuid.uuid4().hex}"
    rfc5424 = (
        "<165>1 2026-11-09T10:00:00Z mymachine.example.com su - ID47 - "
        f'msg="{rfc5424_marker}"'
    )
    response = client.post(
        SYSLOG_PATH,
        headers={"X-API-Key": api_key_demoa},
        json={"lines": [rfc5424]},
    )
    assert response.status_code == 202, response.text
    assert response.json()["accepted"] == 1

    rows = asyncio.run(_events_for_tenant("demoa"))
    for marker in (rfc3164_marker, rfc5424_marker):
        row = next((row for row in rows if marker in json.dumps(row.raw, default=str)), None)
        assert row is not None, f"syslog line was not stored: {marker}"
        assert str(row.source) == "firewall"
        assert "transport=http-syslog" in (row._tags or [])


@pytest.mark.asyncio
async def test_udp_and_tcp_listeners_store_rows(test_database):
    from app.integrations.syslog import SyslogTCPProtocol, SyslogUDPProtocol

    udp_marker = f"udp-regression-{uuid.uuid4().hex}"
    await SyslogUDPProtocol(async_session_maker)._handle(
        f'<134>action=DENY msg="{udp_marker}"'.encode(),
        ("127.0.0.1", 12345),
    )

    tcp_marker = f"tcp-regression-{uuid.uuid4().hex}"
    await SyslogTCPProtocol(async_session_maker)._ingest_line(
        f'<134>action=DENY msg="{tcp_marker}"',
        ("127.0.0.1", 12345),
    )

    tenant = get_settings().SYSLOG_TENANT.strip().lower()
    rows = await _events_for_tenant(tenant)
    assert _contains_marker(rows, udp_marker), "UDP listener stopped storing rows"
    assert _contains_marker(rows, tcp_marker), "TCP listener stopped storing rows"


def test_ingest_validation_and_api_key_boundaries(client, api_key):
    response = client.post(
        "/api/ingest",
        json={"source": "skynet", "event_type": "unsupported_source_probe"},
        headers=_headers(api_key),
    )
    assert response.status_code == 400, response.text
    assert "Unsupported source" in response.json()["detail"]

    response = client.post(
        "/api/ingest",
        json={
            "source": "api",
            "event_type": "cross_tenant_probe",
            "tenant": "demob",
        },
        headers=_headers(api_key),
    )
    assert response.status_code == 403, response.text
    assert "demob" in response.json()["detail"]

    response = client.post(
        "/api/ingest",
        json={"source": "api", "event_type": "missing_key_probe"},
    )
    assert response.status_code == 401, response.text

    response = client.post(
        "/api/ingest",
        json={"source": "api", "event_type": "unknown_key_probe"},
        headers=_headers("unknown-key-that-does-not-exist"),
    )
    assert response.status_code == 401, response.text
