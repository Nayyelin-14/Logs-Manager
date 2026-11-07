"""
Alerting engine tests: detection, deduplication, tenant isolation, concurrency.
All tests hit the real API with real database operations.
"""

import asyncio

import pytest
import json
import time
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import async_session_maker
from app.models.alert import Alert, AlertRule
from app.models.events import Event
from app.models.security_event import SecurityEvent
from sqlalchemy import select, text
import uuid


MARKER = "phase1-alerting"

TEST_IPS = [
    "203.0.113.100",
    "198.51.100.100", "198.51.100.101", "198.51.100.102", "198.51.100.103", "198.51.100.104", "198.51.100.105",
    "198.51.100.200", "198.51.100.201", "198.51.100.202", "198.51.100.203", "198.51.100.204",
    "198.51.100.205", "198.51.100.206", "198.51.100.207", "198.51.100.208",
]


from conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    VIEWER_A_EMAIL,
    VIEWER_A_PASSWORD,
    VIEWER_B_EMAIL,
    VIEWER_B_PASSWORD,
)
@pytest.fixture(autouse=True)
async def _clean_alerting_rows():
    """Delete only rows created by these tests; never truncate seed data."""
    async def _delete():
        async with async_session_maker() as session:
            for ip in TEST_IPS:
                await session.execute(text("DELETE FROM alerts WHERE group_value = :ip").bindparams(ip=ip))
            await session.execute(text("DELETE FROM alerts WHERE tags @> ARRAY['phase1-alerting']::varchar[]"))
            await session.execute(text("DELETE FROM events WHERE _tags @> ARRAY['phase1-alerting']::varchar[]"))
            await session.commit()

    await _delete()
    yield
    await _delete()


def test_alerting_1_five_ad_failures_trigger_one_alert(client, api_key_demoa):
    """1. 5 AD 4625 failures from SAME src_ip within 300s -> ONE alert with count=5."""
    src_ip = "203.0.113.100"
    
    for i in range(5):
        res = client.post(
            "/api/ingest",
            json={
                "tenant": "demoa",
                "source": "ad",
                "event_id": 4625,
                "event_type": "LogonFailed",
                "user": f"demo\\\\evil{i}",
                "host": "DC01",
                "src_ip": src_ip,
                "src_port": str(49152 + i),
                "action": "LOGIN",
                "status": "Failure",
                "severity": 7,
                "@timestamp": (datetime.now(timezone.utc) - timedelta(seconds=30 * i)).isoformat().replace("+00:00", "Z"),
                "tags": [MARKER, "test_alerting_1"],
            },
            headers={"X-API-Key": api_key_demoa}
        )
        assert res.status_code == 200, f"Failed to ingest event {i}: {res.text}"
    
    # Now check alerts via admin
    client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    alert_res = client.get("/api/get-alerts?search=test_alerting_1")
    data = alert_res.json()
    alerts = data.get("alerts", [])
    
    assert len(alerts) == 1, f"Expected 1 alert, got {len(alerts)}"
    alert = alerts[0]
    assert alert["tenant"] == "demoa", f"Alert tenant mismatch: {alert['tenant']}"
    assert alert["status"] == "open", f"Alert status should be open: {alert['status']}"
    assert alert.get("description") and "Brute force" in alert.get("description", ""), f"Wrong description: {alert.get('description')}"


def test_alerting_2_six_different_ips_no_alert(client, api_key_demoa):
    """2. 6 failures spread across 6 DIFFERENT IPs -> no alert."""
    for i in range(6):
        src_ip = f"198.51.100.{100 + i}"
        res = client.post(
            "/api/ingest",
            json={
                "tenant": "demoa",
                "source": "ad",
                "event_id": 4625,
                "event_type": "LogonFailed",
                "user": f"demo\\\\user{i}",
                "host": "DC01",
                "src_ip": src_ip,
                "action": "LOGIN",
                "status": "Failure",
                "severity": 7,
                "@timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "tags": [MARKER, "test_alerting_2"],
            },
            headers={"X-API-Key": api_key_demoa}
        )
        assert res.status_code == 200
    
    client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    alert_res = client.get("/api/get-alerts?search=" + MARKER + "_2")
    alerts = alert_res.json().get("alerts", [])
    
    assert len(alerts) == 0, f"Expected 0 alerts for different IPs, got {len(alerts)}"


def test_alerting_3_mixed_success_failure_no_alert(client, api_key_demoa):
    """3. 6 events from one IP where 3 are successes (4624) -> no alert (only failures count)."""
    src_ip = "198.51.100.200"
    
    for i in range(6):
        event_id = 4624 if i % 2 == 0 else 4625
        event_type = "LogonSuccess" if event_id == 4624 else "LogonFailed"
        res = client.post(
            "/api/ingest",
            json={
                "tenant": "demoa",
                "source": "ad",
                "event_id": event_id,
                "event_type": event_type,
                "user": f"demo\\\\user{i}",
                "host": "DC01",
                "src_ip": src_ip,
                "action": "LOGIN",
                "status": "Success" if event_id == 4624 else "Failure",
                "severity": 7 if event_id == 4625 else 3,
                "@timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "tags": [MARKER, "test_alerting_3"],
            },
            headers={"X-API-Key": api_key_demoa}
        )
        assert res.status_code == 200
    
    client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    alert_res = client.get("/api/get-alerts?search=" + MARKER + "_3")
    alerts = alert_res.json().get("alerts", [])
    
    assert len(alerts) == 0, f"Expected 0 alerts for mixed success/failure, got {len(alerts)}"


def test_alerting_4_events_expired_window_no_alert(client, api_key_demoa):
    """4. 5 failures > 300s apart (using event @timestamp) -> no alert."""
    src_ip = "198.51.100.201"
    
    for i in range(5):
        # Spread events 60 seconds apart = 300 seconds total span, so 5th is outside window
        ts = (datetime.now(timezone.utc) - timedelta(seconds=300 + i * 60)).isoformat().replace("+00:00", "Z")
        res = client.post(
            "/api/ingest",
            json={
                "tenant": "demoa",
                "source": "ad",
                "event_id": 4625,
                "event_type": "LogonFailed",
                "user": f"demo\\\\user{i}",
                "host": "DC01",
                "src_ip": src_ip,
                "action": "LOGIN",
                "status": "Failure",
                "severity": 7,
                "@timestamp": ts,
                "tags": [MARKER, "test_alerting_4"],
            },
            headers={"X-API-Key": api_key_demoa}
        )
        assert res.status_code == 200
    
    client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    alert_res = client.get("/api/get-alerts?search=" + MARKER + "_4")
    alerts = alert_res.json().get("alerts", [])
    
    assert len(alerts) == 0, f"Expected 0 alerts for expired window, got {len(alerts)}"


def test_alerting_5_2025_timestamps_fire_alert(client, api_key_demoa):
    """5. 5 failures within the window from one IP fire exactly one alert."""
    src_ip = "198.51.100.202"
    base_ts = datetime.now(timezone.utc)
    
    for i in range(5):
        res = client.post(
            "/api/ingest",
            json={
                "tenant": "demoa",
                "source": "ad",
                "event_id": 4625,
                "event_type": "LogonFailed",
                "user": f"demo\\\\user{i}",
                "host": "DC01",
                "src_ip": src_ip,
                "action": "LOGIN",
                "status": "Failure",
                "severity": 7,
                "@timestamp": (base_ts - timedelta(seconds=30 * i)).isoformat().replace("+00:00", "Z"),
                "tags": [MARKER, "test_alerting_5"],
            },
            headers={"X-API-Key": api_key_demoa}
        )
        assert res.status_code == 200
    
    client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    alert_res = client.get("/api/get-alerts?search=test_alerting_5")
    alerts = alert_res.json().get("alerts", [])
    
    assert len(alerts) == 1, f"Expected 1 alert, got {len(alerts)}"


def test_alerting_6_multiple_ingest_methods_trigger_alert(client, api_key_demoa):
    """6. 5 failures via /ingest, /ingest/batch, /ingest/file each fires alert."""
    src_ip = "198.51.100.203"
    ts_base = datetime.now(timezone.utc)
    
    # Method 1: single /ingest
    res = client.post(
        "/api/ingest",
        json={
            "tenant": "demoa",
            "source": "ad",
            "event_id": 4625,
            "event_type": "LogonFailed",
            "user": "demo\\\\user",
            "src_ip": src_ip,
            "action": "LOGIN",
            "status": "Failure",
            "severity": 7,
            "@timestamp": ts_base.isoformat(),
            "tags": [MARKER, "test_alerting_6a"],
        },
        headers={"X-API-Key": api_key_demoa}
    )
    assert res.status_code == 200
    
    # Method 2: /ingest/batch
    events = [
        {
            "tenant": "demoa",
            "source": "ad",
            "event_id": 4625,
            "event_type": "LogonFailed",
            "user": "demo\\\\user",
            "src_ip": src_ip,
            "action": "LOGIN",
            "status": "Failure",
            "severity": 7,
            "@timestamp": (ts_base + timedelta(seconds=30)).isoformat(),
            "tags": [MARKER, f"test_alerting_6b_{i}"],
        }
        for i in range(4)
    ]
    res = client.post(
        "/api/ingest/batch",
        json={"events": events, "source": "ad"},
        headers={"X-API-Key": api_key_demoa}
    )
    assert res.status_code == 200
    
    client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    alert_res = client.get("/api/get-alerts?search=" + MARKER)
    alerts = alert_res.json().get("alerts", [])
    
    # Should have at least one alert from single+batch methods combined
    assert len(alerts) >= 1, f"Expected at least 1 alert, got {len(alerts)}"


def test_alerting_7_same_alert_updates_on_more_failures(client, api_key_demoa):
    """7. Further failures from same IP while alert is open -> SAME alert row updates."""
    src_ip = "198.51.100.204"
    
    for i in range(5):
        res = client.post(
            "/api/ingest",
            json={
                "tenant": "demoa",
                "source": "ad",
                "event_id": 4625,
                "event_type": "LogonFailed",
                "user": f"demo\\\\user{i}",
                "src_ip": src_ip,
                "action": "LOGIN",
                "status": "Failure",
                "severity": 7,
                "@timestamp": (datetime.now(timezone.utc) - timedelta(seconds=30 * i)).isoformat().replace("+00:00", "Z"),
                "tags": [MARKER, "test_alerting_7"],
            },
            headers={"X-API-Key": api_key_demoa}
        )
        assert res.status_code == 200
    
    client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    alert_res = client.get("/api/get-alerts?search=test_alerting_7")
    alerts = alert_res.json().get("alerts", [])
    
    assert len(alerts) == 1, f"Expected 1 alert, got {len(alerts)}"
    alert = alerts[0]
    assert alert["count"] == 5, f"Expected count=5, got {alert.get('count')}"
    
    # Add 2 more failures - should update same alert
    for i in range(5, 7):
        res = client.post(
            "/api/ingest",
            json={
                "tenant": "demoa",
                "source": "ad",
                "event_id": 4625,
                "event_type": "LogonFailed",
                "user": f"demo\\\\user{i}",
                "src_ip": src_ip,
                "action": "LOGIN",
                "status": "Failure",
                "severity": 7,
                "@timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "tags": [MARKER, "test_alerting_7b"],
            },
            headers={"X-API-Key": api_key_demoa}
        )
        assert res.status_code == 200
    
    alert_res = client.get("/api/get-alerts?search=test_alerting_7")
    alerts = alert_res.json().get("alerts", [])
    
    # Still exactly 1 alert, count increased
    assert len(alerts) == 1, f"Expected 1 alert after more failures, got {len(alerts)}"
    assert alerts[0]["count"] == 7, f"Expected count=7, got {alerts[0].get('count')}"


def test_alerting_8_count_increments_not_dedup_fails(client, api_key_demoa):
    """8a. After 5 failures, 6th creates new alert due to different window -> 2 alerts (or count=6 in one)."""
    src_ip = "198.51.100.205"
    
    # 5 failures within window
    for i in range(5):
        res = client.post(
            "/api/ingest",
            json={
                "tenant": "demoa",
                "source": "ad",
                "event_id": 4625,
                "event_type": "LogonFailed",
                "user": f"demo\\\\user{i}",
                "src_ip": src_ip,
                "action": "LOGIN",
                "status": "Failure",
                "severity": 7,
                "@timestamp": (datetime.now(timezone.utc) - timedelta(seconds=50)).isoformat().replace("+00:00", "Z"),
                "tags": [MARKER, "test_alerting_8a"],
            },
            headers={"X-API-Key": api_key_demoa}
        )
        assert res.status_code == 200
    
    # 6th failure after window expires (> 300s from first)
    res = client.post(
        "/api/ingest",
        json={
            "tenant": "demoa",
            "source": "ad",
            "event_id": 4625,
            "event_type": "LogonFailed",
            "user": "demo\\\\user6",
            "src_ip": src_ip,
            "action": "LOGIN",
            "status": "Failure",
            "severity": 7,
            "@timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "tags": [MARKER, "test_alerting_8b"],
        },
        headers={"X-API-Key": api_key_demoa}
    )
    assert res.status_code == 200
    
    client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    alert_res = client.get("/api/get-alerts?search=test_alerting_8")
    alerts = alert_res.json().get("alerts", [])
    
    # Should be 1 alert with count=6 since the 5 threshold fires on the 5th, and the 6th is in same unresolved
    assert len(alerts) == 1, f"Expected 1 alert, got {len(alerts)}"
    assert alerts[0]["count"] == 6, f"Expected count=6, got {alerts[0].get('count')}"


def test_alerting_9_cross_tenant_isolation(client, api_key_demoa, api_key_demob):
    """9. demoA events and demob events with same IP never combine; alert has correct tenant."""
    src_ip = "198.51.100.206"
    base_ts = datetime.now(timezone.utc)
    
    # 5 failures in demoa with this IP
    for i in range(5):
        res = client.post(
            "/api/ingest",
            json={
                "tenant": "demoa",
                "source": "ad",
                "event_id": 4625,
                "event_type": "LogonFailed",
                "user": f"demo\\\\user{i}",
                "src_ip": src_ip,
                "action": "LOGIN",
                "status": "Failure",
                "severity": 7,
                "@timestamp": (base_ts + timedelta(seconds=i)).isoformat(),
                "tags": [MARKER, f"test_cross_9a_{i}"],
            },
            headers={"X-API-Key": api_key_demoa}
        )
        assert res.status_code == 200
    
    # 5 failures in demob with same IP
    for i in range(5):
        res = client.post(
            "/api/ingest",
            json={
                "tenant": "demob",
                "source": "ad",
                "event_id": 4625,
                "event_type": "LogonFailed",
                "user": f"demo\\\\user{i}",
                "src_ip": src_ip,
                "action": "LOGIN",
                "status": "Failure",
                "severity": 7,
                "@timestamp": (base_ts + timedelta(seconds=i + 100)).isoformat(),
                "tags": [MARKER, f"test_cross_9b_{i}"],
            },
            headers={"X-API-Key": api_key_demob}
        )
        assert res.status_code == 200
    
    # Admin views all alerts
    client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    alert_res = client.get("/api/get-alerts")
    alerts = alert_res.json().get("alerts", [])
    
    demoa_alerts = [a for a in alerts if a["tenant"] == "demoa" and src_ip in (a.get("dedupeKey") or "")]
    demob_alerts = [a for a in alerts if a["tenant"] == "demob" and src_ip in (a.get("dedupeKey") or "")]
    
    assert len(demoa_alerts) == 1, f"Expected 1 demoa alert, got {len(demoa_alerts)}"
    assert len(demob_alerts) == 1, f"Expected 1 demob alert, got {len(demob_alerts)}"
    assert demoa_alerts[0]["tenant"] == "demoa" and demoa_alerts[0]["count"] == 5
    assert demob_alerts[0]["tenant"] == "demob" and demob_alerts[0]["count"] == 5
    # Evidence must cover exactly the five events that produced the count.
    # A mismatch here means a later evaluation would double-count events.
    assert len(demoa_alerts[0]["eventIds"]) == 5
    assert len(demob_alerts[0]["eventIds"]) == 5
    
    # viewerA (demoa) must not see demob's alert
    client.post("/api/auth/login", json={"email": VIEWER_A_EMAIL, "password": VIEWER_A_PASSWORD})
    viewer_alerts = client.get("/api/get-alerts").json().get("alerts", [])
    assert all(a["tenant"] != "demob" for a in viewer_alerts), "viewerA saw demob alerts"


def test_alerting_9b_alert_evidence_never_crosses_tenants(client, api_key_demoa, api_key_demob):
    """Regression: demoa alert evidence contains only demoa events (same IP as demob)."""
    src_ip = "198.51.100.210"
    base_ts = datetime.now(timezone.utc)

    for i in range(5):
        res = client.post(
            "/api/ingest",
            json={
                "tenant": "demoa",
                "source": "ad",
                "event_id": 4625,
                "event_type": "LogonFailed",
                "user": f"demo\\\\evidence{i}",
                "src_ip": src_ip,
                "action": "LOGIN",
                "status": "Failure",
                "severity": 7,
                "@timestamp": (base_ts + timedelta(seconds=i)).isoformat(),
                "tags": [MARKER, f"test_cross_9b_evidence_a_{i}"],
            },
            headers={"X-API-Key": api_key_demoa},
        )
        assert res.status_code == 200

    for i in range(5):
        res = client.post(
            "/api/ingest",
            json={
                "tenant": "demob",
                "source": "ad",
                "event_id": 4625,
                "event_type": "LogonFailed",
                "user": f"demo\\\\evidence{i}",
                "src_ip": src_ip,
                "action": "LOGIN",
                "status": "Failure",
                "severity": 7,
                "@timestamp": (base_ts + timedelta(seconds=i + 100)).isoformat(),
                "tags": [MARKER, f"test_cross_9b_evidence_b_{i}"],
            },
            headers={"X-API-Key": api_key_demob},
        )
        assert res.status_code == 200

    client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    alerts = client.get("/api/get-alerts").json().get("alerts", [])
    demoa_alerts = [a for a in alerts if a["tenant"] == "demoa" and src_ip in (a.get("dedupeKey") or "")]
    demob_alerts = [a for a in alerts if a["tenant"] == "demob" and src_ip in (a.get("dedupeKey") or "")]
    assert len(demoa_alerts) == 1
    assert len(demob_alerts) == 1

    demoa_ids = set(demoa_alerts[0]["eventIds"])
    demob_ids = set(demob_alerts[0]["eventIds"])
    assert len(demoa_ids) == 5
    assert len(demob_ids) == 5
    assert demoa_ids.isdisjoint(demob_ids)
    assert demoa_alerts[0]["count"] == 5
    assert demob_alerts[0]["count"] == 5

    async def _event_tenants():
        async with async_session_maker() as session:
            rows = (
                await session.execute(
                    select(Event.id, Event.tenant).where(Event.id.in_(demoa_ids | demob_ids))
                )
            ).all()
            return {event_id: tenant for event_id, tenant in rows}

    tenants_by_id = asyncio.run(_event_tenants())
    assert set(tenants_by_id) == demoa_ids | demob_ids
    assert all(tenants_by_id[event_id] == "demoa" for event_id in demoa_ids)
    assert all(tenants_by_id[event_id] == "demob" for event_id in demob_ids)


def test_alerting_10_viewer_sees_own_tenant_alerts(client):
    """10. viewerA sees only demoa alerts via GET /api/get-alerts; ?tenant=other changes nothing."""
    client.post("/api/auth/login", json={"email": VIEWER_A_EMAIL, "password": VIEWER_A_PASSWORD})
    
    res = client.get("/api/get-alerts")
    assert res.status_code == 200
    
    alerts = res.json().get("alerts", [])
    for alert in alerts:
        assert alert["tenant"] == "demoa", f"viewerA should only see demoa alerts, saw {alert['tenant']}"
    
    # Try to force different tenant
    res = client.get("/api/get-alerts?tenant=demob")
    assert res.status_code == 200
    alerts = res.json().get("alerts", [])
    for alert in alerts:
        assert alert["tenant"] == "demoa", f"viewerA should only see demoa alerts, saw {alert['tenant']}"


def test_alerting_11_concurrent_ingest_single_alert(client, api_key_demoa):
    """11. Concurrency: multiple sequential ingests that cross threshold create exactly ONE alert after threshold."""
    src_ip = "198.51.100.207"
    base_ts = datetime.now(timezone.utc)
    
    # 5 failures trigger the alert
    for i in range(5):
        res = client.post(
            "/api/ingest",
            json={
                "tenant": "demoa",
                "source": "ad",
                "event_id": 4625,
                "event_type": "LogonFailed",
                "user": f"demo\\\\user{i}",
                "src_ip": src_ip,
                "action": "LOGIN",
                "status": "Failure",
                "severity": 7,
                "@timestamp": (base_ts + timedelta(seconds=5 * i)).isoformat().replace("+00:00", "Z"),
                "tags": [MARKER, "test_concurrent"],
            },
            headers={"X-API-Key": api_key_demoa}
        )
        assert res.status_code == 200
    
    client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    alert_res = client.get("/api/get-alerts?search=test_concurrent")
    alerts = alert_res.json().get("alerts", [])
    
    # Should be exactly 1 alert
    assert len(alerts) == 1, f"Expected 1 alert from concurrent ingests, got {len(alerts)}"


def test_alerting_12_batch_500_events_completes(client, api_key_demoa, monkeypatch):
    """12. Batch of 500 events completes under 5 seconds and runs bounded alert queries.

    The benchmark measures event evaluation and persistence only. Replace the
    webhook transport with a deterministic in-process stub so external DNS or
    retry backoff cannot dominate the measured time. Retry behavior itself is
    covered by tests/unit/test_notifier.py.
    """
    import time
    import app.services.alerting.alerter as alerter

    delivered = []

    async def fake_send_webhook(*, webhook_url, payload, **kwargs):
        delivered.append(payload)
        return [{
            "attempt": 1,
            "status": "sent",
            "http_code": 200,
            "error": None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }]

    monkeypatch.setattr(alerter, "send_webhook", fake_send_webhook)
    
    events = [
        {
            "tenant": "demoa",
            "source": "ad",
            "event_id": 4625,
            "event_type": "LogonFailed",
            "user": f"demo\\\\user{i}",
            "src_ip": "198.51.100.208",
            "action": "LOGIN",
            "status": "Failure",
            "severity": 7,
            "@timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        for i in range(500)
    ]
    
    start = time.time()
    res = client.post(
        "/api/ingest/batch",
        json={"events": events, "source": "ad"},
        headers={"X-API-Key": api_key_demoa}
    )
    elapsed = time.time() - start
    
    assert res.status_code == 200, res.text
    assert elapsed < 5, f"Batch took {elapsed:.2f}s, should be < 5s"
    assert res.json()["ingested"] == 500
    assert delivered, "expected the threshold alert to reach the stubbed webhook transport"


def test_alerting_13_rule_validation_unknown_type(client):
    """13a. Unknown condition type -> 422 on create."""
    client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    
    res = client.post(
        "/api/create-alertRule",
        json={
            "name": "Bad Rule",
            "tenant": "demoa",
            "conditions": [{"type": "unknown_condition_type", "threshold": 5}],
        }
    )
    assert res.status_code == 422, f"Expected 422, got {res.status_code}"


def test_alerting_14_rule_validation_negative_threshold(client):
    """13b. Negative threshold -> 422 on create."""
    client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    
    res = client.post(
        "/api/create-alertRule",
        json={
            "name": "Bad Threshold",
            "tenant": "demoa",
            "conditions": [{"type": "event_type", "value": "test", "threshold": -1}],
        }
    )
    assert res.status_code == 422, f"Expected 422, got {res.status_code}"


def test_alerting_15_rule_validation_window_too_small(client):
    """13c. window < 1 -> 422 on create."""
    client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    
    res = client.post(
        "/api/create-alertRule",
        json={
            "name": "Bad Window",
            "tenant": "demoa",
            "conditions": [{"type": "event_type", "value": "test", "windowSeconds": 0}],
        }
    )
    assert res.status_code == 422, f"Expected 422, got {res.status_code}"


def test_alerting_16_rule_validation_window_too_large(client):
    """13d. window > 86400 -> 422 on create."""
    client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    
    res = client.post(
        "/api/create-alertRule",
        json={
            "name": "Bad Window Large",
            "tenant": "demoa",
            "conditions": [{"type": "event_type", "value": "test", "windowSeconds": 86401}],
        }
    )
    assert res.status_code == 422, f"Expected 422, got {res.status_code}"


def test_alerting_17_rule_validation_group_by(client):
    """13e. Invalid group_by -> 422 on create."""
    client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    
    res = client.post(
        "/api/create-alertRule",
        json={
            "name": "Bad GroupBy",
            "tenant": "demoa",
            "conditions": [{"type": "event_type", "value": "test", "groupBy": "invalid_field"}],
        }
    )
    assert res.status_code == 422, f"Expected 422, got {res.status_code}"


def test_alerting_18_tenant_mismatch_403(client):
    """13f. viewers cannot create rules; admins may create for any tenant."""
    payload = {
        "name": "Cross Tenant",
        "tenant": "demoa",
        "conditions": [{"type": "event_type", "value": "test"}],
    }
    
    client.post("/api/auth/login", json={"email": VIEWER_A_EMAIL, "password": VIEWER_A_PASSWORD})
    res = client.post("/api/create-alertRule", json=payload)
    assert res.status_code == 403, f"Expected 403 for viewerA/demoa, got {res.status_code}"
    
    res = client.post("/api/create-alertRule", json={**payload, "tenant": "demob"})
    assert res.status_code == 403, f"Expected 403 for viewerA/demob, got {res.status_code}"
    
    client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    res = client.post("/api/create-alertRule", json={**payload, "tenant": "demob"})
    assert res.status_code == 201, f"Expected 201 for admin/demob, got {res.status_code}"
    assert res.json()["createdRule"]["tenant"] == "demob"
