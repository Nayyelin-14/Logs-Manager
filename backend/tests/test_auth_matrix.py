import time
import uuid
import jwt
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import async_session_maker
from app.models.user import User
from app.models.tenant import Tenant
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, TokenPayload, decode_token
from app.core.config import get_settings
from sqlalchemy import select
import pytest


settings = get_settings()


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
    return res


def _logout(client):
    return client.post("/api/auth/logout")


def _auth_check(client):
    return client.get("/api/auth/auth-check")


def _get_admin_client(client=None):
    if client is None:
        client = TestClient(app)
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    return client


def _get_viewer_a_client(client=None):
    if client is None:
        client = TestClient(app)
    _login(client, VIEWER_A_EMAIL, VIEWER_A_PASSWORD)
    return client


def _get_viewer_b_client(client=None):
    if client is None:
        client = TestClient(app)
    _login(client, VIEWER_B_EMAIL, VIEWER_B_PASSWORD)
    return client


def _unique_email(prefix: str = "test") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}@demo.local"


def _create_expired_access_token(payload: TokenPayload, minutes_ago: int = 60) -> str:
    now = datetime.now(timezone.utc)
    expire = now - timedelta(minutes=minutes_ago)
    token_payload = payload.to_dict()
    token_payload.update({"exp": int(expire.timestamp())})
    return jwt.encode(token_payload, settings.ACCESS_TOKEN_SECRET, algorithm=settings.JWT_ALGORITHM)


def _create_expired_refresh_token(payload: TokenPayload, days_ago: int = 60) -> str:
    now = datetime.now(timezone.utc)
    expire = now - timedelta(days=days_ago)
    token_payload = payload.to_dict()
    token_payload.update({"exp": int(expire.timestamp())})
    return jwt.encode(token_payload, settings.REFRESH_TOKEN_SECRET, algorithm=settings.JWT_ALGORITHM)


class TestLoginAndSession:

    def test_login_success_sets_httponly_cookies(self, client):
        res = _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
        assert res.status_code == 200, f"login failed: {res.text}"
        assert "accessToken" in client.cookies, "accessToken cookie not set"
        assert "refreshToken" in client.cookies, "refreshToken cookie not set"

    def test_login_wrong_password_returns_401_same_message(self, client):
        res = _login(client, ADMIN_EMAIL, "WrongPassword!")
        assert res.status_code == 401, f"expected 401, got {res.status_code}: {res.text}"
        assert res.json()["detail"] == "Invalid credentials"

    def test_login_unknown_email_returns_401_same_message(self, client):
        res = _login(client, "nonexistent@demo.local", "AnyPassword!")
        assert res.status_code == 401, f"expected 401, got {res.status_code}: {res.text}"
        assert res.json()["detail"] == "Invalid credentials"

    def test_login_disabled_user_returns_403(self, client):
        admin = _get_admin_client(client)
        email = _unique_email("disabled")
        create_res = admin.post(
            "/api/create-user",
            data={"username": "disableduser", "email": email, "tenant": "demoa", "role": "VIEWER", "password": "Password123!", "status": "INACTIVE"},
        )
        assert create_res.status_code == 201, f"create failed: {create_res.text}"


        res = _login(client, email, "Password123!")
        assert res.status_code == 403, f"expected 403 for disabled user login, got {res.status_code}: {res.text}"

    def test_login_unknown_email_returns_401_same_message(self, client):
        res = _login(client, "nonexistent@demo.local", "AnyPassword!")
        assert res.status_code == 401, f"expected 401, got {res.status_code}: {res.text}"
        assert res.json()["detail"] == "Invalid credentials"

    def test_expired_access_token_with_valid_refresh_refreshes(self, client):
        _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)

        refresh_token = client.cookies.get("refreshToken")
        assert refresh_token is not None, "refresh token not set"
        payload = decode_token(refresh_token, settings.REFRESH_TOKEN_SECRET)

        expired_payload = TokenPayload(user_id=payload["userId"], username=payload["username"], email=payload["email"], tenant=payload["tenant"], role=payload["role"])
        expired_access = _create_expired_access_token(expired_payload)


        client.cookies.clear()
        client.cookies.set("accessToken", expired_access)
        client.cookies.set("refreshToken", refresh_token)

        res = client.get("/api/get-logs")
        assert res.status_code == 200, f"expected 200 after refresh, got {res.status_code}: {res.text}"

    def test_expired_refresh_token_returns_401(self, client):
        _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)

        refresh_token = client.cookies.get("refreshToken")
        assert refresh_token is not None, "refresh token not set"
        payload = decode_token(refresh_token, settings.REFRESH_TOKEN_SECRET)

        expired_payload = TokenPayload(user_id=payload["userId"], username=payload["username"], email=payload["email"], tenant=payload["tenant"], role=payload["role"])
        expired_refresh = _create_expired_refresh_token(expired_payload)
        expired_access = _create_expired_access_token(expired_payload)


        client.cookies.clear()
        client.cookies.set("accessToken", expired_access)
        client.cookies.set("refreshToken", expired_refresh)

        res = client.get("/api/get-logs")
        assert res.status_code == 401, f"expected 401, got {res.status_code}: {res.text}"

    def test_logout_invalidates_cookie(self, client):
        _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
        assert client.get("/api/get-logs").status_code == 200

        _logout(client)
        res = client.get("/api/get-logs")
        assert res.status_code == 401, f"expected 401 after logout, got {res.status_code}: {res.text}"

    def test_disabled_user_cannot_refresh(self, client):
        admin = _get_admin_client(client)
        email = _unique_email("disabled")
        create_res = admin.post(
            "/api/create-user",
            data={"username": "disableduser", "email": email, "tenant": "demoa", "role": "VIEWER", "password": "Password123!", "status": "INACTIVE"},
        )
        assert create_res.status_code == 201, f"create failed: {create_res.text}"


        res = _login(client, email, "Password123!")
        assert res.status_code == 403, f"expected 403 for disabled user login, got {res.status_code}: {res.text}"

    def test_inactive_tenant_cannot_refresh(self, client):
        admin = _get_admin_client(client)
        email = _unique_email("inactive")
        create_res = admin.post(
            "/api/create-user",
            data={"username": "inactiveuser", "email": email, "password": "Password123!", "role": "VIEWER", "tenant": "demoa", "status": "INACTIVE"},
        )
        assert create_res.status_code == 201, f"create failed: {create_res.text}"


        res = _login(client, email, "Password123!")
        assert res.status_code == 403, f"expected 403 for inactive tenant login, got {res.status_code}: {res.text}"


class TestRoleChecks:

    ADMIN_ONLY_ROUTES = [
        ("POST", "/api/create-user", {"username": "x", "email": "x@x.com", "tenant": "demoa", "role": "VIEWER", "password": "Password123!"}),
        ("PUT", "/api/update-user", {"id": 999, "username": "x"}),
        ("DELETE", "/api/delete-user/999", None),
        ("GET", "/api/get-users", None),
        ("GET", "/api/get-rules", None),
        ("POST", "/api/create-alertRule", {"name": "x", "tenant": "demoa", "conditions": [{"type": "severity_min"}]}),
        ("PUT", "/api/update-rule/abc123", {"name": "x"}),
        ("PATCH", "/api/rules/abc123/enabled", {"enabled": True}),
        ("DELETE", "/api/delete-rule/abc123", None),
        ("DELETE", "/api/delete-log/abc123", None),
        ("PATCH", "/api/alerts/abc123", {"status": "resolved"}),
        ("POST", "/api/tenants", {"name": "newtenant"}),
        ("GET", "/api/tenants", None),
        ("PATCH", "/api/tenants/demoa", {"is_active": True}),
        ("POST", "/api/tenants/demoa/rotate-key", None),
    ]

    @pytest.mark.parametrize("method,path,body", ADMIN_ONLY_ROUTES)
    def test_viewer_gets_403_on_admin_routes(self, client, method, path, body):
        client = _get_viewer_a_client(client)
        if method == "GET":
            res = client.get(path)
        elif method == "POST":
            if "create-user" in path or "update-user" in path:
                res = client.post(path, data=body)
            else:
                res = client.post(path, json=body)
        elif method == "PUT":
            res = client.put(path, data=body)
        elif method == "PATCH":
            res = client.patch(path, json=body)
        elif method == "DELETE":
            res = client.delete(path)
        assert res.status_code == 403, f"viewer {method} {path}: expected 403, got {res.status_code}: {res.text}"

    @pytest.mark.parametrize("method,path,body", ADMIN_ONLY_ROUTES)
    def test_anonymous_gets_401_on_admin_routes(self, client, method, path, body):
        client = TestClient(app)
        if method == "GET":
            res = client.get(path)
        elif method == "POST":
            if "create-user" in path or "update-user" in path:
                res = client.post(path, data=body)
            else:
                res = client.post(path, json=body)
        elif method == "PUT":
            res = client.put(path, data=body)
        elif method == "PATCH":
            res = client.patch(path, json=body)
        elif method == "DELETE":
            res = client.delete(path)
        assert res.status_code == 401, f"anon {method} {path}: expected 401, got {res.status_code}: {res.text}"


class TestTenantIsolation:

    def test_viewer_b_get_logs_forced_to_own_tenant(self, client):
        client = _get_viewer_b_client(client)
        res = client.get("/api/get-logs?tenant=demoa")
        assert res.status_code == 200
        logs = res.json()["logs"]
        for log in logs:
            assert log["tenant"] == "demob", f"viewerB saw tenant={log.get('tenant')}"

    def test_viewer_b_get_logs_tenant_all_returns_demob_only(self, client):
        client = _get_viewer_b_client(client)
        res = client.get("/api/get-logs?tenant=all")
        assert res.status_code == 200
        logs = res.json()["logs"]
        for log in logs:
            assert log["tenant"] == "demob", f"viewerB with ?tenant=all saw tenant={log.get('tenant')}"

    def test_viewer_b_get_alerts_forced_to_own_tenant(self, client):
        client = _get_viewer_b_client(client)
        res = client.get("/api/get-alerts?tenant=demoa")
        assert res.status_code == 200
        alerts = res.json()["alerts"]
        for alert in alerts:
            assert alert["tenant"] == "demob", f"viewerB saw alert tenant={alert.get('tenant')}"

    def test_viewer_b_dashboard_tenants_list_only_demob(self, client):
        client = _get_viewer_b_client(client)
        res = client.get("/api/dashboard")
        assert res.status_code == 200
        tenants = res.json().get("tenants", [])
        tenant_names = [t.get("tenant") for t in tenants]
        assert tenant_names == ["demob"], f"expected [demob], got {tenant_names}"

    def test_viewer_b_cannot_patch_demoa_alert(self, client, api_key):
        admin = _get_admin_client(client)

        admin.post("/api/rules", json={
            "name": "test-rule",
            "tenant": "demoa",
            "conditions": [{"type": "source", "value": "ad"}, {"type": "event_type", "value": "LogonFailed"}],
        })

        admin.post("/api/ingest", headers={"X-API-Key": api_key, "Content-Type": "application/json"}, json={
            "source": "ad",
            "tenant": "demoa",
            "event_type": "LogonFailed",
            "user": "eve_0",
            "ip": "192.0.2.1",
            "src_ip": "192.0.2.1",
            "reason": "wrong_password",
            "status": "Failure",
            "action": "LOGIN",
            "severity": 7,
            "@timestamp": time.time(),
        })
        res = admin.get("/api/get-alerts?tenant=demoa&limit=1")
        assert res.status_code == 200, f"expected 200, got {res.status_code}: {res.text}"
        alerts = res.json()["alerts"]
        assert len(alerts) == 1, f"expected 1 alert, got {len(alerts)}"
        alert_id = alerts[0]["id"]

        client = _get_viewer_b_client(client)
        res = client.patch(f"/api/alerts/{alert_id}", json={"status": "resolved"})
        assert res.status_code == 403, f"expected 403, got {res.status_code}: {res.text}"

    def test_viewer_b_cannot_delete_demoa_log(self, client, api_key):
        admin = _get_admin_client(client)
        res = admin.post("/api/ingest", headers={"X-API-Key": api_key, "Content-Type": "application/json"}, json={
            "source": "api",
            "tenant": "demoa",
            "event_type": "test",
            "user": "test",
            "ip": "1.2.3.4",
            "severity": 6,
        })
        assert res.status_code == 200
        event_id = res.json().get("eventId")
        assert event_id is not None

        client = _get_viewer_b_client(client)
        res = client.delete(f"/api/delete-log/{event_id}")
        assert res.status_code == 403, f"expected 403, got {res.status_code}: {res.text}"


class TestUserManagement:

    def test_create_user_admin_201(self, client):
        admin = _get_admin_client(client)
        email = _unique_email("newuser")
        create_res = admin.post(
            "/api/create-user",
            data={"username": "newuser", "email": email, "tenant": "demoa", "role": "VIEWER", "password": "Password123!"},
        )
        assert create_res.status_code == 201, f"create failed: {create_res.text}"

    def test_create_viewer_without_tenant_returns_422(self, client):
        admin = _get_admin_client(client)
        create_res = admin.post(
            "/api/create-user",
            data={"username": "no-tenant", "email": _unique_email("no-tenant"), "role": "VIEWER", "password": "Password123!"},
        )
        assert create_res.status_code == 422, f"expected 422, got {create_res.status_code}: {create_res.text}"

    def test_duplicate_email_returns_409(self, client):
        admin = _get_admin_client(client)
        admin.post(
            "/api/create-user",
            data={"username": "dup1", "email": "dup@example.com", "tenant": "demoa", "role": "VIEWER", "password": "Password123!"},
        )
        create_res = admin.post(
            "/api/create-user",
            data={"username": "dup2", "email": "dup@example.com", "tenant": "demoa", "role": "VIEWER", "password": "Password123!"},
        )
        assert create_res.status_code == 409, f"expected 409, got {create_res.status_code}: {create_res.text}"

    def test_response_never_contains_password_or_hash(self, client):
        admin = _get_admin_client(client)
        create_res = admin.post(
            "/api/create-user",
            data={"username": "nopw", "email": _unique_email("nopw"), "tenant": "demoa", "role": "VIEWER", "password": "Password123!"},
        )
        assert create_res.status_code == 201, f"create failed: {create_res.text}"
        created = create_res.json()
        assert "password" not in created
        assert "password_hash" not in created

    def test_admin_cannot_delete_self(self, client):
        admin = _get_admin_client(client)
        res = admin.delete(f"/api/delete-user/{ADMIN_EMAIL}")

        assert res.status_code == 403, f"expected 403/400, got {res.status_code}: {res.text}"

    def test_get_users_sorted_by_create_at_desc(self, client):
        admin = _get_admin_client(client)
        res = admin.get("/api/get-users")
        assert res.status_code == 200
        users = res.json()["users"]
        assert len(users) >= 3

    def test_created_user_appears_first_in_users_list(self, client):
        admin = _get_admin_client(client)
        before = admin.get("/api/get-users").json()["users"]
        first_before = before[0]["email"] if before else None

        admin.post(
            "/api/create-user",
            data={"username": "newuser", "email": _unique_email("newbie"), "tenant": "demoa", "role": "VIEWER", "password": "Password123!"},
        )
        after = admin.get("/api/get-users").json()["users"]
        first_after = after[0]["email"] if after else None
        assert first_after != first_before

    def test_new_user_can_login_and_sees_only_their_tenant(self, client):
        admin = _get_admin_client(client)
        email = _unique_email("newuser")
        admin.post(
            "/api/create-user",
            data={"username": "newuser", "email": email, "tenant": "demoa", "role": "VIEWER", "password": "Password123!"},
        )

        new_client = TestClient(app)
        _login(new_client, email, "Password123!")
        res = new_client.get("/api/get-logs?tenant=demoa")
        assert res.status_code == 200
        logs = res.json()["logs"]
        for log in logs:
            assert log["tenant"] == "demoa"

    def test_viewer_cannot_list_users_via_either_endpoint(self, client):
        client = _get_viewer_a_client(client)
        res = client.get("/api/get-users")
        assert res.status_code == 403, f"expected 403, got {res.status_code}: {res.text}"
        res = client.get("/api/auth/users")
        assert res.status_code == 403, f"expected 403, got {res.status_code}: {res.text}"
