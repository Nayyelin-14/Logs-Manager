"""Alerting acceptance tests.

Uses the seeded brute-force rule (5 failed AD logons from one source IP in five
minutes) to prove that a matching event generates an alert, aggregates repeated
events into one record, records a notification, and never mixes evidence across
tenants. One additional test covers rule validation and the viewer boundary.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.database import async_session_maker
from app.models.events import Event

from conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    VIEWER_A_EMAIL,
    VIEWER_A_PASSWORD,
    login,
)

AD_FAILURE = {
    "source": "ad",
    "event_id": 4625,
    "event_type": "LogonFailed",
    "host": "DC01",
    "action": "LOGIN",
    "status": "Failure",
    "severity": 7,
}


def _ingest_failure(
    client,
    api_key: str,
    *,
    tenant: str,
    src_ip: str,
    user: str,
    tag: str,
    ts: datetime,
):
    event = {
        **AD_FAILURE,
        "tenant": tenant,
        "src_ip": src_ip,
        "user": user,
        "src_port": "49152",
        "@timestamp": ts.isoformat(),
        "tags": [tag],
    }
    return client.post(
        "/api/ingest",
        json=event,
        headers={"X-API-Key": api_key, "Content-Type": "application/json"},
    )


def _alerts_for_tag(client, tag: str) -> list[dict]:
    response = client.get("/api/get-alerts", params={"search": tag})
    assert response.status_code == 200, response.text
    return response.json()["alerts"]


def test_threshold_rule_triggers_one_alert_and_aggregates(client, api_key_demoa):
    tag = f"brute-a-{uuid.uuid4().hex}"
    src_ip = "203.0.113.201"
    now = datetime.now(timezone.utc)

    for i in range(5):
        response = _ingest_failure(
            client,
            api_key_demoa,
            tenant="demoa",
            src_ip=src_ip,
            user=f"demo\\user{i}",
            tag=tag,
            ts=now - timedelta(seconds=30 * i),
        )
        assert response.status_code == 200, response.text

    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    alerts = _alerts_for_tag(client, tag)
    assert len(alerts) == 1, f"expected one alert, got {len(alerts)}"
    alert = alerts[0]
    assert alert["tenant"] == "demoa"
    assert alert["status"] == "open"
    assert alert["count"] == 5
    assert "Brute force" in alert["description"]

    for i in range(5, 7):
        response = _ingest_failure(
            client,
            api_key_demoa,
            tenant="demoa",
            src_ip=src_ip,
            user=f"demo\\user{i}",
            tag=tag,
            ts=datetime.now(timezone.utc),
        )
        assert response.status_code == 200, response.text

    alerts = _alerts_for_tag(client, tag)
    assert len(alerts) == 1, "more failures must update the existing alert"
    assert alerts[0]["count"] == 7


def test_rule_does_not_fire_below_threshold_or_across_ips(client, api_key_demoa):
    now = datetime.now(timezone.utc)

    low_tag = f"brute-low-{uuid.uuid4().hex}"
    for i in range(4):
        response = _ingest_failure(
            client,
            api_key_demoa,
            tenant="demoa",
            src_ip="198.51.100.150",
            user=f"low{i}",
            tag=low_tag,
            ts=now - timedelta(seconds=10 * i),
        )
        assert response.status_code == 200, response.text

    spread_tag = f"brute-spread-{uuid.uuid4().hex}"
    for i in range(5):
        response = _ingest_failure(
            client,
            api_key_demoa,
            tenant="demoa",
            src_ip=f"198.51.100.{160 + i}",
            user=f"spread{i}",
            tag=spread_tag,
            ts=now - timedelta(seconds=10 * i),
        )
        assert response.status_code == 200, response.text

    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    assert _alerts_for_tag(client, low_tag) == []
    assert _alerts_for_tag(client, spread_tag) == []


def test_alert_records_a_notification(client, api_key_demoa):
    tag = f"brute-notify-{uuid.uuid4().hex}"
    now = datetime.now(timezone.utc)

    for i in range(5):
        response = _ingest_failure(
            client,
            api_key_demoa,
            tenant="demoa",
            src_ip="203.0.113.202",
            user=f"notify{i}",
            tag=tag,
            ts=now - timedelta(seconds=20 * i),
        )
        assert response.status_code == 200, response.text

    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    alerts = _alerts_for_tag(client, tag)
    assert len(alerts) == 1

    notifications = alerts[0]["notifications"]
    assert notifications, "a triggered alert must record a notification attempt"
    assert any(
        notification["channel"] == "webhook" and notification["status"] == "sent"
        for notification in notifications
    )


def test_alert_evidence_stays_within_tenant(client, api_key_demoa, api_key_demob):
    tag = f"evidence-{uuid.uuid4().hex}"
    src_ip = "198.51.100.210"
    now = datetime.now(timezone.utc)

    for tenant, api_key, offset in (
        ("demoa", api_key_demoa, 0),
        ("demob", api_key_demob, 100),
    ):
        for i in range(5):
            response = _ingest_failure(
                client,
                api_key,
                tenant=tenant,
                src_ip=src_ip,
                user=f"evidence{i}",
                tag=tag,
                ts=now + timedelta(seconds=offset + i),
            )
            assert response.status_code == 200, response.text

    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    alerts = client.get("/api/get-alerts").json()["alerts"]

    demoa_alerts = [
        alert
        for alert in alerts
        if alert["tenant"] == "demoa" and src_ip in (alert.get("dedupeKey") or "")
    ]
    demob_alerts = [
        alert
        for alert in alerts
        if alert["tenant"] == "demob" and src_ip in (alert.get("dedupeKey") or "")
    ]
    assert len(demoa_alerts) == 1
    assert len(demob_alerts) == 1
    assert demoa_alerts[0]["count"] == 5
    assert demob_alerts[0]["count"] == 5

    demoa_ids = set(demoa_alerts[0]["eventIds"])
    demob_ids = set(demob_alerts[0]["eventIds"])
    assert len(demoa_ids) == 5
    assert len(demob_ids) == 5
    assert demoa_ids.isdisjoint(demob_ids)

    async def _tenants_by_event_id() -> dict[str, str]:
        async with async_session_maker() as session:
            rows = (
                await session.execute(
                    select(Event.id, Event.tenant).where(
                        Event.id.in_(demoa_ids | demob_ids)
                    )
                )
            ).all()
            return {event_id: tenant for event_id, tenant in rows}

    tenants_by_id = asyncio.run(_tenants_by_event_id())
    assert set(tenants_by_id) == demoa_ids | demob_ids
    assert all(tenants_by_id[event_id] == "demoa" for event_id in demoa_ids)
    assert all(tenants_by_id[event_id] == "demob" for event_id in demob_ids)


def test_rule_validation_and_viewer_boundary(viewer_a_client):
    payload = {
        "name": "Consolidated viewer rule",
        "tenant": "demoa",
        "conditions": [{"type": "event_type", "value": "viewer_probe"}],
    }
    response = viewer_a_client.post("/api/create-alertRule", json=payload)
    assert response.status_code == 403, response.text

    login(viewer_a_client, ADMIN_EMAIL, ADMIN_PASSWORD)

    response = viewer_a_client.post(
        "/api/create-alertRule",
        json={
            "name": "Invalid condition rule",
            "tenant": "demoa",
            "conditions": [{"type": "unknown_condition_type", "threshold": 5}],
        },
    )
    assert response.status_code == 422, response.text

    response = viewer_a_client.post(
        "/api/create-alertRule",
        json={
            "name": f"Valid rule {uuid.uuid4().hex[:8]}",
            "tenant": "demob",
            "conditions": [{"type": "event_type", "value": "rotation_probe"}],
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["createdRule"]["tenant"] == "demob"
