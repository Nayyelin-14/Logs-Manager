"""End-to-end HTTP route tests against the test database.

Note: login returns cookies (no access_token in the JSON body), so every
authenticated call reuses the same TestClient session.
"""

import time
import uuid

from app.core.config import get_settings


def _login(client, email: str, password: str):
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"login failed: {res.status_code} {res.text}"
    return res


def test_viewer_cannot_see_other_tenant(client):
    """ViewerA should never see demoB events."""
    _login(client, "viewerA@demo.local", "ViewerA123!")

    search_res = client.get(
        "/api/get-logs", params={"tenant": "demoA", "limit": "100"}
    )
    assert search_res.status_code == 200, f"get-logs failed: {search_res.text}"
    for event in search_res.json().get("logs", []):
        assert event.get("tenant") != "demoB", f"ViewerA saw demoB event: {event.get('id')}"

    dash_res = client.get("/api/dashboard")
    assert dash_res.status_code == 200, f"dashboard failed: {dash_res.text}"

    alerts_res = client.get("/api/get-alerts")
    assert alerts_res.status_code == 200, f"alerts failed: {alerts_res.text}"

    # Explicitly requesting another tenant must not leak data
    search_res2 = client.get(
        "/api/get-logs", params={"tenant": "demoB", "limit": "100"}
    )
    demoB_events = [
        e for e in search_res2.json().get("logs", []) if e.get("tenant") == "demoB"
    ]
    assert len(demoB_events) == 0, f"ViewerA saw {len(demoB_events)} demoB events"


def test_six_ad_4625_failures_create_one_alert(client):
    """6 failed logins from the same IP create exactly one alert."""
    api_key = get_settings().INGEST_API_KEY
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}

    ip = f"198.51.100.{uuid.uuid4().int % 250 + 1}"
    base_time = time.time()
    alert_ids = set()
    for i in range(6):
        event = {
            "source": "ad",
            "event_type": "LogonFailed",
            "user": f"eve_{i}",
            "ip": ip,
            "src_ip": ip,
            "reason": "wrong_password",
            "status": "Failure",
            "action": "LOGIN",
            "@timestamp": base_time + i * 10,
        }
        resp = client.post("/api/ingest", headers=headers, json=event)
        assert resp.status_code == 200, f"ingest {i} failed: {resp.status_code} {resp.text}"
        for alert in resp.json().get("alerts", []):
            alert_ids.add(alert["id"])

    # The threshold rule must fire exactly once for this source IP
    assert len(alert_ids) == 1, f"expected 1 alert from ingest responses, got {alert_ids}"

    _login(client, "admin@demo.local", "Admin123!")
    alerts_res = client.get("/api/get-alerts", params={"limit": 100})
    assert alerts_res.status_code == 200, f"alerts failed: {alerts_res.text}"
    alerts = alerts_res.json().get("alerts", [])

    matching = [a for a in alerts if a.get("id") in alert_ids]
    assert len(matching) == 1, f"created alert missing from listing: {alert_ids}"
    alert = matching[0]
    assert "id" in alert and "title" in alert and "severity" in alert


def test_firewall_events_have_expected_fields(client):
    """Firewall events returned by search carry normalized fields."""
    _login(client, "admin@demo.local", "Admin123!")

    search_res = client.get(
        "/api/get-logs", params={"source": "FIREWALL", "limit": "5"}
    )
    assert search_res.status_code == 200, f"get-logs failed: {search_res.text}"
    firewall_events = search_res.json().get("logs", [])
    assert firewall_events, "expected at least one firewall event"
    for event in firewall_events:
        assert event.get("source") == "FIREWALL"
        assert event.get("eventType") or event.get("event_type")
        assert event.get("severity") is not None
        assert isinstance(event.get("raw"), dict)
