"""Functional end-to-end tests against the real FastAPI app + test database."""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from conftest import ADMIN_EMAIL, ADMIN_PASSWORD, VIEWER_A_EMAIL, VIEWER_A_PASSWORD


def _login(client, email: str, password: str):
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"login failed: {res.status_code} {res.text}"
    return res


class TestFunctional:
    """End-to-end functional verification."""

    def test_admin_login_and_sees_all_tenants(self):
        client = TestClient(app)
        _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
        res = client.get("/api/get-logs?tenant=all&limit=5")
        assert res.status_code == 200
        assert "logs" in res.json()

    def test_viewer_login_and_sees_own_tenant_only(self):
        client = TestClient(app)
        _login(client, VIEWER_A_EMAIL, VIEWER_A_PASSWORD)
        res = client.get("/api/get-logs?limit=100")
        assert res.status_code == 200
        logs = res.json()["logs"]
        for log in logs:
            assert log["tenant"] == "demoa"

    def test_alert_rule_model_has_required_columns(self):
        from sqlalchemy import inspect
        from app.models.alert import AlertRule
        cols = {c.name for c in AlertRule.__table__.columns}
        expected = {"id", "name", "description", "tenant", "conditions",
                    "enabled", "severity", "createdAt", "updatedAt"}
        assert expected.issubset(cols)

    def test_alert_model_has_dedupe_key(self):
        from sqlalchemy import inspect
        from app.models.alert import Alert
        cols = {c.name for c in Alert.__table__.columns}
        assert "dedupe_key" in cols

    def test_security_event_matches_schema(self):
        from app.models.security_event import SecurityEvent
        cols = {c.name for c in SecurityEvent.__table__.columns}
        assert "ingested_at" in cols

    def test_firewall_event_fields_searchable(self):
        client = TestClient(app)
        _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
        res = client.get("/api/get-logs?source=firewall&limit=5")
        assert res.status_code == 200
        data = res.json()
        assert "logs" in data
