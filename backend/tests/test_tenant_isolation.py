"""
Tenant isolation verification tests.
Hits the real FastAPI app against a real test database.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from conftest import ADMIN_EMAIL, ADMIN_PASSWORD, VIEWER_A_EMAIL, VIEWER_A_PASSWORD


def _login(client, email: str, password: str):
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"login failed: {res.status_code} {res.text}"
    return res


class TestTenantIsolation:
    """Viewer of demoA sees only demoA data; demoB data is never returned."""

    def test_viewer_a_sees_only_demoa(self):
        client = TestClient(app)
        _login(client, VIEWER_A_EMAIL, VIEWER_A_PASSWORD)
        res = client.get("/api/get-logs?limit=100")
        assert res.status_code == 200
        logs = res.json()["logs"]
        for log in logs:
            assert log["tenant"] == "demoa", f"viewerA saw tenant={log.get('tenant')}"

    def test_viewer_a_tenant_param_demob_returns_only_demoa(self):
        """Even with ?tenant=demob, viewerA is forced to demoa."""
        client = TestClient(app)
        _login(client, VIEWER_A_EMAIL, VIEWER_A_PASSWORD)
        res = client.get("/api/get-logs?tenant=demob&limit=100")
        assert res.status_code == 200
        logs = res.json()["logs"]
        for log in logs:
            assert log["tenant"] == "demoa", f"viewerA with ?tenant=demob saw tenant={log.get('tenant')}"

    def test_viewer_a_cannot_call_admin_create_user(self):
        client = TestClient(app)
        _login(client, VIEWER_A_EMAIL, VIEWER_A_PASSWORD)
        res = client.post(
            "/api/create-user",
            data={"username": "x", "email": "x@x.com", "tenant": "demoa", "role": "VIEWER", "password": "p"},
        )
        assert res.status_code == 403, f"expected 403, got {res.status_code}"
