"""Search and filtering acceptance tests.

Events are ingested through the real HTTP API, then found through the search
endpoint using the filters the dashboard and log table rely on: free text,
source, event type, severity band, user, IP, and time range.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from conftest import ADMIN_EMAIL, ADMIN_PASSWORD, login


def _headers(api_key: str) -> dict:
    return {"X-API-Key": api_key, "Content-Type": "application/json"}


def _ingest(client, api_key, event: dict) -> dict:
    response = client.post("/api/ingest", json=event, headers=_headers(api_key))
    assert response.status_code == 200, response.text
    return response.json()


def _search_pair(client, api_key):
    run = uuid.uuid4().hex[:10]
    now = datetime.now(timezone.utc)

    alpha = {
        "source": "aws",
        "event_type": f"search_alpha_{run}",
        "user": f"search_alice_{run}",
        "src_ip": "198.51.100.61",
        "severity": 8,
        "action": "LOGIN",
        "@timestamp": now.isoformat(),
    }
    beta = {
        "source": "api",
        "event_type": f"search_beta_{run}",
        "user": f"search_bob_{run}",
        "src_ip": "198.51.100.62",
        "severity": 3,
        "action": "DENY",
        "@timestamp": (now - timedelta(hours=2)).isoformat(),
    }

    alpha_id = _ingest(client, api_key, alpha)["eventId"]
    beta_id = _ingest(client, api_key, beta)["eventId"]
    return run, now, alpha_id, beta_id


def test_search_filters_by_text_source_severity_user_and_type(client, api_key):
    run, _now, alpha_id, beta_id = _search_pair(client, api_key)
    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)

    response = client.get("/api/get-logs", params={"search": f"search_alpha_{run}"})
    assert response.status_code == 200, response.text
    ids = {log["id"] for log in response.json()["logs"]}
    assert ids == {alpha_id}

    response = client.get(
        "/api/get-logs",
        params={"source": "aws", "severity": "high", "event_type": f"search_alpha_{run}"},
    )
    assert response.status_code == 200, response.text
    ids = {log["id"] for log in response.json()["logs"]}
    assert ids == {alpha_id}

    response = client.get("/api/get-logs", params={"user": f"search_alice_{run}"})
    assert response.status_code == 200, response.text
    ids = {log["id"] for log in response.json()["logs"]}
    assert ids == {alpha_id}

    response = client.get("/api/get-logs", params={"src_ip": "198.51.100.62"})
    assert response.status_code == 200, response.text
    ids = {log["id"] for log in response.json()["logs"]}
    assert ids == {beta_id}

    response = client.get("/api/get-logs", params={"tenant": "demoa", "limit": 1})
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["logs"]) == 1
    assert body["newCursor"] is not None, "pagination cursor should be returned"


def test_search_filters_by_time_range(client, api_key):
    run, now, alpha_id, beta_id = _search_pair(client, api_key)
    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)

    response = client.get(
        "/api/get-logs",
        params={
            "search": f"search_alpha_{run}",
            "from": (now - timedelta(minutes=30)).isoformat(),
            "to": (now + timedelta(minutes=30)).isoformat(),
        },
    )
    assert response.status_code == 200, response.text
    ids = {log["id"] for log in response.json()["logs"]}
    assert ids == {alpha_id}, "the event outside the requested window must be excluded"
    assert beta_id not in ids
