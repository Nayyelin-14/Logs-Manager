"""Health, readiness, version, and feature-flag endpoints."""

from __future__ import annotations


def test_healthz_and_health_liveness_report_database(client):
    for path in ("/healthz", "/health"):
        response = client.get(path)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "ok"
        assert body["database"] == "connected"
        assert isinstance(body["uptime"], int)
        assert body["timestamp"].endswith("Z")

    version = client.get("/version")
    assert version.status_code == 200, version.text
    assert set(version.json()) == {"app_version", "git_sha"}
    assert version.json()["app_version"]


def test_readiness_checks_database_and_redis(client):
    response = client.get("/ready")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ready"
    assert body["database"] == "connected"
    assert body["redis"] == "connected"


def test_feature_flags_are_hidden_until_enabled(client, monkeypatch):
    monkeypatch.delenv("FEATURE_TEST_FLAG_ENABLED", raising=False)
    response = client.get("/features/test-flagged")
    assert response.status_code == 404, response.text

    monkeypatch.setenv("FEATURE_TEST_FLAG_ENABLED", "true")
    listing = client.get("/features")
    assert listing.status_code == 200
    assert listing.json()["features"]["test_flag"] is True

    response = client.get("/features/test-flagged")
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "ok", "feature": "test_flag"}
