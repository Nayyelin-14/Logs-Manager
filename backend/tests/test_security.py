"""Security and authorization acceptance tests.

Covers the boundaries that matter for the assignment and the product:

* Viewers only see their own tenant (logs, dashboards, alerts, event detail).
* Viewers cannot use admin routes or mutate another tenant's data.
* Anonymous requests are rejected.
* API keys are tenant-bound, are never listed, and rotation invalidates the old key.
* A small representative set of hardening checks (CSRF double-submit and
  outbound webhook SSRF protection).
"""

from __future__ import annotations

import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.webhook_security import WebhookUrlError, is_safe_webhook_url, validate_webhook_url
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


def _headers(api_key: str) -> dict:
    return {"X-API-Key": api_key, "Content-Type": "application/json"}


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

    forced = client.get(
        "/api/get-logs", params={"tenant": "demob", "limit": 100}
    ).json()["logs"]
    assert all(log["tenant"] == "demoa" for log in forced)

    dashboard = client.get("/api/dashboard", params={"tenant": "demob"}).json()
    assert dashboard["tenant"] == "demoa"
    assert marker not in json.dumps(dashboard)

    assert client.get(f"/api/events/{event_id}").status_code == 404

    login(client, VIEWER_B_EMAIL, VIEWER_B_PASSWORD)
    assert client.get(f"/api/events/{event_id}").status_code == 200


def test_viewer_cannot_use_admin_routes(viewer_a_client):
    routes = [
        ("get", "/api/get-users", None),
        ("get", "/api/get-rules", None),
        (
            "post",
            "/api/create-alertRule",
            {
                "name": "viewer-boundary",
                "tenant": "demoa",
                "conditions": [{"type": "event_type", "value": "viewer_probe"}],
            },
        ),
        ("get", "/api/tenants", None),
    ]

    for method, path, body in routes:
        if body is None:
            response = getattr(viewer_a_client, method)(path)
        else:
            response = getattr(viewer_a_client, method)(path, json=body)
        assert response.status_code == 403, f"{method.upper()} {path}: {response.text}"


def test_anonymous_requests_are_rejected(client):
    for path in (
        "/api/get-logs",
        "/api/get-alerts",
        "/api/dashboard",
        "/api/get-users",
    ):
        response = client.get(path)
        assert response.status_code == 401, f"GET {path}: {response.text}"


def test_viewer_cannot_mutate_other_tenant_data(viewer_a_client):
    response = viewer_a_client.patch(
        "/api/alerts/does-not-exist", json={"status": "resolved"}
    )
    assert response.status_code == 403, response.text

    response = viewer_a_client.delete("/api/delete-log/does-not-exist")
    assert response.status_code == 403, response.text


def test_api_key_tenant_binding_secrecy_and_rotation(
    admin_client, api_key_demoa, api_key_demob
):
    cross_tenant = admin_client.post(
        "/api/ingest",
        json={
            "source": "api",
            "tenant": "demob",
            "event_type": "cross_tenant_probe",
            "user": "probe",
            "severity": 3,
        },
        headers=_headers(DEMOA_API_KEY),
    )
    assert cross_tenant.status_code == 403, cross_tenant.text

    missing_key = admin_client.post(
        "/api/ingest",
        json={"source": "api", "event_type": "missing_key_probe", "user": "probe"},
    )
    assert missing_key.status_code == 401, missing_key.text

    unknown_key = admin_client.post(
        "/api/ingest",
        json={"source": "api", "event_type": "unknown_key_probe", "user": "probe"},
        headers=_headers("unknown-key-that-does-not-exist"),
    )
    assert unknown_key.status_code == 401, unknown_key.text

    tenants_response = admin_client.get("/api/tenants")
    assert tenants_response.status_code == 200, tenants_response.text
    body = tenants_response.text
    assert "api_key" not in body, "tenant listing must not expose key material"
    assert "api_key_hash" not in body
    assert DEMOA_API_KEY not in body

    tenant_name = f"rotate-{uuid.uuid4().hex[:8]}"
    created = admin_client.post(
        "/api/tenants", json={"name": tenant_name, "is_active": True}
    )
    assert created.status_code == 201, created.text
    original_key = created.json()["api_key"]

    rotated = admin_client.post(f"/api/tenants/{tenant_name}/rotate-key")
    assert rotated.status_code == 200, rotated.text
    rotated_key = rotated.json()["api_key"]
    assert rotated_key != original_key

    payload = {
        "source": "api",
        "tenant": tenant_name,
        "event_type": "rotation_probe",
        "user": "rotation",
        "severity": 3,
    }
    assert (
        admin_client.post(
            "/api/ingest", json=payload, headers=_headers(rotated_key)
        ).status_code
        == 200
    )
    assert (
        admin_client.post(
            "/api/ingest", json=payload, headers=_headers(original_key)
        ).status_code
        == 401
    )


def test_csrf_required_for_cookie_authenticated_mutations():
    with TestClient(app) as csrf_client:
        login(csrf_client, ADMIN_EMAIL, ADMIN_PASSWORD)
        body = {
            "tenant": "demoa",
            "source": "api",
            "event_type": "csrf_probe",
            "user": "csrf",
            "severity": 3,
        }

        accepted = csrf_client.post(
            "/api/ingest/ui",
            json=body,
            headers={"Origin": "http://localhost:5173"},
        )
        assert accepted.status_code == 200, accepted.text

        csrf_client.headers.pop("X-XSRF-TOKEN", None)
        rejected = csrf_client.post(
            "/api/ingest/ui",
            json={**body, "event_type": "csrf_probe_without_token"},
            headers={"Origin": "http://localhost:5173"},
        )
        assert rejected.status_code == 403, rejected.text


def test_csrf_rejects_untrusted_origin_even_with_valid_token():
    with TestClient(app) as origin_client:
        login(origin_client, ADMIN_EMAIL, ADMIN_PASSWORD)
        response = origin_client.post(
            "/api/ingest/ui",
            json={
                "tenant": "demoa",
                "source": "api",
                "event_type": "csrf_origin_probe",
                "severity": 3,
            },
            headers={"Origin": "https://evil.example"},
        )
        assert response.status_code == 403, response.text
        assert response.json()["detail"] == "Untrusted origin"


def test_cors_preflight_allows_trusted_origin_only():
    with TestClient(app) as preflight_client:
        allowed = preflight_client.options(
            "/api/ingest/ui",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,x-xsrf-token",
            },
        )
        assert allowed.status_code == 200, allowed.text
        assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"
        assert allowed.headers.get("access-control-allow-credentials") == "true"

        blocked = preflight_client.options(
            "/api/ingest/ui",
            headers={
                "Origin": "https://evil.example",
                "Access-Control-Request-Method": "POST",
            },
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
