import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import async_session_maker
from app.models.events import Event
from app.models.alert import Alert, AlertRule
from app.models.enums import Source, Action
from sqlalchemy import select, text
import uuid
import asyncio
from datetime import datetime, timezone


SEED_DATA = {}

ISO_LOG_DEMOA = "iso_log_demoa_1"
ISO_LOG_DEMOB = "iso_log_demob_1"
ISO_LOG_ADMIN_DELETE = "iso_log_admin_delete"
ISO_RULE_DEMOA = "iso_rule_demoa"
ISO_RULE_DEMOB = "iso_rule_demob"
ISO_ALERT_DEMOA = "iso_alert_demoa"
ISO_ALERT_DEMOB = "iso_alert_demob"


async def _seed_isolation_data():
    async with async_session_maker() as session:
        demoa_ts = datetime(2025, 8, 20, 7, 20, 0, tzinfo=timezone.utc)
        demob_ts = datetime(2025, 8, 20, 8, 20, 0, tzinfo=timezone.utc)

        log_a = await session.execute(select(Event).where(Event.id == ISO_LOG_DEMOA))
        if not log_a.scalar_one_or_none():
            log_a = Event(
                id=ISO_LOG_DEMOA,
                ts=demoa_ts,
                tenant="demoa",
                source=Source.AD,
                event_type="LogonFailed",
                action=Action.LOGIN,
                severity=7,
                user_name="demo\\eve",
                host="DC01",
                src_ip="203.0.113.77",
                raw={"_seed": True},
                _tags=["seed"],
            )
            session.add(log_a)

        log_b = await session.execute(select(Event).where(Event.id == ISO_LOG_DEMOB))
        if not log_b.scalar_one_or_none():
            log_b = Event(
                id=ISO_LOG_DEMOB,
                ts=demob_ts,
                tenant="demob",
                source=Source.AWS,
                event_type="CreateUser",
                action=Action.CREATE,
                severity=6,
                user_name="admin",
                host="EC2",
                raw={"_seed": True},
                _tags=["seed"],
            )
            session.add(log_b)

        log_admin_delete = await session.execute(select(Event).where(Event.id == ISO_LOG_ADMIN_DELETE))
        if not log_admin_delete.scalar_one_or_none():
            log_admin_delete = Event(
                id=ISO_LOG_ADMIN_DELETE,
                ts=demob_ts,
                tenant="demoa",
                source=Source.FIREWALL,
                event_type="traffic_blocked",
                action=Action.DENY,
                severity=4,
                user_name="external",
                host="FW01",
                src_ip="10.0.1.10",
                raw={"_seed": True, "_admin_delete_test": True},
                _tags=["seed"],
            )
            session.add(log_admin_delete)

        rule_a = await session.execute(select(AlertRule).where(AlertRule.id == ISO_RULE_DEMOA))
        if not rule_a.scalar_one_or_none():
            rule_a = AlertRule(
                id=ISO_RULE_DEMOA,
                name="Test Rule A",
                description="Test",
                tenant="demoa",
                enabled=True,
                severity="high",
                conditions=[{"type": "event_type"}],
            )
            session.add(rule_a)

        alert_a = await session.execute(select(Alert).where(Alert.id == ISO_ALERT_DEMOA))
        if not alert_a.scalar_one_or_none():
            alert_a = Alert(
                id=ISO_ALERT_DEMOA,
                rule_id=ISO_RULE_DEMOA,
                tenant="demoa",
                description="Test alert A",
                event_ids=[ISO_LOG_DEMOA],
                severity="high",
                status="open",
                title="Alert A",
                dedupe_key="test-a",
                group_key="test-a",
                group_value="test",
                count=1,
                first_seen=demoa_ts,
                last_seen=demoa_ts,
            )
            session.add(alert_a)

        rule_b = await session.execute(select(AlertRule).where(AlertRule.id == ISO_RULE_DEMOB))
        if not rule_b.scalar_one_or_none():
            rule_b = AlertRule(
                id=ISO_RULE_DEMOB,
                name="Test Rule B",
                description="Test",
                tenant="demob",
                enabled=True,
                severity="high",
                conditions=[{"type": "event_type"}],
            )
            session.add(rule_b)

        alert_b = await session.execute(select(Alert).where(Alert.id == ISO_ALERT_DEMOB))
        if not alert_b.scalar_one_or_none():
            alert_b = Alert(
                id=ISO_ALERT_DEMOB,
                rule_id=ISO_RULE_DEMOB,
                tenant="demob",
                description="Test alert B",
                event_ids=[ISO_LOG_DEMOB],
                severity="high",
                status="open",
                title="Alert B",
                dedupe_key="test-b",
                group_key="test-b",
                group_value="test",
                count=1,
                first_seen=demob_ts,
                last_seen=demob_ts,
            )
            session.add(alert_b)

        await session.commit()

        SEED_DATA["demoA_log_id"] = ISO_LOG_DEMOA
        SEED_DATA["demoB_log_id"] = ISO_LOG_DEMOB
        SEED_DATA["demoA_admin_delete_log_id"] = ISO_LOG_ADMIN_DELETE
        SEED_DATA["demoA_alert_id"] = ISO_ALERT_DEMOA
        SEED_DATA["demoB_alert_id"] = ISO_ALERT_DEMOB
        SEED_DATA["demoA_rule_id"] = ISO_RULE_DEMOA
        SEED_DATA["demoB_rule_id"] = ISO_RULE_DEMOB


from conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    VIEWER_A_EMAIL,
    VIEWER_A_PASSWORD,
    VIEWER_B_EMAIL,
    VIEWER_B_PASSWORD,
)

def _login(test_client, email: str, password: str):
    """Log in and attach the CSRF token the browser would read from its cookie."""
    response = test_client.post("/api/auth/login", json={"email": email, "password": password})
    token = response.cookies.get("XSRF-TOKEN")
    if token:
        test_client.headers["X-XSRF-TOKEN"] = token
    return response


@pytest.fixture(scope="module", autouse=True)
def isolation_seed(test_database):
    asyncio.run(_seed_isolation_data())
    yield


@pytest.fixture(scope="session")
def test_client():
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="session")
def test_data():
    return {
        "admin_email": ADMIN_EMAIL,
        "admin_password": ADMIN_PASSWORD,
        "viewer_a_email": VIEWER_A_EMAIL,
        "viewer_a_password": VIEWER_A_PASSWORD,
        "viewer_b_email": VIEWER_B_EMAIL,
        "viewer_b_password": VIEWER_B_PASSWORD,
    }




def test_1_viewer_b_get_logs_forced_to_own_tenant(test_client, test_data):
    _login(test_client, test_data["viewer_b_email"], test_data["viewer_b_password"])

    response = test_client.get("/api/get-logs?tenant=demoa")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    data = response.json()
    logs = data.get("logs", [])
    assert len(logs) >= 1, f"Expected at least 1 row, got {len(logs)}"

    demo_a_logs = [l for l in logs if l.get("tenant") == "demoa"]
    assert len(demo_a_logs) == 0, f"VULNERABILITY: viewerB sees {len(demo_a_logs)} demoa logs"

    for log in logs:
        assert log.get("tenant") == "demob", f"VULNERABILITY: viewerB sees tenant={log.get('tenant')}"


def test_2_viewer_b_get_alerts_forced_to_own_tenant(test_client, test_data):
    _login(test_client, test_data["viewer_b_email"], test_data["viewer_b_password"])

    response = test_client.get("/api/get-alerts?tenant=demoa")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    data = response.json()
    alerts = data.get("alerts", [])
    assert len(alerts) >= 1, f"Expected at least 1 row, got {len(alerts)}"

    demo_a_alerts = [a for a in alerts if a.get("tenant") == "demoa"]
    assert len(demo_a_alerts) == 0, f"VULNERABILITY: viewerB sees {len(demo_a_alerts)} demoa alerts"

    for alert in alerts:
        assert alert.get("tenant") == "demob", f"VULNERABILITY: viewerB sees tenant={alert.get('tenant')}"


def test_3_viewer_b_dashboard_counts_demoB_only(test_client, test_data):
    _login(test_client, test_data["viewer_b_email"], test_data["viewer_b_password"])

    response = test_client.get("/api/dashboard?tenant=demoa")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    data = response.json()
    assert data.get("allLogs", 0) == 0, f"Expected allLogs=0 (demob only), got {data.get('allLogs')}"
    assert data.get("allAlerts", 0) == 0, f"Expected allAlerts=0 (demob only), got {data.get('allAlerts')}"


def test_4_viewer_b_patch_demoA_alert_403(test_client, test_data):
    _login(test_client, test_data["viewer_b_email"], test_data["viewer_b_password"])

    alert_id = SEED_DATA["demoA_alert_id"]
    response = test_client.patch(f"/api/alerts/{alert_id}", json={"status": "CLOSED"})
    assert response.status_code == 403, f"Expected 403, got {response.status_code} - VULNERABILITY: viewer can modify another tenant's alert"


def test_5_viewer_b_delete_demoA_log_403(test_client, test_data):
    _login(test_client, test_data["viewer_b_email"], test_data["viewer_b_password"])

    log_id = SEED_DATA["demoA_log_id"]
    response = test_client.delete(f"/api/delete-log/{log_id}")
    assert response.status_code == 403, f"Expected 403, got {response.status_code} - VULNERABILITY: viewer can delete another tenant's log"


def test_6_viewer_b_delete_demoB_log_403(test_client, test_data):
    _login(test_client, test_data["viewer_b_email"], test_data["viewer_b_password"])

    log_id = SEED_DATA["demoB_log_id"]
    response = test_client.delete(f"/api/delete-log/{log_id}")
    assert response.status_code == 403, f"Expected 403, got {response.status_code} - VULNERABILITY: viewer can delete own tenant's log"


def test_7_viewer_b_patch_demoB_alert_403(test_client, test_data):
    _login(test_client, test_data["viewer_b_email"], test_data["viewer_b_password"])

    alert_id = SEED_DATA["demoB_alert_id"]
    response = test_client.patch(f"/api/alerts/{alert_id}", json={"status": "CLOSED"})
    assert response.status_code == 403, f"Expected 403, got {response.status_code} - VULNERABILITY: viewer can modify own tenant's alert"


def test_8_viewer_cannot_access_admin_endpoints(test_client, test_data):
    _login(test_client, test_data["viewer_b_email"], test_data["viewer_b_password"])

    resp = test_client.get("/api/get-users")
    assert resp.status_code == 403, f"Expected 403 for viewer get-users, got {resp.status_code}"

    resp = test_client.get("/api/get-rules")
    assert resp.status_code == 403, f"Expected 403 for viewer get-rules, got {resp.status_code}"

    resp = test_client.post("/api/create-user", json={
        "username": "newuser",
        "email": "new@example.com",
        "tenant": "demob",
        "role": "VIEWER",
        "password": "Password123!"
    })
    assert resp.status_code == 403, f"Expected 403 for viewer create-user, got {resp.status_code}"

    resp = test_client.post("/api/create-alertRule", json={
        "name": "Evil Rule",
        "description": "Test",
        "tenant": "demob",
        "severity": "high",
        "conditions": {},
        "enabled": True,
    })
    assert resp.status_code == 403, f"Expected 403 for viewer create-alertRule, got {resp.status_code}"


def test_10_register_returns_404(test_client):
    test_client.cookies.clear()
    test_client.headers.pop("X-XSRF-TOKEN", None)
    response = test_client.post("/api/auth/register", json={
        "username": "testuser",
        "email": "test@example.com",
        "tenant": "test"
    })
    assert response.status_code == 404, f"Expected 404, got {response.status_code}"




def test_9_admin_patch_demoA_alert_200(test_client, test_data):
    _login(test_client, test_data["admin_email"], test_data["admin_password"])

    alert_id = SEED_DATA["demoA_alert_id"]
    response = test_client.patch(f"/api/alerts/{alert_id}", json={"status": "resolved"})
    assert response.status_code == 200, f"Expected 200, got {response.status_code} - endpoint may not work for admin"


def test_11_admin_delete_demoA_log_200(test_client, test_data):
    _login(test_client, test_data["admin_email"], test_data["admin_password"])

    log_id = SEED_DATA["demoA_admin_delete_log_id"]
    response = test_client.delete(f"/api/delete-log/{log_id}")
    assert response.status_code == 200, f"Expected 200, got {response.status_code} - admin delete may not work"


def test_12_admin_get_logs_all_tenants(test_client, test_data):
    _login(test_client, test_data["admin_email"], test_data["admin_password"])

    response = test_client.get("/api/get-logs")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    data = response.json()
    logs = data.get("logs", [])
    tenants = set(log.get("tenant") for log in logs if log.get("tenant"))
    assert "demoa" in tenants and "demob" in tenants, f"Expected both tenants, got {tenants}"




def test_22_admin_create_viewer_without_tenant_422(test_client, test_data):
    _login(test_client, test_data["admin_email"], test_data["admin_password"])

    response = test_client.post("/api/create-user", json={
        "username": "newviewer",
        "email": "newviewer@example.com",
        "tenant": "",
        "role": "VIEWER",
        "password": "Password123!"
    })
    assert response.status_code == 422, f"Expected 422 for VIEWER without tenant, got {response.status_code}"


def test_23_admin_create_admin_tenant_null(test_client, test_data):
    _login(test_client, test_data["admin_email"], test_data["admin_password"])

    response = test_client.get("/api/auth/auth-check")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    user_data = response.json().get("user", {})
    assert user_data.get("tenant") is None or user_data.get("tenant") == "", \
        f"Expected admin tenant NULL/empty, got {user_data.get('tenant')}"
    assert user_data.get("role") == "ADMIN", f"Expected role ADMIN, got {user_data.get('role')}"




def test_13_viewer_b_dashboard_tenants_only_demoB(test_client, test_data):
    _login(test_client, test_data["viewer_b_email"], test_data["viewer_b_password"])

    response = test_client.get("/api/dashboard")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    data = response.json()
    tenants_list = data.get("tenants", [])
    tenant_names = [t.get("tenant") for t in tenants_list]
    assert tenant_names == ["demob"], f"Expected [demob], got {tenant_names} - VULNERABILITY: viewerB dashboard shows other tenants"


def test_14_admin_dashboard_tenants_both(test_client, test_data):
    _login(test_client, test_data["admin_email"], test_data["admin_password"])

    response = test_client.get("/api/dashboard")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    data = response.json()
    tenants_list = data.get("tenants", [])
    tenant_names = [t.get("tenant") for t in tenants_list]
    assert "demoa" in tenant_names, f"Expected demoa in tenants, got {tenant_names}"
    assert "demob" in tenant_names, f"Expected demob in tenants, got {tenant_names}"


def test_15_viewer_b_get_all_data_demoB_only(test_client, test_data):
    _login(test_client, test_data["viewer_b_email"], test_data["viewer_b_password"])

    response = test_client.get("/api/get-all-data")
    assert response.status_code == 403, f"Expected 403, got {response.status_code}"


def test_16_viewer_b_get_all_data_tenant_param_403(test_client, test_data):
    _login(test_client, test_data["viewer_b_email"], test_data["viewer_b_password"])

    response = test_client.get("/api/get-all-data?tenant=demoA")
    assert response.status_code == 403, f"Expected 403, got {response.status_code}"


def test_17_viewer_b_get_logs_tenant_all_and_DemoA(test_client, test_data):
    _login(test_client, test_data["viewer_b_email"], test_data["viewer_b_password"])

    response = test_client.get("/api/get-logs?tenant=all")
    assert response.status_code == 200, f"Expected 200 for ?tenant=all, got {response.status_code}"
    data = response.json()
    logs = data.get("logs", [])
    for log in logs:
        assert log.get("tenant") == "demob", f"VULNERABILITY: viewerB with ?tenant=all sees tenant={log.get('tenant')}"

    response = test_client.get("/api/get-logs?tenant=DemoA")
    assert response.status_code == 200, f"Expected 200 for ?tenant=DemoA, got {response.status_code}"
    data = response.json()
    logs = data.get("logs", [])
    for log in logs:
        assert log.get("tenant") == "demob", f"VULNERABILITY: viewerB with ?tenant=DemoA sees tenant={log.get('tenant')}"


def test_18_viewer_a_only_sees_demoA(test_client, test_data):
    _login(test_client, test_data["viewer_a_email"], test_data["viewer_a_password"])

    response = test_client.get("/api/get-logs")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    logs = data.get("logs", [])
    for log in logs:
        assert log.get("tenant") == "demoa", f"VULNERABILITY: viewerA sees tenant={log.get('tenant')}"

    response = test_client.get("/api/get-alerts")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    alerts = data.get("alerts", [])
    for alert in alerts:
        assert alert.get("tenant") == "demoa", f"VULNERABILITY: viewerA sees alert tenant={alert.get('tenant')}"


def test_19_no_cookie_routes_return_401():
    from fastapi.testclient import TestClient
    from app.main import app

    no_auth_client = TestClient(app)

    routes_to_test = [
        ("GET", "/api/get-logs"),
        ("GET", "/api/get-alerts"),
        ("GET", "/api/dashboard"),
        ("GET", "/api/get-rules"),
        ("GET", "/api/get-users"),
        ("POST", "/api/create-user"),
        ("POST", "/api/create-alertRule"),
        ("PUT", "/api/update-user"),
        ("DELETE", "/api/delete-log/demoA"),
        ("PUT", "/api/update-rule/demoA"),
        ("PATCH", "/api/rules/demoA/enabled"),
        ("DELETE", "/api/delete-rule/demoA"),
        ("PATCH", "/api/alerts/demoA"),
        ("POST", "/api/ingest"),
    ]

    for method, path in routes_to_test:
        if method == "GET":
            response = no_auth_client.get(path)
        elif method == "POST":
            response = no_auth_client.post(path, json={})
        elif method == "PUT":
            response = no_auth_client.put(path, json={})
        elif method == "DELETE":
            response = no_auth_client.delete(path)
        elif method == "PATCH":
            response = no_auth_client.patch(path, json={})

        assert response.status_code == 401, (
            f"Expected 401 for {method} {path}, got {response.status_code}"
        )


def test_20_viewer_b_rule_id_routes_403(test_client, test_data):
    _login(test_client, test_data["viewer_b_email"], test_data["viewer_b_password"])

    rule_id = SEED_DATA["demoA_rule_id"]

    response = test_client.put(f"/api/update-rule/{rule_id}", json={"name": "Evil", "enabled": True})
    assert response.status_code == 403, f"Expected 403 for PUT update-rule, got {response.status_code}"

    response = test_client.patch(f"/api/rules/{rule_id}/enabled", json={"enabled": False})
    assert response.status_code == 403, f"Expected 403 for PATCH rules/enabled, got {response.status_code}"

    response = test_client.delete(f"/api/delete-rule/{rule_id}")
    assert response.status_code == 403, f"Expected 403 for DELETE delete-rule, got {response.status_code}"


def test_21_viewer_b_user_id_routes_403(test_client, test_data):
    _login(test_client, test_data["viewer_b_email"], test_data["viewer_b_password"])

    response = test_client.put("/api/update-user", json={
        "id": 999,
        "username": "evil",
        "email": "evil@example.com",
        "tenant": "demoB",
        "role": "VIEWER",
        "password": "Password123!"
    })
    assert response.status_code == 403, f"Expected 403 for PUT update-user, got {response.status_code}"

    response = test_client.delete("/api/delete-user/999")
    assert response.status_code == 403, f"Expected 403 for DELETE delete-user, got {response.status_code}"
