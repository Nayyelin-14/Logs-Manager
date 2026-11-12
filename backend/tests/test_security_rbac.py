"""Authentication, authorization, tenant isolation, and request hardening.

These are the boundaries the assignment calls out explicitly: viewers never see
another tenant, admin routes are admin-only, API keys are tenant-bound, CSRF and
CORS reject untrusted browsers, and outbound webhooks cannot target internal
addresses.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.security import (
    TokenPayload,
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.core.webhook_security import (
    WebhookUrlError,
    is_safe_webhook_url,
    validate_webhook_url,
)
from app.main import app

from conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    DEMOA_API_KEY,
    VIEWER_A_EMAIL,
    VIEWER_A_PASSWORD,
    VIEWER_B_EMAIL,
    VIEWER_B_PASSWORD,
    login,
)

settings = get_settings()


def _headers(api_key: str) -> dict:
    return {"X-API-Key": api_key, "Content-Type": "application/json"}


def _expired_access_token(payload: TokenPayload) -> str:
    token = payload.to_dict()
    token["exp"] = int((datetime.now(timezone.utc) - timedelta(minutes=60)).timestamp())
    return jwt.encode(token, settings.ACCESS_TOKEN_SECRET, algorithm=settings.JWT_ALGORITHM)


def _expired_refresh_token(payload: TokenPayload) -> str:
    token = payload.to_dict()
    token["exp"] = int((datetime.now(timezone.utc) - timedelta(days=60)).timestamp())
    return jwt.encode(token, settings.REFRESH_TOKEN_SECRET, algorithm=settings.JWT_ALGORITHM)


def test_login_sets_cookies_and_logout_invalidates_the_session(client):
    response = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    assert response.status_code == 200
    assert "accessToken" in client.cookies
    assert "refreshToken" in client.cookies
    assert client.get("/api/get-logs").status_code == 200

    client.post("/api/auth/logout")
    assert client.get("/api/get-logs").status_code == 401

    hashed = hash_password("Password123!")
    assert hashed.startswith("$2b$")
    assert verify_password("Password123!", hashed)
    assert not verify_password("wrong", hashed)


def test_login_rejects_bad_credentials_and_inactive_users(client):
    response = client.post(
        "/api/auth/login", json={"email": ADMIN_EMAIL, "password": "WrongPassword!"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"

    response = client.post(
        "/api/auth/login",
        json={"email": "nonexistent@demo.local", "password": "AnyPassword!"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"

    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    email = f"inactive_{uuid.uuid4().hex[:8]}@demo.local"
    created = client.post(
        "/api/create-user",
        json={
            "username": "inactive-user",
            "email": email,
            "tenant": "demoa",
            "role": "VIEWER",
            "status": "INACTIVE",
            "password": "Password123!",
        },
    )
    assert created.status_code == 201, created.text
    assert "password" not in created.json()
    assert "password_hash" not in created.json()

    response = client.post(
        "/api/auth/login", json={"email": email, "password": "Password123!"}
    )
    assert response.status_code == 403, response.text

    # Per-email lockout and the route-level limiter remain part of the
    # security boundary even though the dedicated rate-limit suite was removed.
    import time

    from app.api.routes.auth import (
        _FAILED_LOGIN_TRACKER,
        _clear_failed_logins,
        _is_locked_out,
        _record_failed_login,
        login_limiter,
    )

    _FAILED_LOGIN_TRACKER.clear()
    lockout_email = "lockout@demo.local"
    for _ in range(4):
        _record_failed_login(lockout_email)
        assert _is_locked_out(lockout_email)[0] is False
    _record_failed_login(lockout_email)
    locked, retry_after = _is_locked_out(lockout_email)
    assert locked and retry_after > 0

    _FAILED_LOGIN_TRACKER[lockout_email]["first_failed_at"] = time.time() - (
        get_settings().LOGIN_LOCKOUT_MINUTES * 60 + 1
    )
    assert _is_locked_out(lockout_email)[0] is False
    assert lockout_email not in _FAILED_LOGIN_TRACKER

    _record_failed_login(lockout_email)
    _clear_failed_logins(lockout_email)
    assert lockout_email not in _FAILED_LOGIN_TRACKER
    assert login_limiter is not None and login_limiter.enabled


def test_repeated_bad_logins_return_429_lockout(client):
    """Assignment requirement: repeated failed logins are rate limited."""
    email = f"lockout-{uuid.uuid4().hex[:8]}@demo.local"
    statuses = [
        client.post(
            "/api/auth/login", json={"email": email, "password": "WrongPassword!"}
        ).status_code
        for _ in range(5)
    ]

    assert statuses[:4] == [401, 401, 401, 401], statuses
    assert statuses[4] in (423, 429), statuses


def test_register_route_is_absent(client):
    """Assignment requirement: users are provisioned by an admin, not self-registration."""
    response = client.post(
        "/api/auth/register", json={"email": "new@demo.local", "password": "Password123!"}
    )
    assert response.status_code in (404, 405), response.text


def test_expired_access_token_refreshes_but_expired_refresh_is_rejected(client):
    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    refresh_token = client.cookies.get("refreshToken")
    assert refresh_token is not None

    payload = decode_token(refresh_token, settings.REFRESH_TOKEN_SECRET)
    token_payload = TokenPayload(
        user_id=payload["userId"],
        username=payload["username"],
        email=payload["email"],
        tenant=payload["tenant"],
        role=payload["role"],
    )
    assert create_access_token(token_payload)

    client.cookies.clear()
    client.cookies.set("accessToken", _expired_access_token(token_payload))
    client.cookies.set("refreshToken", refresh_token)
    assert client.get("/api/get-logs").status_code == 200

    client.cookies.clear()
    client.cookies.set("accessToken", _expired_access_token(token_payload))
    client.cookies.set("refreshToken", _expired_refresh_token(token_payload))
    assert client.get("/api/get-logs").status_code == 401


def test_admin_routes_require_admin_and_authentication(client):
    login(client, VIEWER_A_EMAIL, VIEWER_A_PASSWORD)
    routes = [
        ("get", "/api/get-users", None),
        ("get", "/api/get-rules", None),
        ("get", "/api/tenants", None),
        (
            "post",
            "/api/create-user",
            {
                "username": "x",
                "email": "x@example.com",
                "tenant": "demoa",
                "role": "VIEWER",
                "password": "Password123!",
            },
        ),
        (
            "post",
            "/api/create-alertRule",
            {
                "name": "x",
                "tenant": "demoa",
                "conditions": [{"type": "event_type", "value": "x"}],
            },
        ),
    ]
    for method, path, body in routes:
        response = (
            getattr(client, method)(path)
            if body is None
            else getattr(client, method)(path, json=body)
        )
        assert response.status_code == 403, f"viewer {method.upper()} {path}: {response.text}"

    anonymous = TestClient(app)
    for method, path, body in routes:
        response = (
            getattr(anonymous, method)(path)
            if body is None
            else getattr(anonymous, method)(path, json=body)
        )
        assert response.status_code == 401, f"anonymous {method.upper()} {path}: {response.text}"


def test_viewer_reads_are_tenant_scoped(client, api_key_demob):
    marker = f"tenant-scope-{uuid.uuid4().hex}"
    src_ip = "198.51.100.90"
    response = client.post(
        "/api/ingest",
        json={
            "source": "api",
            "tenant": "demob",
            "event_type": marker,
            "user": marker,
            "src_ip": src_ip,
            "severity": 4,
        },
        headers=_headers(api_key_demob),
    )
    assert response.status_code == 200, response.text
    event_id = response.json()["eventId"]

    login(client, VIEWER_A_EMAIL, VIEWER_A_PASSWORD)
    logs = client.get("/api/get-logs", params={"src_ip": src_ip}).json()["logs"]
    assert all(log["tenant"] == "demoa" for log in logs)
    assert all(log["id"] != event_id for log in logs)

    forced = client.get("/api/get-logs", params={"tenant": "demob", "limit": 100}).json()
    assert all(log["tenant"] == "demoa" for log in forced["logs"])
    assert forced["total"] == len(forced["logs"])

    dashboard = client.get("/api/dashboard", params={"tenant": "demob"}).json()
    assert dashboard["tenant"] == "demoa"
    assert client.get(f"/api/events/{event_id}").status_code == 404

    login(client, VIEWER_B_EMAIL, VIEWER_B_PASSWORD)
    detail = client.get(f"/api/events/{event_id}")
    assert detail.status_code == 200
    assert detail.json()["tenant"] == "demob"


def test_viewer_cannot_mutate_alerts_rules_logs_or_users(client):
    login(client, VIEWER_A_EMAIL, VIEWER_A_PASSWORD)

    response = client.patch("/api/alerts/does-not-exist", json={"status": "resolved"})
    assert response.status_code == 403, response.text

    response = client.delete("/api/delete-log/does-not-exist")
    assert response.status_code == 403, response.text

    response = client.put("/api/update-rule/does-not-exist", json={"name": "evil"})
    assert response.status_code == 403, response.text

    response = client.patch("/api/rules/does-not-exist/enabled", params={"enabled": "false"})
    assert response.status_code == 403, response.text

    response = client.delete("/api/delete-rule/does-not-exist")
    assert response.status_code == 403, response.text

    response = client.put("/api/update-user", json={"id": 999, "username": "evil"})
    assert response.status_code == 403, response.text

    response = client.delete("/api/delete-user/999")
    assert response.status_code == 403, response.text


def test_api_key_tenant_binding_secrecy_and_rotation(client, api_key_demoa):
    response = client.post(
        "/api/ingest",
        json={"source": "api", "event_type": "cross_tenant_probe", "tenant": "demob"},
        headers=_headers(DEMOA_API_KEY),
    )
    assert response.status_code == 403, response.text

    response = client.post(
        "/api/ingest",
        json={"source": "api", "event_type": "missing_key_probe"},
    )
    assert response.status_code == 401, response.text

    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    tenants_response = client.get("/api/tenants")
    assert tenants_response.status_code == 200
    assert "api_key" not in tenants_response.text
    assert DEMOA_API_KEY not in tenants_response.text

    tenant_name = f"rotate-{uuid.uuid4().hex[:8]}"
    created = client.post("/api/tenants", json={"name": tenant_name, "is_active": True})
    assert created.status_code == 201, created.text
    original_key = created.json()["api_key"]

    rotated = client.post(f"/api/tenants/{tenant_name}/rotate-key")
    assert rotated.status_code == 200, rotated.text
    rotated_key = rotated.json()["api_key"]
    assert rotated_key != original_key

    payload = {
        "source": "api",
        "tenant": tenant_name,
        "event_type": "rotation_probe",
        "severity": 3,
    }
    assert client.post(
        "/api/ingest", json=payload, headers=_headers(rotated_key)
    ).status_code == 200
    assert client.post(
        "/api/ingest", json=payload, headers=_headers(original_key)
    ).status_code == 401


def test_csrf_and_cors_boundaries():
    body = {
        "tenant": "demoa",
        "source": "api",
        "event_type": "csrf_probe",
        "severity": 3,
    }

    with TestClient(app) as csrf_client:
        login(csrf_client, ADMIN_EMAIL, ADMIN_PASSWORD)
        csrf_client.headers.pop("X-XSRF-TOKEN", None)
        rejected = csrf_client.post(
            "/api/ingest/ui", json=body, headers={"Origin": "http://localhost:5173"}
        )
        assert rejected.status_code == 403, rejected.text

    with TestClient(app) as trusted_client:
        login(trusted_client, ADMIN_EMAIL, ADMIN_PASSWORD)
        accepted = trusted_client.post(
            "/api/ingest/ui", json=body, headers={"Origin": "http://localhost:5173"}
        )
        assert accepted.status_code == 200, accepted.text

    with TestClient(app) as untrusted_client:
        login(untrusted_client, ADMIN_EMAIL, ADMIN_PASSWORD)
        rejected = untrusted_client.post(
            "/api/ingest/ui", json=body, headers={"Origin": "https://evil.example"}
        )
        assert rejected.status_code == 403
        assert rejected.json()["detail"] == "Untrusted origin"

    with TestClient(app) as preflight_client:
        allowed = preflight_client.options(
            "/api/ingest/ui",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,x-xsrf-token",
            },
        )
        assert allowed.status_code == 200
        assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"
        assert allowed.headers.get("access-control-allow-credentials") == "true"

        blocked = preflight_client.options(
            "/api/ingest/ui",
            headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
        )
        assert blocked.headers.get("access-control-allow-origin") is None


def test_webhook_ssrf_blocks_internal_targets():
    blocked = [
        "http://127.0.0.1/webhook",
        "http://169.254.169.254/latest/meta-data",
        "http://10.0.0.1/webhook",
        "http://localhost/webhook",
        "file:///etc/passwd",
    ]
    for url in blocked:
        with pytest.raises(WebhookUrlError):
            validate_webhook_url(url)

    assert is_safe_webhook_url("http://127.0.0.1/webhook") is False


def test_tenant_lifecycle_validation(client):
    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)

    for bad_name in ["all", "a", "x;y", ""]:
        response = client.post("/api/tenants", json={"name": bad_name, "is_active": True})
        assert response.status_code == 422, f"{bad_name!r}: {response.text}"

    response = client.post("/api/tenants", json={"name": "demoa", "is_active": True})
    assert response.status_code == 409, response.text

    response = client.patch("/api/tenants/demob", json={"is_active": False})
    assert response.status_code == 200
    assert response.json()["is_active"] is False
    response = client.patch("/api/tenants/demob", json={"is_active": True})
    assert response.status_code == 200
    assert response.json()["is_active"] is True
    assert client.patch("/api/tenants/missing-tenant", json={"is_active": False}).status_code == 404

    # User lifecycle through the documented JSON body and cursor pagination.
    email = f"lifecycle_{uuid.uuid4().hex[:8]}@demo.local"
    created = client.post(
        "/api/create-user",
        json={
            "username": "lifecycle-user",
            "email": email,
            "tenant": "demoa",
            "role": "VIEWER",
            "status": "ACTIVE",
            "password": "Password123!",
        },
    )
    assert created.status_code == 201, created.text
    user_id = created.json()["id"]
    assert created.json()["tenant"] == "demoa"

    duplicate = client.post(
        "/api/create-user",
        json={
            "username": "lifecycle-user",
            "email": email,
            "tenant": "demoa",
            "role": "VIEWER",
            "password": "Password123!",
        },
    )
    assert duplicate.status_code == 409, duplicate.text
    missing_password = client.post(
        "/api/create-user",
        json={"username": "x", "email": "x@example.test", "tenant": "demoa"},
    )
    assert missing_password.status_code == 422, missing_password.text

    listing = client.get("/api/get-users", params={"search": "lifecycle"})
    assert listing.status_code == 200, listing.text
    assert any(row["id"] == user_id for row in listing.json()["usersList"])
    assert client.get("/api/get-users", params={"role": "bogus"}).status_code == 422
    assert client.get("/api/get-users", params={"status": "bogus"}).status_code == 422

    first_page = client.get("/api/get-users", params={"limit": 1})
    assert first_page.status_code == 200, first_page.text
    next_cursor = first_page.json()["newCursor"]
    assert next_cursor is not None
    second_page = client.get("/api/get-users", params={"limit": 1, "cursor": next_cursor})
    assert second_page.status_code == 200, second_page.text
    assert second_page.json()["usersList"]

    updated = client.put(
        "/api/update-user",
        json={"id": user_id, "username": "renamed-user", "status": "INACTIVE"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["status"] == "INACTIVE"
    assert updated.json()["username"] == "renamed-user"
    assert client.put("/api/update-user", json={"id": "not-an-int"}).status_code == 422
    assert client.put("/api/update-user", json={"id": 999999, "username": "x"}).status_code == 404

    moved = client.put("/api/update-user", json={"id": user_id, "tenant": "demob"})
    assert moved.status_code == 200, moved.text
    assert moved.json()["tenant"] == "demob"
    assert client.delete(f"/api/delete-user/{user_id}").status_code == 200
    assert client.delete(f"/api/delete-user/{user_id}").status_code == 404

    all_data = client.get("/api/get-all-data")
    assert all_data.status_code == 200, all_data.text
    assert {"allLogs", "allUsers", "allAlerts", "allRules", "tenants"} <= set(
        all_data.json()["data"]
    )
    scoped_data = client.get("/api/get-all-data", params={"tenant": "demoa"})
    assert scoped_data.status_code == 200, scoped_data.text
    assert "tenants" not in scoped_data.json()["data"]

    login(client, VIEWER_B_EMAIL, VIEWER_B_PASSWORD)
    response = client.post("/api/tenants", json={"name": "viewer-tenant", "is_active": True})
    assert response.status_code == 403, response.text
