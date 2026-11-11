"""Focused, DB-backed tests for the HTTPS Syslog ingestion path.

Covers assignment scenarios 1-4: single message, two-message batch, database
failure returning 503 (never a false 202), and per-line validation isolation.
"""

from __future__ import annotations

import asyncio
import json
import uuid

from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.core.database import async_session_maker
from app.models.events import Event
from app.services.ingest_service import IngestionService

SYSLOG_PATH = "/api/ingest/syslog"


def _line(marker: str, action: str = "DENY") -> str:
    return (
        f'<134>Oct 30 22:14:15 fw01 vendor=Fortinet product=FortiGate '
        f'action={action} src=10.0.0.5 dst=8.8.8.8 spt=54321 dpt=53 '
        f'proto=UDP msg="{marker}" policy=block-dns event=traffic'
    )


async def _stored_markers(tenant: str, markers: list[str]) -> set[str]:
    async with async_session_maker() as session:
        result = await session.execute(
            select(Event).where(Event.tenant == tenant).order_by(Event.ingested_at.desc()).limit(200)
        )
        rows = result.scalars().all()

    found: set[str] = set()
    for event in rows:
        try:
            blob = json.dumps(event.raw, default=str)
        except TypeError:
            blob = str(event.raw)
        for marker in markers:
            if marker in blob:
                found.add(marker)
    return found


def _headers(api_key: str, content_type: str = "text/plain") -> dict:
    return {"X-API-Key": api_key, "Content-Type": content_type}


def test_https_single_message_persists(client, api_key_demoa):
    marker = f"single-{uuid.uuid4().hex}"
    response = client.post(
        SYSLOG_PATH,
        headers=_headers(api_key_demoa),
        content=_line(marker).encode(),
    )

    assert response.status_code == 202, response.text
    body = response.json()
    assert body["accepted"] == 1, body
    assert body["rejected"] == 0, body
    assert body["errors"] == []
    assert marker in asyncio.run(_stored_markers("demoa", [marker]))


def test_https_two_message_batch_persists_both(client, api_key_demoa):
    first = f"batch-a-{uuid.uuid4().hex}"
    second = f"batch-b-{uuid.uuid4().hex}"
    payload = "\n".join([_line(first), _line(second)])

    response = client.post(
        SYSLOG_PATH,
        headers=_headers(api_key_demoa),
        content=payload.encode(),
    )

    assert response.status_code == 202, response.text
    body = response.json()
    assert body["accepted"] == 2, body
    assert body["rejected"] == 0, body
    assert asyncio.run(_stored_markers("demoa", [first, second])) == {first, second}


def test_database_failure_returns_503_not_202(client, api_key_demoa, monkeypatch):
    marker = f"dbfail-{uuid.uuid4().hex}"

    async def _fail(self, *args, **kwargs):
        raise OperationalError("INSERT", {}, Exception("connection refused"))

    monkeypatch.setattr(IngestionService, "ingest_batch_atomic", _fail)

    response = client.post(
        SYSLOG_PATH,
        headers=_headers(api_key_demoa),
        content=_line(marker).encode(),
    )

    assert response.status_code == 503, response.text
    assert response.headers.get("retry-after") == "5"
    body = response.json()
    assert body["accepted"] == 0
    assert body["rejected"] >= 1
    assert body["errors"][0]["error"].startswith("temporary storage failure")
    # Nothing may have been committed by the failing request.
    assert marker not in asyncio.run(_stored_markers("demoa", [marker]))


def test_validation_errors_are_isolated_per_line(client, api_key_demoa):
    good = f"isolated-good-{uuid.uuid4().hex}"
    payload = {
        "lines": [
            _line(good),
            {"not": "a string"},
        ]
    }

    response = client.post(
        SYSLOG_PATH,
        headers=_headers(api_key_demoa, "application/json"),
        content=json.dumps(payload).encode(),
    )

    assert response.status_code == 202, response.text
    body = response.json()
    assert body["accepted"] == 1, body
    assert body["rejected"] == 1, body
    assert body["errors"][0]["line"] == 1
    assert "string" in body["errors"][0]["error"]
    assert good in asyncio.run(_stored_markers("demoa", [good]))
