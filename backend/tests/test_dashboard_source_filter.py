"""Dashboard source-filter acceptance tests.

Covers the assignment requirement that the dashboard filters by time range,
tenant and source, with server-side tenant isolation on every aggregate.
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


def _ingest(client, api_key: str, event: dict) -> str:
    response = client.post("/api/ingest", json=event, headers=_headers(api_key))
    assert response.status_code == 200, response.text
    return response.json()["eventId"]


def _event(
    *,
    source: str,
    event_type: str,
    user: str,
    src_ip: str,
    ts: datetime,
    index: int,
) -> dict:
    return {
        "source": source,
        "event_type": event_type,
        "user": user,
        "src_ip": src_ip,
        "src_port": 30000 + index,
        "severity": 8 if source == "ad" else 3,
        "action": "LOGIN",
        "@timestamp": ts.isoformat(),
        "raw": {"dashboard_source_filter": index},
    }


def test_dashboard_source_filter_limits_all_top_lists(client, api_key):
    """source=ad only counts AD rows in top IPs/users/event types and timeline."""
    run = uuid.uuid4().hex[:10]
    ad_user = f"ad_user_{run}"
    aws_user = f"aws_user_{run}"
    ad_ip = "198.51.100.201"
    aws_ip = "198.51.100.202"
    ad_type = f"ad_event_{run}"
    aws_type = f"aws_event_{run}"
    now = datetime.now(timezone.utc).replace(microsecond=0)

    # A high count makes these markers robust against other tests' data.
    for index in range(25):
        _ingest(
            client,
            api_key,
            _event(
                source="ad",
                event_type=ad_type,
                user=ad_user,
                src_ip=ad_ip,
                ts=now - timedelta(seconds=index),
                index=index,
            ),
        )
    for index in range(5):
        _ingest(
            client,
            api_key,
            _event(
                source="aws",
                event_type=aws_type,
                user=aws_user,
                src_ip=aws_ip,
                ts=now - timedelta(seconds=index),
                index=100 + index,
            ),
        )

    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    response = client.get(
        "/api/dashboard",
        params={"tenant": "demoa", "range": "1d", "source": "ad"},
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert ad_user in {item["user"] for item in body["topUsers"]}
    assert aws_user not in {item["user"] for item in body["topUsers"]}
    assert ad_ip in {item["ip"] for item in body["topIPs"]}
    assert aws_ip not in {item["ip"] for item in body["topIPs"]}
    assert ad_type in {item["type"] for item in body["topEventTypes"]}
    assert aws_type not in {item["type"] for item in body["topEventTypes"]}

    # Timeline/source distribution also describe only the selected source.
    assert body["eventsBySource"]
    assert {item["source"] for item in body["eventsBySource"]} == {"ad"}
    assert {item["source"] for item in body["sources"]} == {"ad"}
    assert body["totalEvents"] >= 25


def test_dashboard_rejects_unknown_source(client, api_key):
    """Unknown source values are clean 422s on every dashboard/stats endpoint."""
    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)

    for path in (
        "/api/dashboard",
        "/api/stats/top",
        "/api/stats/timeline",
        "/api/stats/summary",
    ):
        response = client.get(path, params={"source": "definitely-not-a-source"})
        assert response.status_code == 422, f"{path}: {response.text}"
        assert "unsupported source" in response.json()["detail"].lower()


def test_viewer_source_and_tenant_override_stay_in_own_tenant(
    client, api_key_demoa, api_key_demob
):
    """A demoa viewer using source + ?tenant=demob still sees only demoa."""
    run = uuid.uuid4().hex[:10]
    demoa_user = f"viewer_demoa_{run}"
    demob_user = f"viewer_demob_{run}"
    event_type = f"viewer_scope_{run}"
    now = datetime.now(timezone.utc).replace(microsecond=0)

    for index in range(8):
        _ingest(
            client,
            api_key_demoa,
            _event(
                source="ad",
                event_type=event_type,
                user=demoa_user,
                src_ip="198.51.100.211",
                ts=now - timedelta(seconds=index),
                index=index,
            ),
        )
        _ingest(
            client,
            api_key_demob,
            _event(
                source="ad",
                event_type=event_type,
                user=demob_user,
                src_ip="198.51.100.212",
                ts=now - timedelta(seconds=index),
                index=200 + index,
            ),
        )

    login(client, VIEWER_A_EMAIL, VIEWER_A_PASSWORD)
    params = {"tenant": "demob", "range": "1d", "source": "ad"}

    dashboard = client.get("/api/dashboard", params=params)
    assert dashboard.status_code == 200, dashboard.text
    body = dashboard.json()
    assert demoa_user in {item["user"] for item in body["topUsers"]}
    assert demob_user not in {item["user"] for item in body["topUsers"]}
    assert {item["tenant"] for item in body["eventsByTenant"]} == {"demoa"}

    top = client.get(
        "/api/stats/top",
        params={"tenant": "demob", "source": "ad", "field": "user", "n": 100},
    )
    assert top.status_code == 200, top.text
    top_values = {item["value"] for item in top.json()["items"]}
    assert demoa_user in top_values
    assert demob_user not in top_values

    summary = client.get("/api/stats/summary", params=params)
    assert summary.status_code == 200, summary.text
    assert summary.json()["tenants"] == ["demoa"]
    assert summary.json()["total_events"] >= 8

    timeline = client.get("/api/stats/timeline", params=params)
    assert timeline.status_code == 200, timeline.text
    assert {source for bucket in timeline.json()["buckets"] for source in bucket["by_source"]} == {"ad"}
