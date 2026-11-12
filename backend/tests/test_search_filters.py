"""Search filters used by the log table.

Every event is ingested through the public API first, then found through
``/api/events`` using the filters the UI sends: free text, source, event type,
severity band, time range, sort order, and server-side tenant scope.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    VIEWER_A_EMAIL,
    VIEWER_A_PASSWORD,
    login,
)


def _headers(api_key: str) -> dict:
    return {"X-API-Key": api_key, "Content-Type": "application/json"}


def _ingest(client, api_key: str, event: dict) -> dict:
    response = client.post("/api/ingest", json=event, headers=_headers(api_key))
    assert response.status_code == 200, response.text
    return response.json()


def _search(client, params: dict) -> list[dict]:
    response = client.get("/api/events", params=params)
    assert response.status_code == 200, response.text
    return response.json()["logs"]


def test_free_text_user_and_ip_search(client, api_key):
    run = uuid.uuid4().hex[:10]
    alpha_user = f"search_alice_{run}"
    beta_user = f"search_bob_{run}"
    alpha_ip = "198.51.100.61"
    beta_ip = "198.51.100.62"

    _ingest(
        client,
        api_key,
        {
            "source": "aws",
            "event_type": f"search_alpha_{run}",
            "user": alpha_user,
            "src_ip": alpha_ip,
            "severity": 8,
            "action": "LOGIN",
        },
    )
    _ingest(
        client,
        api_key,
        {
            "source": "api",
            "event_type": f"search_beta_{run}",
            "user": beta_user,
            "src_ip": beta_ip,
            "severity": 3,
            "action": "LOGIN",
        },
    )

    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    assert {row["user"] for row in _search(client, {"q": alpha_user})} == {alpha_user}
    assert {row["user"] for row in _search(client, {"user": alpha_user})} == {alpha_user}
    assert {row["srcIp"] for row in _search(client, {"src_ip": alpha_ip})} == {alpha_ip}


def test_source_event_type_and_severity_filters(client, api_key):
    run = uuid.uuid4().hex[:10]
    high_type = f"search_high_{run}"
    low_type = f"search_low_{run}"

    _ingest(
        client,
        api_key,
        {
            "source": "ad",
            "event_type": high_type,
            "src_ip": "203.0.113.70",
            "severity": 8,
            "action": "LOGIN",
        },
    )
    _ingest(
        client,
        api_key,
        {
            "source": "aws",
            "event_type": low_type,
            "src_ip": "203.0.113.71",
            "severity": 3,
            "action": "CREATE",
        },
    )

    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    rows = _search(client, {"source": "ad", "event_type": high_type})
    assert rows and all(row["source"] == "ad" for row in rows)

    rows = _search(client, {"event_type": high_type.upper()})
    assert {row["eventType"] for row in rows} == {high_type}
    assert all(row["severityLevel"] == "high" for row in rows)

    rows = _search(client, {"event_type": low_type, "severity": "low"})
    assert {row["eventType"] for row in rows} == {low_type}


def test_time_range_filters_use_from_and_to(client, api_key):
    run = uuid.uuid4().hex[:10]
    event_type = f"search_range_{run}"
    src_ip = "198.51.100.75"
    now = datetime.now(timezone.utc).replace(microsecond=0)
    inside_id = _ingest(
        client,
        api_key,
        {
            "source": "api",
            "event_type": event_type,
            "src_ip": src_ip,
            "severity": 4,
            "@timestamp": now.isoformat(),
        },
    )["eventId"]
    outside_id = _ingest(
        client,
        api_key,
        {
            "source": "api",
            "event_type": event_type,
            "src_ip": src_ip,
            "severity": 4,
            "@timestamp": (now - timedelta(hours=48)).isoformat(),
        },
    )["eventId"]

    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    rows = _search(
        client,
        {
            "event_type": event_type,
            "from": (now - timedelta(hours=1)).isoformat(),
            "to": (now + timedelta(hours=1)).isoformat(),
        },
    )
    assert {row["id"] for row in rows} == {inside_id}

    rows = _search(
        client,
        {
            "event_type": event_type,
            "from": (now - timedelta(days=3)).isoformat(),
            "to": (now - timedelta(hours=24)).isoformat(),
        },
    )
    assert {row["id"] for row in rows} == {outside_id}


def test_invalid_search_filters_return_422(client):
    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)

    for params in (
        {"source": "skynet"},
        {"severity": "extreme"},
        {"from": "not-a-date"},
    ):
        response = client.get("/api/events", params=params)
        assert response.status_code == 422, f"{params}: {response.text}"


def test_search_sort_order_and_limit(client, api_key):
    run = uuid.uuid4().hex[:10]
    event_type = f"search_sort_{run}"
    src_ip = "198.51.100.80"
    now = datetime.now(timezone.utc).replace(microsecond=0)

    ids = []
    for index in range(3):
        ids.append(
            _ingest(
                client,
                api_key,
                {
                    "source": "api",
                    "event_type": event_type,
                    "src_ip": src_ip,
                    "severity": 5,
                    "@timestamp": (now - timedelta(minutes=index)).isoformat(),
                },
            )["eventId"]
        )

    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    ascending = _search(
        client,
        {"src_ip": src_ip, "sort_by": "ts", "sort_order": "asc", "limit": 10},
    )
    assert [row["id"] for row in ascending] == list(reversed(ids))

    descending = _search(
        client,
        {"src_ip": src_ip, "sort_by": "ts", "sort_order": "desc", "limit": 2},
    )
    assert [row["id"] for row in descending] == ids[:2]


def test_viewer_search_stays_inside_their_tenant(client, api_key_demob):
    marker = f"viewer_search_{uuid.uuid4().hex}"
    _ingest(
        client,
        api_key_demob,
        {
            "source": "api",
            "tenant": "demob",
            "event_type": marker,
            "user": marker,
            "severity": 4,
        },
    )

    login(client, VIEWER_A_EMAIL, VIEWER_A_PASSWORD)
    rows = _search(client, {"q": marker, "tenant": "demob", "limit": 100})
    assert rows == []
