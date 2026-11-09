import uuid

from conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    VIEWER_A_EMAIL,
    VIEWER_A_PASSWORD,
    VIEWER_B_EMAIL,
    VIEWER_B_PASSWORD,
    login,
)


def _relogin(client, email: str, password: str):
    client.cookies.clear()
    login(client, email, password)
    return client


def _ingest(client, api_key: str, payload: dict):
    return client.post(
        "/api/ingest",
        headers={"X-API-Key": api_key, "Content-Type": "application/json"},
        json=payload,
    )


class TestEventDetail:

    def test_owner_and_platform_admin_can_read_event(self, client, api_key):
        res = _ingest(
            client,
            api_key,
            {
                "source": "api",
                "event_type": "event-detail-test",
                "user": "alice",
                "severity": 4,
            },
        )
        assert res.status_code == 200, res.text
        event_id = res.json()["eventId"]

        _relogin(client, VIEWER_A_EMAIL, VIEWER_A_PASSWORD)
        own = client.get(f"/api/events/{event_id}")
        assert own.status_code == 200, own.text
        body = own.json()
        assert body["id"] == event_id
        assert body["tenant"] == "demoa"
        assert body["eventType"] == "event-detail-test"
        assert "raw" in body

        _relogin(client, VIEWER_B_EMAIL, VIEWER_B_PASSWORD)
        other = client.get(f"/api/events/{event_id}")
        assert other.status_code == 404, other.text

        _relogin(client, ADMIN_EMAIL, ADMIN_PASSWORD)
        platform = client.get(f"/api/events/{event_id}")
        assert platform.status_code == 200, platform.text

    def test_missing_event_returns_404(self, client, admin_client):
        res = client.get(f"/api/events/{uuid.uuid4().hex}")
        assert res.status_code == 404


class TestTenantBoundAdmin:

    def _create_tenant_admin(self, client, tenant: str = "demoa"):
        _relogin(client, ADMIN_EMAIL, ADMIN_PASSWORD)
        suffix = uuid.uuid4().hex[:8]
        email = f"tadmin_{suffix}@demo.local"
        password = "TenantAdminPassword123!"
        res = client.post(
            "/api/create-user",
            data={
                "username": f"tadmin_{suffix}",
                "email": email,
                "tenant": tenant,
                "role": "ADMIN",
                "status": "ACTIVE",
                "password": password,
            },
        )
        assert res.status_code == 201, res.text
        return email, password

    def test_tenant_admin_is_bound_to_own_tenant(self, client, api_key_demob):
        email, password = self._create_tenant_admin(client, "demoa")

        _relogin(client, ADMIN_EMAIL, ADMIN_PASSWORD)
        ing = _ingest(
            client,
            api_key_demob,
            {
                "source": "crowdstrike",
                "event_type": "MalwareDetected",
                "src_ip": "198.51.100.77",
                "host": "host-b",
                "severity": 9,
            },
        )
        assert ing.status_code == 200, ing.text
        demob_event = ing.json()["eventId"]

        alerts = client.get("/api/get-alerts?tenant=demob&limit=50")
        assert alerts.status_code == 200, alerts.text
        demob_alerts = [a for a in alerts.json()["alerts"] if a["tenant"] == "demob"]
        assert demob_alerts, alerts.text
        demob_alert = demob_alerts[0]["id"]

        _relogin(client, email, password)

        cross_rule = client.post(
            "/api/create-alertRule",
            json={
                "name": f"cross-{uuid.uuid4().hex[:6]}",
                "tenant": "demob",
                "conditions": [{"type": "event_type", "value": "x"}],
            },
        )
        assert cross_rule.status_code == 403, cross_rule.text

        cross_user = client.post(
            "/api/create-user",
            data={
                "username": "crossuser",
                "email": f"cross_{uuid.uuid4().hex[:6]}@demo.local",
                "tenant": "demob",
                "role": "VIEWER",
                "password": "Password123!",
            },
        )
        assert cross_user.status_code == 403, cross_user.text

        assert client.get("/api/tenants").status_code == 403
        assert client.patch(
            f"/api/alerts/{demob_alert}", json={"status": "resolved"}
        ).status_code == 404
        assert (
            client.delete(f"/api/delete-log/{demob_event}").json().get("success") is False
        )

        users = client.get("/api/get-users?tenant=demob")
        assert users.status_code == 200, users.text
        assert all(u["tenant"] == "demoa" for u in users.json()["users"])

        visible_alerts = client.get("/api/get-alerts?tenant=demob")
        assert visible_alerts.status_code == 200, visible_alerts.text
        assert all(a["tenant"] == "demoa" for a in visible_alerts.json()["alerts"])

        own_rule = client.post(
            "/api/create-alertRule",
            json={
                "name": f"own-{uuid.uuid4().hex[:6]}",
                "tenant": "demoa",
                "conditions": [{"type": "event_type", "value": "own-test"}],
            },
        )
        assert own_rule.status_code == 201, own_rule.text


class TestIngestRateLimit:

    def test_ingest_is_rate_limited_per_api_key(self, client, api_key, monkeypatch):
        from app.core.config import get_settings

        monkeypatch.setattr(
            get_settings(), "INGEST_RATE_LIMIT", "2/minute", raising=False
        )

        payload = {
            "source": "api",
            "event_type": "rate-limit-test",
            "user": "rate",
            "severity": 3,
        }
        first = _ingest(client, api_key, payload)
        second = _ingest(client, api_key, payload)
        third = _ingest(client, api_key, payload)

        assert first.status_code == 200, first.text
        assert second.status_code == 200, second.text
        assert third.status_code == 429, third.text
        assert third.headers.get("Retry-After")
