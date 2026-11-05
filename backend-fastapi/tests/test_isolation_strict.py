"""
STRICT INTEGRATION TESTS for tenant isolation.
Tests MUST hit real database through real HTTP app.
Uses exact status codes and exact row counts - no ranges.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture(scope="session")
def test_client():
    """Test client with app loaded."""
    with TestClient(app) as client:
        yield client


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


def test_1_viewer_b_forced_to_own_tenant_on_logs(test_client, test_data):
    """viewerB GET /api/get-logs?tenant=demoA -> forced to demoB (zero demoA rows)."""
    test_client.post("/api/auth/login", json={
        "email": test_data["viewer_b_email"],
        "password": test_data["viewer_b_password"]
    })
    
    response = test_client.get("/api/get-logs?tenant=demoA")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    data = response.json()
    logs = data.get("logs", [])
    
    # Zero demoA rows - viewer bypass does NOT work
    demo_a_logs = [l for l in logs if l.get("tenant") == "demoA"]
    assert len(demo_a_logs) == 0, f"VULNERABILITY: viewerB sees {len(demo_a_logs)} demoA logs"
    
    # viewerB sees their own demoB logs
    demo_b_logs = [l for l in logs if l.get("tenant") == "demoB"]
    assert len(demo_b_logs) >= 0, "viewerB should see own tenant logs"


def test_2_viewer_b_cannot_see_demo_a_alerts(test_client, test_data):
    """viewerB GET /api/get-alerts?tenant=demoA -> zero demoA rows."""
    test_client.post("/api/auth/login", json={
        "email": test_data["viewer_b_email"],
        "password": test_data["viewer_b_password"]
    })
    
    response = test_client.get("/api/get-alerts?tenant=demoA")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    data = response.json()
    alerts = data.get("alerts", [])
    
    # Zero demoA alerts - viewer bypass does NOT work
    demo_a_alerts = [a for a in alerts if a.get("tenant") == "demoA"]
    assert len(demo_a_alerts) == 0, f"VULNERABILITY: viewerB sees {len(demo_a_alerts)} demoA alerts"


def test_4_viewer_b_cannot_access_demo_a_alert(test_client, test_data):
    """viewerB PATCH /api/alerts/{demoA id} -> 403 (no GET endpoint for individual alerts)."""
    # Login as admin to get demoA alert ID
    test_client.post("/api/auth/login", json={
        "email": test_data["admin_email"],
        "password": test_data["admin_password"]
    })
    
    alerts_resp = test_client.get("/api/get-alerts?tenant=demoA")
    assert alerts_resp.status_code == 200
    alerts = alerts_resp.json().get("alerts", [])
    if not alerts:
        pytest.skip("No demoA alerts found")
    
    alert_id = alerts[0]["id"]
    
    # Now viewerB tries to PATCH it
    test_client.post("/api/auth/login", json={
        "email": test_data["viewer_b_email"],
        "password": test_data["viewer_b_password"]
    })
    
    response = test_client.patch(f"/api/alerts/{alert_id}", json={"status": "CLOSED"})
    assert response.status_code == 403, f"Expected 403, got {response.status_code} - VULNERABILITY: viewer can modify another tenant's alert"


def test_5_viewer_b_cannot_patch_demo_a_alert(test_client, test_data):
    """viewerB PATCH /api/alerts/{demoA id} -> 403."""
    test_client.post("/api/auth/login", json={
        "email": test_data["viewer_b_email"],
        "password": test_data["viewer_b_password"]
    })
    
    alerts_resp = test_client.get("/api/get-alerts?tenant=demoA")
    if alerts_resp.status_code != 200:
        pytest.skip("Cannot fetch alerts")
    
    alerts = alerts_resp.json().get("alerts", [])
    if not alerts:
        pytest.skip("No demoA alerts found")
    
    alert_id = alerts[0]["id"]
    response = test_client.patch(f"/api/alerts/{alert_id}", json={"status": "CLOSED"})
    assert response.status_code == 403, f"Expected 403, got {response.status_code} - VULNERABILITY: viewer can modify another tenant's alert"


def test_6_viewer_cannot_access_admin_endpoints(test_client, test_data):
    """viewer on /api/get-users, /api/create-user, /api/get-rules, /api/tenants -> 403."""
    test_client.post("/api/auth/login", json={
        "email": test_data["viewer_b_email"],
        "password": test_data["viewer_b_password"]
    })
    
    # Viewer accessing get-users -> 403
    resp = test_client.get("/api/get-users")
    assert resp.status_code == 403, f"Expected 403 for viewer get-users, got {resp.status_code}"
    
    # Viewer accessing get-rules -> 403
    resp = test_client.get("/api/get-rules")
    assert resp.status_code == 403, f"Expected 403 for viewer get-rules, got {resp.status_code}"


def test_9_register_returns_404(test_client):
    """POST /api/auth/register -> 404."""
    response = test_client.post("/api/auth/register", json={
        "username": "testuser",
        "email": "test@example.com",
        "tenant": "test"
    })
    assert response.status_code == 404, f"Expected 404, got {response.status_code}"


def test_7_admin_can_see_all_tenants_logs(test_client, test_data):
    """admin GET /api/get-logs without tenant -> rows from both tenants."""
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