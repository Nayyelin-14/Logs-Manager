"""Auth and user-management matrix tests.

Covers: login success/failure, disabled user, expired/garbage token, logout invalidation,
refresh restrictions, admin-only routes (viewer=403, anon=401), user creation validation,
self-delete and last-admin protection, cookies vs API key not interchangeable.
"""

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


def _get_admin_client():
    client = TestClient(app)
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    return client


def _get_viewer_a_client():
    client = TestClient(app)
    _login(client, VIEWER_A_EMAIL, VIEWER_A_PASSWORD)
    return client


def _get_viewer_b_client():
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
    """Login, cookies, and session management."""

    def test_login_success_sets_httponly_cookies(self):
        client = TestClient(app)
        res = _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
        assert res.status_code == 200, f"login failed: {res.text}"
        assert "accessToken" in client.cookies, "accessToken cookie not set"
        assert "refreshToken" in client.cookies, "refreshToken cookie not set"

    def test_login_wrong_password_returns_401_same_message(self):
        client = TestClient(app)
        res = _login(client, ADMIN_EMAIL, "WrongPassword!")
        assert res.status_code == 401, f"expected 401, got {res.status_code}: {res.text}"
        assert res.json()["detail"] == "Invalid credentials"

    def test_login_unknown_email_returns_401_same_message(self):
        client = TestClient(app)
        res = _login(client, "nonexistent@demo.local", "AnyPassword!")
        assert res.status_code == 401, f"expected 401, got {res.status_code}: {res.text}"
        assert res.json()["detail"] == "Invalid credentials"

    def test_login_disabled_user_returns_403(self):
        admin = _get_admin_client()
        email = _unique_email("disabled")
        create_res = admin.post(
            "/api/create-user",
            data={"username": "disableduser", "email": email, "tenant": "demoa", "role": "VIEWER", "password": "Password123!", "status": "INACTIVE"},
        )
        assert create_res.status_code == 201, f"create failed: {create_res.text}"
        
        test_client = TestClient(app)
        res = _login(test_client, email, "Password123!")
        assert res.status_code == 403, f"expected 403 for disabled user, got {res.status_code}: {res.text}"
        assert "not active" in res.json()["detail"].lower()

    def test_no_cookie_on_protected_route_returns_401(self):
        client = TestClient(app)
        res = client.get("/api/get-logs")
        assert res.status_code == 401, f"expected 401, got {res.status_code}: {res.text}"

    def test_garbage_token_returns_401(self):
        client = TestClient(app)
        client.cookies.clear()
        client.cookies.set("accessToken", "garbage.token.here")
        client.cookies.set("refreshToken", "garbage.refresh.here")
        res = client.get("/api/get-logs")
        assert res.status_code == 401, f"expected 401, got {res.status_code}: {res.text}"

    def test_expired_access_token_with_valid_refresh_refreshes(self):
        client = TestClient(app)
        _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
        
        refresh_token = client.cookies.get("refreshToken")
        assert refresh_token is not None, "refresh token not set"
        payload = decode_token(refresh_token, settings.REFRESH_TOKEN_SECRET)
        
        expired_payload = TokenPayload(user_id=payload["userId"], username=payload["username"], email=payload["email"], tenant=payload["tenant"], role=payload["role"])
        expired_access = _create_expired_access_token(expired_payload)
        
        # Clear and set only access token (keep valid refresh token)
        client.cookies.clear()
        client.cookies.set("accessToken", expired_access)
        client.cookies.set("refreshToken", refresh_token)
        
        res = client.get("/api/get-logs")
        assert res.status_code == 200, f"expected 200 after refresh, got {res.status_code}: {res.text}"

    def test_expired_refresh_token_returns_401(self):
        """Expired refresh token should return 401."""
        client = TestClient(app)
        _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
        
        refresh_token = client.cookies.get("refreshToken")
        assert refresh_token is not None, "refresh token not set"
        payload = decode_token(refresh_token, settings.REFRESH_TOKEN_SECRET)
        
        expired_payload = TokenPayload(user_id=payload["userId"], username=payload["username"], email=payload["email"], tenant=payload["tenant"], role=payload["role"])
        expired_refresh = _create_expired_refresh_token(expired_payload)
        expired_access = _create_expired_access_token(expired_payload)
        
        # Clear cookies first to avoid conflict, then set expired ones
        client.cookies.clear()
        client.cookies.set("accessToken", expired_access)
        client.cookies.set("refreshToken", expired_refresh)
        
        res = client.get("/api/get-logs")
        assert res.status_code == 401, f"expected 401, got {res.status_code}: {res.text}"

    def test_logout_invalidates_cookie(self):
        client = TestClient(app)
        _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
        assert client.get("/api/get-logs").status_code == 200
        
        _logout(client)
        
        res = client.get("/api/get-logs")
        assert res.status_code == 401, f"expected 401 after logout, got {res.status_code}: {res.text}"

    def test_access_token_not_accepted_as_refresh_token(self):
        client = TestClient(app)
        _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
        access_token = client.cookies.get("accessToken")
        
        client2 = TestClient(app)
        client2.cookies.clear()
        client2.cookies.set("accessToken", access_token)
        
        res = client2.get("/api/get-logs")
        assert res.status_code == 401, f"expected 401 without refresh token, got {res.status_code}"

    def test_disabled_user_cannot_refresh(self):
        admin = _get_admin_client()
        email = _unique_email("disabled2")
        create_res = admin.post("/api/create-user", data={"username": "disableduser2", "email": email, "tenant": "demoa", "role": "VIEWER", "password": "Password123!", "status": "ACTIVE"})
        assert create_res.status_code == 201
        
        client = TestClient(app)
        _login(client, email, "Password123!")
        assert client.get("/api/get-logs").status_code == 200
        
        user_id = create_res.json()["id"]
        admin.put("/api/update-user", data={"id": user_id, "status": "INACTIVE"})
        
        client2 = TestClient(app)
        for name, value in client.cookies.items():
            client2.cookies.set(name, value, domain="testserver")
        
        res = client2.get("/api/get-logs")
        assert res.status_code == 401, f"expected 401 for disabled user refresh, got {res.status_code}: {res.text}"

    def test_inactive_tenant_cannot_refresh(self):
        admin = _get_admin_client()
        email = _unique_email("tenantuser")
        create_res = admin.post("/api/create-user", data={"username": "tenantuser", "email": email, "tenant": "demob", "role": "VIEWER", "password": "Password123!"})
        assert create_res.status_code == 201
        
        client = TestClient(app)
        _login(client, email, "Password123!")
        assert client.get("/api/get-logs").status_code == 200
        
        admin.patch("/api/tenants/demob", json={"is_active": False})
        
        client2 = TestClient(app)
        for name, value in client.cookies.items():
            client2.cookies.set(name, value, domain="testserver")
        
        res = client2.get("/api/get-logs")
        assert res.status_code == 401, f"expected 401 for inactive tenant, got {res.status_code}: {res.text}"


class TestRoleChecks:
    """Every admin-only route: viewer=403, anonymous=401."""

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
    def test_viewer_gets_403_on_admin_routes(self, method, path, body):
        client = _get_viewer_a_client()
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
    def test_anonymous_gets_401_on_admin_routes(self, method, path, body):
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
    """Viewer isolation: viewerB sees only demob data."""

    def test_viewer_b_get_logs_forced_to_own_tenant(self):
        client = _get_viewer_b_client()
        res = client.get("/api/get-logs?tenant=demoa")
        assert res.status_code == 200
        logs = res.json()["logs"]
        for log in logs:
            assert log["tenant"] == "demob", f"viewerB saw tenant={log.get('tenant')}"

    def test_viewer_b_get_logs_tenant_all_returns_demob_only(self):
        client = _get_viewer_b_client()
        res = client.get("/api/get-logs?tenant=all")
        assert res.status_code == 200
        logs = res.json()["logs"]
        for log in logs:
            assert log["tenant"] == "demob", f"viewerB with ?tenant=all saw tenant={log.get('tenant')}"

    def test_viewer_b_get_alerts_forced_to_own_tenant(self):
        client = _get_viewer_b_client()
        res = client.get("/api/get-alerts?tenant=demoa")
        assert res.status_code == 200
        alerts = res.json()["alerts"]
        for alert in alerts:
            assert alert["tenant"] == "demob", f"viewerB saw alert tenant={alert.get('tenant')}"

    def test_viewer_b_dashboard_tenants_list_only_demob(self):
        client = _get_viewer_b_client()
        res = client.get("/api/dashboard")
        assert res.status_code == 200
        tenants = res.json().get("tenants", [])
        tenant_names = [t.get("tenant") for t in tenants]
        assert tenant_names == ["demob"], f"expected [demob], got {tenant_names}"

    def test_viewer_b_cannot_patch_demoa_alert(self):
        admin = _get_admin_client()
        res = admin.get("/api/get-alerts?tenant=demoa&limit=1")
        assert res.status_code == 200
        alerts = res.json()["alerts"]
        if alerts:
            alert_id = alerts[0]["id"]
            viewer_b = _get_viewer_b_client()
            res = viewer_b.patch(f"/api/alerts/{alert_id}", json={"status": "resolved"})
            assert res.status_code == 403, f"expected 403, got {res.status_code}: {res.text}"

    def test_viewer_b_cannot_delete_demoa_log(self):
        admin = _get_admin_client()
        res = admin.get("/api/get-logs?tenant=demoa&limit=1")
        assert res.status_code == 200
        logs = res.json()["logs"]
        if logs:
            log_id = logs[0]["id"]
            viewer_b = _get_viewer_b_client()
            res = viewer_b.delete(f"/api/delete-log/{log_id}")
            assert res.status_code == 403, f"expected 403, got {res.status_code}: {res.text}"

    def test_viewer_a_sees_demoa(self):
        client = _get_viewer_a_client()
        res = client.get("/api/get-logs")
        assert res.status_code == 200
        logs = res.json()["logs"]
        for log in logs:
            assert log["tenant"] == "demoa", f"viewerA saw tenant={log.get('tenant')}"

    def test_admin_sees_both_tenants(self):
        admin = _get_admin_client()
        for tenant in ("demoa", "demob"):
            res = admin.get(f"/api/get-logs?tenant={tenant}")
            assert res.status_code == 200, f"Expected 200 for tenant={tenant}, got {res.status_code}: {res.text}"
            logs = res.json()["logs"]
            assert len(logs) > 0, f"Expected non-empty page for tenant={tenant}"
            for log in logs:
                assert log["tenant"] == tenant, f"Expected tenant={tenant}, got {log.get('tenant')}"


class TestUserManagement:
    """Admin user creation and management."""

    def test_create_viewer_with_tenant_returns_201(self):
        admin = _get_admin_client()
        email = _unique_email("newviewer")
        res = admin.post("/api/create-user", data={"username": "newviewer", "email": email, "tenant": "demoa", "role": "VIEWER", "password": "Password123!"})
        assert res.status_code == 201, f"expected 201, got {res.status_code}: {res.text}"
        data = res.json()
        assert data["tenant"] == "demoa"
        assert data["role"] == "VIEWER"
        assert "password" not in data
        assert "hash" not in str(data).lower()

    def test_create_viewer_without_tenant_returns_422(self):
        admin = _get_admin_client()
        res = admin.post("/api/create-user", data={"username": "noviewer", "email": _unique_email("noviewer"), "tenant": "", "role": "VIEWER", "password": "Password123!"})
        assert res.status_code == 422, f"expected 422, got {res.status_code}: {res.text}"

    def test_duplicate_email_returns_409(self):
        admin = _get_admin_client()
        email = _unique_email("dup")
        admin.post("/api/create-user", data={"username": "dup1", "email": email, "tenant": "demoa", "role": "VIEWER", "password": "Password123!"})
        res = admin.post("/api/create-user", data={"username": "dup2", "email": email, "tenant": "demoa", "role": "VIEWER", "password": "Password123!"})
        assert res.status_code == 409, f"expected 409, got {res.status_code}: {res.text}"

    def test_response_never_contains_password_or_hash(self):
        admin = _get_admin_client()
        email = _unique_email("pwdcheck")
        res = admin.post("/api/create-user", data={"username": "pwdcheck", "email": email, "tenant": "demoa", "role": "VIEWER", "password": "Password123!"})
        assert res.status_code == 201
        data = res.json()
        for key in data:
            assert "password" not in key.lower()
            assert "hash" not in key.lower()
        res2 = admin.get("/api/get-users")
        assert res2.status_code == 200
        for user in res2.json()["usersList"]:
            assert "password" not in user
            assert "hash" not in str(user).lower()

    def test_admin_cannot_delete_self(self):
        """BUG: admin can delete themselves. Should return 403."""
        admin = _get_admin_client()
        res = admin.get("/api/auth/auth-check")
        assert res.status_code == 200
        admin_id = res.json()["user"]["id"]
        
        res = admin.delete(f"/api/delete-user/{admin_id}")
        assert res.status_code == 403, f"BUG: expected 403, got {res.status_code}: {res.text}"

    def test_new_user_can_login_and_sees_only_their_tenant(self):
        admin = _get_admin_client()
        email = _unique_email("newviewer2")
        create_res = admin.post("/api/create-user", data={"username": "newviewer2", "email": email, "tenant": "demoa", "role": "VIEWER", "password": "NewPass123!"})
        assert create_res.status_code == 201
        
        client = TestClient(app)
        res = _login(client, email, "NewPass123!")
        assert res.status_code == 200
        
        res = client.get("/api/get-logs")
        assert res.status_code == 200
        logs = res.json()["logs"]
        for log in logs:
            assert log["tenant"] == "demoa", f"new viewer saw tenant={log.get('tenant')}"


class TestCredentialInterchange:
    """Cookie and API key are not interchangeable."""

    def test_viewer_cookie_on_ingest_returns_401(self):
        viewer = _get_viewer_a_client()
        res = viewer.post("/api/ingest", json={"source": "api", "event_type": "test"})
        assert res.status_code == 401, f"expected 401, got {res.status_code}: {res.text}"

    def test_api_key_on_get_logs_returns_401(self):
        client = TestClient(app)
        res = client.get("/api/get-logs", headers={"X-API-Key": "fake-key"})
        assert res.status_code == 401, f"expected 401, got {res.status_code}: {res.text}"

    def test_api_key_on_admin_route_returns_401(self):
        client = TestClient(app)
        res = client.get("/api/get-users", headers={"X-API-Key": "fake-key"})
        assert res.status_code == 401, f"expected 401, got {res.status_code}: {res.text}"


class TestRefreshRestrictions:
    """Refresh token specific restrictions."""

    def test_refresh_token_works_for_token_refresh(self):
        client = TestClient(app)
        _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
        
        refresh_token = client.cookies.get("refreshToken")
        assert refresh_token is not None, "refresh token not set"
        payload = decode_token(refresh_token, settings.REFRESH_TOKEN_SECRET)
        
        expired_payload = TokenPayload(user_id=payload["userId"], username=payload["username"], email=payload["email"], tenant=payload["tenant"], role=payload["role"])
        expired_access = _create_expired_access_token(expired_payload)
        client.cookies.set("accessToken", expired_access, domain="testserver")
        
        res = client.get("/api/get-logs")
        assert res.status_code == 200, f"expected 200 after refresh, got {res.status_code}: {res.text}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
