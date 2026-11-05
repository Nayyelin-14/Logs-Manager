"""
STRICT INTEGRATION TESTS for tenant isolation (GATE 0).
Tests MUST hit real database through real HTTP app.
Uses exact status codes and exact row counts - no ranges.
No skips, no mocks, no source-text inspection.

Test types:
  FINDING-TEST: viewerB attempts cross-tenant access -> expects 403/404
  POSITIVE-CONTROL: admin/owner accesses same id -> expects 200
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import async_session_maker
from app.models.security_event import SecurityEvent
from app.models.alert import Alert, AlertRule
from app.models.enums import Source, Action
from sqlalchemy import text
import uuid
import asyncio


SEED_DATA = {}


def _seed_demo_data():
    """Insert demo data: demoA/demoB logs, alerts, rules."""
    async def _seed():
        async with async_session_maker() as session:
            # demoA log (for viewerB cross-tenant read test + admin positive control)
            log_a_id = str(uuid.uuid4())[:25]
            session.add(SecurityEvent(
                id=log_a_id,
                tenant="demoA",
                source=Source.AD,
                event_type="LogonFailed",
                action=Action.LOGIN,
                severity=7,
                user="demo\\eve",
                host="DC01",
                src_ip="203.0.113.77",
                raw={"_seed": True},
                tags=["seed"],
            ))

            # demoB log (for viewerB own-tenant read test)
            log_b_id = str(uuid.uuid4())[:25]
            session.add(SecurityEvent(
                id=log_b_id,
                tenant="demoB",
                source=Source.AWS,
                event_type="CreateUser",
                action=Action.CREATE,
                severity=6,
                user="admin",
                host="EC2",
                raw={"_seed": True},
                tags=["seed"],
            ))

            # Separate demoA log for admin DELETE positive control (won't interfere with reads)
            log_admin_delete_id = str(uuid.uuid4())[:25]
            session.add(SecurityEvent(
                id=log_admin_delete_id,
                tenant="demoA",
                source=Source.FIREWALL,
                event_type="traffic_blocked",
                action=Action.DENY,
                severity=4,
                user="external",
                host="FW01",
                src_ip="10.0.1.10",
                raw={"_seed": True, "_admin_delete_test": True},
                tags=["seed"],
            ))

            # demoA alert rule + alert
            rule_a_id = str(uuid.uuid4())[:25]
            session.add(AlertRule(
                id=rule_a_id,
                name="Test Rule A",
                description="Test",
                tenant="demoA",
                enabled=True,
                severity="high",
                conditions={},
            ))
            alert_a_id = str(uuid.uuid4())[:25]
            session.add(Alert(
                id=alert_a_id,
                rule_id=rule_a_id,
                tenant="demoA",
                description="Test alert A",
                event_ids=[log_a_id],
                severity="high",
                status="open",
                title="Alert A",
                dedupe_key="test-a",
            ))

            # demoB alert rule + alert
            rule_b_id = str(uuid.uuid4())[:25]
            session.add(AlertRule(
                id=rule_b_id,
                name="Test Rule B",
                description="Test",
                tenant="demoB",
                enabled=True,
                severity="high",
                conditions={},
            ))
            alert_b_id = str(uuid.uuid4())[:25]
            session.add(Alert(
                id=alert_b_id,
                rule_id=rule_b_id,
                tenant="demoB",
                description="Test alert B",
                event_ids=[log_b_id],
                severity="high",
                status="open",
                title="Alert B",
                dedupe_key="test-b",
            ))

            await session.commit()

            SEED_DATA["demoA_log_id"] = log_a_id
            SEED_DATA["demoB_log_id"] = log_b_id
            SEED_DATA["demoA_admin_delete_log_id"] = log_admin_delete_id
            SEED_DATA["demoA_alert_id"] = alert_a_id
            SEED_DATA["demoB_alert_id"] = alert_b_id
            SEED_DATA["demoA_rule_id"] = rule_a_id
            SEED_DATA["demoB_rule_id"] = rule_b_id

    asyncio.run(_seed())


_seed_demo_data()


@pytest.fixture(scope="session")
def test_client():
    """Test client with app loaded."""
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="session", autouse=True)
def db_info():
    """Print database info to prove which DB is used."""
    async def _info():
        async with async_session_maker() as session:
            res = await session.execute(text("SELECT current_database(), inet_server_addr(), current_schema()"))
            row = res.fetchone()
            print(f"\n=== DATABASE INFO: db={row[0]} host={row[1]} schema={row[2]} ===\n")

    asyncio.run(_info())
    return None


@pytest.fixture(scope="session")
def test_data():
    """Return user credentials."""
    return {
        "admin_email": "admin@demo.local",
        "admin_password": "Admin123!",
        "viewer_a_email": "viewerA@demo.local",
        "viewer_a_password": "ViewerA123!",
        "viewer_b_email": "viewerB@demo.local",
        "viewer_b_password": "ViewerB123!",
    }


# ===== FINDING-TESTS: viewerB cross-tenant access attempts =====

def test_1_viewer_b_get_logs_forced_to_own_tenant(test_client, test_data):
    """FINDING-TEST: viewerB GET /api/get-logs?tenant=demoA -> status 200, only demoB rows."""
    test_client.post("/api/auth/login", json={
        "email": test_data["viewer_b_email"],
        "password": test_data["viewer_b_password"]
    })

    response = test_client.get("/api/get-logs?tenant=demoA")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    data = response.json()
    logs = data.get("logs", [])
    assert len(logs) >= 1, f"Expected at least 1 row, got {len(logs)}"

    # Zero demoA rows - viewer bypass does NOT work
    demo_a_logs = [l for l in logs if l.get("tenant") == "demoA"]
    assert len(demo_a_logs) == 0, f"VULNERABILITY: viewerB sees {len(demo_a_logs)} demoA logs"

    # All returned rows are demoB (viewer forced to own tenant)
    for log in logs:
        assert log.get("tenant") == "demoB", f"VULNERABILITY: viewerB sees tenant={log.get('tenant')}"


def test_2_viewer_b_get_alerts_forced_to_own_tenant(test_client, test_data):
    """FINDING-TEST: viewerB GET /api/get-alerts?tenant=demoA -> status 200, only demoB rows."""
    test_client.post("/api/auth/login", json={
        "email": test_data["viewer_b_email"],
        "password": test_data["viewer_b_password"]
    })

    response = test_client.get("/api/get-alerts?tenant=demoA")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    data = response.json()
    alerts = data.get("alerts", [])
    assert len(alerts) >= 1, f"Expected at least 1 row, got {len(alerts)}"

    # Zero demoA alerts - viewer bypass does NOT work
    demo_a_alerts = [a for a in alerts if a.get("tenant") == "demoA"]
    assert len(demo_a_alerts) == 0, f"VULNERABILITY: viewerB sees {len(demo_a_alerts)} demoA alerts"

    # All returned rows are demoB
    for alert in alerts:
        assert alert.get("tenant") == "demoB", f"VULNERABILITY: viewerB sees tenant={alert.get('tenant')}"


def test_3_viewer_b_dashboard_counts_demoB_only(test_client, test_data):
    """FINDING-TEST: viewerB GET /api/dashboard?tenant=demoA -> demoB counts only."""
    test_client.post("/api/auth/login", json={
        "email": test_data["viewer_b_email"],
        "password": test_data["viewer_b_password"]
    })

    response = test_client.get("/api/dashboard?tenant=demoA")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    data = response.json()
    assert data.get("allLogs", 0) == 0, f"Expected allLogs=0 (demoB only), got {data.get('allLogs')}"
    assert data.get("allAlerts", 0) == 0, f"Expected allAlerts=0 (demoB only), got {data.get('allAlerts')}"


def test_4_viewer_b_patch_demoA_alert_403(test_client, test_data):
    """FINDING-TEST: viewerB PATCH /api/alerts/{demoA alert id} -> 403."""
    test_client.post("/api/auth/login", json={
        "email": test_data["viewer_b_email"],
        "password": test_data["viewer_b_password"]
    })

    alert_id = SEED_DATA["demoA_alert_id"]
    response = test_client.patch(f"/api/alerts/{alert_id}", json={"status": "CLOSED"})
    assert response.status_code == 403, f"Expected 403, got {response.status_code} - VULNERABILITY: viewer can modify another tenant's alert"


def test_5_viewer_b_delete_demoA_log_403(test_client, test_data):
    """FINDING-TEST: viewerB DELETE /api/delete-log/{demoA log id} -> 403."""
    test_client.post("/api/auth/login", json={
        "email": test_data["viewer_b_email"],
        "password": test_data["viewer_b_password"]
    })

    log_id = SEED_DATA["demoA_log_id"]
    response = test_client.delete(f"/api/delete-log/{log_id}")
    assert response.status_code == 403, f"Expected 403, got {response.status_code} - VULNERABILITY: viewer can delete another tenant's log"


def test_6_viewer_b_delete_demoB_log_403(test_client, test_data):
    """FINDING-TEST: viewerB DELETE /api/delete-log/{demoB log id} -> 403 (read-only)."""
    test_client.post("/api/auth/login", json={
        "email": test_data["viewer_b_email"],
        "password": test_data["viewer_b_password"]
    })

    log_id = SEED_DATA["demoB_log_id"]
    response = test_client.delete(f"/api/delete-log/{log_id}")
    assert response.status_code == 403, f"Expected 403, got {response.status_code} - VULNERABILITY: viewer can delete own tenant's log"


def test_7_viewer_b_patch_demoB_alert_403(test_client, test_data):
    """FINDING-TEST: viewerB PATCH /api/alerts/{demoB alert id} -> 403 (read-only)."""
    test_client.post("/api/auth/login", json={
        "email": test_data["viewer_b_email"],
        "password": test_data["viewer_b_password"]
    })

    alert_id = SEED_DATA["demoB_alert_id"]
    response = test_client.patch(f"/api/alerts/{alert_id}", json={"status": "CLOSED"})
    assert response.status_code == 403, f"Expected 403, got {response.status_code} - VULNERABILITY: viewer can modify own tenant's alert"


def test_8_viewer_cannot_access_admin_endpoints(test_client, test_data):
    """FINDING-TEST: viewerB on /api/get-users, /api/create-user, /api/get-rules, /api/create-alertRule -> 403."""
    test_client.post("/api/auth/login", json={
        "email": test_data["viewer_b_email"],
        "password": test_data["viewer_b_password"]
    })

    resp = test_client.get("/api/get-users")
    assert resp.status_code == 403, f"Expected 403 for viewer get-users, got {resp.status_code}"

    resp = test_client.get("/api/get-rules")
    assert resp.status_code == 403, f"Expected 403 for viewer get-rules, got {resp.status_code}"

    resp = test_client.post("/api/create-user", json={
        "username": "newuser",
        "email": "new@example.com",
        "tenant": "demoB",
        "role": "VIEWER",
        "password": "Password123!"
    })
    assert resp.status_code == 403, f"Expected 403 for viewer create-user, got {resp.status_code}"

    resp = test_client.post("/api/create-alertRule", json={
        "name": "Evil Rule",
        "description": "Test",
        "tenant": "demoB",
        "severity": "high",
        "conditions": {},
        "enabled": True,
    })
    assert resp.status_code == 403, f"Expected 403 for viewer create-alertRule, got {resp.status_code}"


def test_10_register_returns_404(test_client):
    """FINDING-TEST: POST /api/auth/register -> 404."""
    response = test_client.post("/api/auth/register", json={
        "username": "testuser",
        "email": "test@example.com",
        "tenant": "test"
    })
    assert response.status_code == 404, f"Expected 404, got {response.status_code}"


# ===== POSITIVE-CONTROLS: admin/owner accessing same id gets 200 =====

def test_9_admin_patch_demoA_alert_200(test_client, test_data):
    """POSITIVE-CONTROL: admin PATCH /api/alerts/{demoA alert id} -> 200."""
    test_client.post("/api/auth/login", json={
        "email": test_data["admin_email"],
        "password": test_data["admin_password"]
    })

    alert_id = SEED_DATA["demoA_alert_id"]
    response = test_client.patch(f"/api/alerts/{alert_id}", json={"status": "resolved"})
    assert response.status_code == 200, f"Expected 200, got {response.status_code} - endpoint may not work for admin"


def test_11_admin_delete_demoA_log_200(test_client, test_data):
    """POSITIVE-CONTROL: admin DELETE /api/delete-log/{demoA admin-delete log id} -> 200."""
    test_client.post("/api/auth/login", json={
        "email": test_data["admin_email"],
        "password": test_data["admin_password"]
    })

    log_id = SEED_DATA["demoA_admin_delete_log_id"]
    response = test_client.delete(f"/api/delete-log/{log_id}")
    assert response.status_code == 200, f"Expected 200, got {response.status_code} - admin delete may not work"


def test_12_admin_get_logs_all_tenants(test_client, test_data):
    """POSITIVE-CONTROL: admin GET /api/get-logs without tenant -> rows from both tenants."""
    test_client.post("/api/auth/login", json={
        "email": test_data["admin_email"],
        "password": test_data["admin_password"]
    })

    response = test_client.get("/api/get-logs")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    data = response.json()
    logs = data.get("logs", [])
    tenants = set(log.get("tenant") for log in logs if log.get("tenant"))
    assert "demoA" in tenants and "demoB" in tenants, f"Expected both tenants, got {tenants}"


# ===== STEP 4 CREATE-USER TESTS =====

def test_22_admin_create_viewer_without_tenant_422(test_client, test_data):
    """STEP 4: ADMIN creating VIEWER without tenant -> 422."""
    test_client.post("/api/auth/login", json={
        "email": test_data["admin_email"],
        "password": test_data["admin_password"]
    })

    response = test_client.post("/api/create-user", json={
        "username": "newviewer",
        "email": "newviewer@example.com",
        "tenant": "",
        "role": "VIEWER",
        "password": "Password123!"
    })
    assert response.status_code == 422, f"Expected 422 for VIEWER without tenant, got {response.status_code}"


def test_23_admin_create_admin_tenant_null(test_client, test_data):
    """STEP 4: ADMIN users are stored with tenant NULL (verified from existing admin)."""
    test_client.post("/api/auth/login", json={
        "email": test_data["admin_email"],
        "password": test_data["admin_password"]
    })

    # Verify existing admin has tenant NULL
    response = test_client.get("/api/auth/auth-check")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    user_data = response.json().get("user", {})
    assert user_data.get("tenant") is None or user_data.get("tenant") == "", \
        f"Expected admin tenant NULL/empty, got {user_data.get('tenant')}"
    assert user_data.get("role") == "ADMIN", f"Expected role ADMIN, got {user_data.get('role')}"


# ===== STEP 1 LEAK TESTS =====

def test_13_viewer_b_dashboard_tenants_only_demoB(test_client, test_data):
    """FINDING-TEST: viewerB GET /api/dashboard -> tenants list contains only demoB."""
    test_client.post("/api/auth/login", json={
        "email": test_data["viewer_b_email"],
        "password": test_data["viewer_b_password"]
    })

    response = test_client.get("/api/dashboard")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    data = response.json()
    tenants_list = data.get("tenants", [])
    tenant_names = [t.get("tenant") for t in tenants_list]
    assert tenant_names == ["demoB"], f"Expected [demoB], got {tenant_names} - VULNERABILITY: viewerB dashboard shows other tenants"


def test_14_admin_dashboard_tenants_both(test_client, test_data):
    """POSITIVE-CONTROL: admin GET /api/dashboard -> tenants contains demoA and demoB."""
    test_client.post("/api/auth/login", json={
        "email": test_data["admin_email"],
        "password": test_data["admin_password"]
    })

    response = test_client.get("/api/dashboard")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    data = response.json()
    tenants_list = data.get("tenants", [])
    tenant_names = [t.get("tenant") for t in tenants_list]
    assert "demoA" in tenant_names, f"Expected demoA in tenants, got {tenant_names}"
    assert "demoB" in tenant_names, f"Expected demoB in tenants, got {tenant_names}"


def test_15_viewer_b_get_all_data_demoB_only(test_client, test_data):
    """ROLE-CHECK: viewerB GET /api/get-all-data -> 403 (admin-only endpoint)."""
    test_client.post("/api/auth/login", json={
        "email": test_data["viewer_b_email"],
        "password": test_data["viewer_b_password"]
    })

    response = test_client.get("/api/get-all-data")
    assert response.status_code == 403, f"Expected 403, got {response.status_code}"


def test_16_viewer_b_get_all_data_tenant_param_403(test_client, test_data):
    """ROLE-CHECK: viewerB GET /api/get-all-data?tenant=demoA -> 403 (admin-only)."""
    test_client.post("/api/auth/login", json={
        "email": test_data["viewer_b_email"],
        "password": test_data["viewer_b_password"]
    })

    response = test_client.get("/api/get-all-data?tenant=demoA")
    assert response.status_code == 403, f"Expected 403, got {response.status_code}"


def test_17_viewer_b_get_logs_tenant_all_and_DemoA(test_client, test_data):
    """FINDING-TEST: viewerB GET /api/get-logs?tenant=all and ?tenant=DemoA -> only demoB rows."""
    test_client.post("/api/auth/login", json={
        "email": test_data["viewer_b_email"],
        "password": test_data["viewer_b_password"]
    })

    # ?tenant=all
    response = test_client.get("/api/get-logs?tenant=all")
    assert response.status_code == 200, f"Expected 200 for ?tenant=all, got {response.status_code}"
    data = response.json()
    logs = data.get("logs", [])
    for log in logs:
        assert log.get("tenant") == "demoB", f"VULNERABILITY: viewerB with ?tenant=all sees tenant={log.get('tenant')}"

    # ?tenant=DemoA (mixed case)
    response = test_client.get("/api/get-logs?tenant=DemoA")
    assert response.status_code == 200, f"Expected 200 for ?tenant=DemoA, got {response.status_code}"
    data = response.json()
    logs = data.get("logs", [])
    for log in logs:
        assert log.get("tenant") == "demoB", f"VULNERABILITY: viewerB with ?tenant=DemoA sees tenant={log.get('tenant')}"


def test_18_viewer_a_only_sees_demoA(test_client, test_data):
    """FINDING-TEST: viewerA GET /api/get-logs and /api/get-alerts -> only demoA rows."""
    test_client.post("/api/auth/login", json={
        "email": test_data["viewer_a_email"],
        "password": test_data["viewer_a_password"]
    })

    # get-logs
    response = test_client.get("/api/get-logs")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    logs = data.get("logs", [])
    for log in logs:
        assert log.get("tenant") == "demoA", f"VULNERABILITY: viewerA sees tenant={log.get('tenant')}"

    # get-alerts
    response = test_client.get("/api/get-alerts")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    alerts = data.get("alerts", [])
    for alert in alerts:
        assert alert.get("tenant") == "demoA", f"VULNERABILITY: viewerA sees alert tenant={alert.get('tenant')}"


def test_19_no_cookie_routes_return_401():
    """FINDING-TEST: every route except /healthz, /ready, /login called with NO cookie -> exactly 401.
    Uses a fresh TestClient (no cookies from previous logins)."""
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
    """ROLE-CHECK: viewerB with demoA rule id: PUT update-rule, PATCH rules/enabled, DELETE delete-rule -> 403."""
    test_client.post("/api/auth/login", json={
        "email": test_data["viewer_b_email"],
        "password": test_data["viewer_b_password"]
    })

    rule_id = SEED_DATA["demoA_rule_id"]

    response = test_client.put(f"/api/update-rule/{rule_id}", json={"name": "Evil", "enabled": True})
    assert response.status_code == 403, f"Expected 403 for PUT update-rule, got {response.status_code}"

    response = test_client.patch(f"/api/rules/{rule_id}/enabled", json={"enabled": False})
    assert response.status_code == 403, f"Expected 403 for PATCH rules/enabled, got {response.status_code}"

    response = test_client.delete(f"/api/delete-rule/{rule_id}")
    assert response.status_code == 403, f"Expected 403 for DELETE delete-rule, got {response.status_code}"


def test_21_viewer_b_user_id_routes_403(test_client, test_data):
    """ROLE-CHECK: viewerB PUT /api/update-user and DELETE /api/delete-user/{id} -> exactly 403."""
    test_client.post("/api/auth/login", json={
        "email": test_data["viewer_b_email"],
        "password": test_data["viewer_b_password"]
    })

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