"""Deployment and operations acceptance tests.

These are the checks a reviewer or uptime monitor uses to decide whether the
service is usable: liveness, readiness (database and Redis), the deployed
version, and the feature-flag dependency used to gate optional features.
"""

from __future__ import annotations

import os


def test_health_and_readiness_report_dependencies(client):
    health = client.get("/healthz")
    assert health.status_code == 200, health.text
    assert health.json()["status"] == "ok"
    assert health.json()["database"] == "connected"

    ready = client.get("/ready")
    assert ready.status_code == 200, ready.text
    body = ready.json()
    assert body["status"] == "ready"
    assert body["database"] == "connected"
    assert body["redis"] == "connected"


def test_version_identifies_the_deployment(client):
    response = client.get("/version")
    assert response.status_code == 200, response.text
    body = response.json()
    assert "git_sha" in body
    assert "app_version" in body


def test_feature_flag_gates_optional_routes(client):
    os.environ.pop("FEATURE_TEST_FLAG_ENABLED", None)
    try:
        disabled = client.get("/features/test-flagged")
        assert disabled.status_code == 404, disabled.text

        os.environ["FEATURE_TEST_FLAG_ENABLED"] = "true"
        enabled = client.get("/features/test-flagged")
        assert enabled.status_code == 200, enabled.text
        assert enabled.json() == {"status": "ok", "feature": "test_flag"}
    finally:
        os.environ.pop("FEATURE_TEST_FLAG_ENABLED", None)
