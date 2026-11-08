import time
import uuid

from app.core.config import get_settings


from conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    VIEWER_A_EMAIL,
    VIEWER_A_PASSWORD,
    VIEWER_B_EMAIL,
    VIEWER_B_PASSWORD,
)


def _login(client, email: str, password: str):
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"login failed: {res.status_code} {res.text}"
    return res


def test_viewer_cannot_see_other_tenant(client):
    _login(client, VIEWER_A_EMAIL, VIEWER_A_PASSWORD)

    search_res = client.get(
        "/api/get-logs", params={"tenant": "demoa", "limit": "100"}
    )
    assert search_res.status_code == 200, f"get-logs failed: {search_res.text}"
    for event in search_res.json().get("logs", []):
        assert event.get("tenant") != "demob", f"ViewerA saw demob event: {event.get('id')}"

    dash_res = client.get("/api/dashboard")
    assert dash_res.status_code == 200, f"dashboard failed: {dash_res.text}"

    alerts_res = client.get("/api/get-alerts")
    assert alerts_res.status_code == 200, f"alerts failed: {alerts_res.text}"


    search_res2 = client.get(
        "/api/get-logs", params={"tenant": "demob", "limit": "100"}
    )
    demob_events = [
        e for e in search_res2.json().get("logs", []) if e.get("tenant") == "demob"
    ]
    assert len(demob_events) == 0, f"ViewerA saw {len(demob_events)} demob events"


def test_six_ad_4625_failures_create_one_alert(client, api_key_demoa):
    from app.core.database import async_session_maker
    from app.models.tenant import Tenant
    import asyncio

    headers = {"X-API-Key": api_key_demoa, "Content-Type": "application/json"}


    ip = f"192.0.2.{uuid.uuid4().int % 250 + 1}"
    base_time = time.time()
    alert_ids = set()
    for i in range(6):
        event = {
            "source": "ad",
            "event_type": "LogonFailed",
            "event_id": 4625,
            "user": f"eve_{i}",
            "ip": ip,
            "src_ip": ip,
            "reason": "wrong_password",
            "status": "Failure",
            "action": "LOGIN",
            "severity": 7,
            "@timestamp": base_time + i * 10,
        }
        resp = client.post("/api/ingest", headers=headers, json=event)
        assert resp.status_code == 200, f"ingest {i} failed: {resp.status_code} {resp.text}"
        for alert in resp.json().get("alerts", []):


            if ip in (alert.get("dedupe_key") or ""):
                alert_ids.add(alert["id"])


    assert len(alert_ids) == 1, f"expected 1 alert from ingest responses, got {alert_ids}"

    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    alerts_res = client.get("/api/get-alerts", params={"limit": 100})
    assert alerts_res.status_code == 200, f"alerts failed: {alerts_res.text}"
    alerts = alerts_res.json().get("alerts", [])

    matching = [a for a in alerts if a.get("id") in alert_ids]
    assert len(matching) == 1, f"created alert missing from listing: {alert_ids}"
    alert = matching[0]
    assert "id" in alert and "title" in alert and "severity" in alert


def test_firewall_events_have_expected_fields(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)

    search_res = client.get(
        "/api/get-logs", params={"source": "firewall", "limit": "5"}
    )
    assert search_res.status_code == 200, f"get-logs failed: {search_res.text}"
    firewall_events = search_res.json().get("logs", [])
    assert firewall_events, "expected at least one firewall event"
    for event in firewall_events:
        assert event.get("source") == "firewall"
        assert event.get("eventType") or event.get("event_type")
        assert event.get("severity") is not None
        assert isinstance(event.get("raw"), dict)


def test_feature_flag_off_returns_404(client):
    res = client.get("/features/test-flagged")
    assert res.status_code == 404, f"Expected 404, got {res.status_code}"


def test_feature_flag_on_returns_200(client, feature_test_flag_enabled):
    res = client.get("/features/test-flagged")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
