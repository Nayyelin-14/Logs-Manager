"""Cursor pagination and total-count acceptance tests.

These tests cover the search endpoint requirements added in Phase 2:
keyset paging on ``ts`` (including ties), a real filtered total, invalid
cursor handling, and tenant isolation across pages.
"""

from __future__ import annotations

import base64
import json
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


def _event(event_type: str, ts: datetime, *, index: int, source: str = "api") -> dict:
    return {
        "source": source,
        "event_type": event_type,
        "user": f"pagination_user_{index}",
        "src_ip": "203.0.113.200",
        "src_port": 20000 + index,
        "severity": 5,
        "action": "LOGIN",
        "@timestamp": ts.isoformat(),
        "raw": {"pagination_index": index},
    }


def test_cursor_pagination_covers_every_row_once_with_timestamp_ties(client, api_key):
    """Ingest 25 rows (12 distinct times + 13 ties), page by 10, see all once."""
    run = uuid.uuid4().hex[:10]
    event_type = f"pagination_{run}"
    base = datetime.now(timezone.utc).replace(microsecond=0)

    expected: dict[str, datetime] = {}
    for index in range(25):
        # The last 13 events deliberately share one timestamp to exercise the
        # (ts, id) tie-break branch of the keyset cursor.
        ts = base - timedelta(seconds=index) if index < 12 else base - timedelta(seconds=12)
        event_id = _ingest(client, api_key, _event(event_type, ts, index=index))
        expected[event_id] = ts

    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)

    cursor = None
    seen: list[str] = []
    page_sizes: list[int] = []
    for _ in range(10):
        params = {"event_type": event_type, "limit": 10}
        if cursor:
            params["cursor"] = cursor
        response = client.get("/api/events", params=params)
        assert response.status_code == 200, response.text
        body = response.json()

        assert body["total"] == 25, "total must count all matching rows, not the page"
        assert body["has_more"] == bool(body["newCursor"])
        page_sizes.append(len(body["logs"]))
        seen.extend(log["id"] for log in body["logs"])

        cursor = body["newCursor"]
        if not cursor:
            break

    assert len(seen) == 25, f"expected every event exactly once, got {len(seen)}"
    assert len(set(seen)) == 25, "pagination returned duplicate events"
    assert set(seen) == set(expected), "pagination skipped events"
    assert page_sizes == [10, 10, 5], f"unexpected page sizes: {page_sizes}"

    timestamps = [expected[event_id] for event_id in seen]
    assert timestamps == sorted(timestamps, reverse=True), "default order must be ts DESC"


def test_total_is_real_filtered_count_not_page_length(client, api_key):
    """A filtered page of 2 reports the true total (7), not len(logs)."""
    run = uuid.uuid4().hex[:10]
    event_type = f"total_{run}"
    now = datetime.now(timezone.utc).replace(microsecond=0)

    for index in range(7):
        _ingest(
            client,
            api_key,
            _event(event_type, now - timedelta(seconds=index), index=index, source="ad"),
        )
    # Same event type, different source: these must not inflate the AD total.
    for index in range(7, 10):
        _ingest(
            client,
            api_key,
            _event(event_type, now - timedelta(seconds=index), index=index, source="aws"),
        )

    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)

    response = client.get(
        "/api/events",
        params={"source": "ad", "event_type": event_type, "limit": 2},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["logs"]) == 2
    assert body["total"] == 7, "total must use the same source/event_type filters"
    assert body["has_more"] is True

    next_response = client.get(
        "/api/events",
        params={
            "source": "ad",
            "event_type": event_type,
            "limit": 2,
            "cursor": body["newCursor"],
        },
    )
    assert next_response.status_code == 200, next_response.text
    assert next_response.json()["total"] == 7


def test_non_timestamp_sort_uses_offset_cursor(client, api_key):
    """Allowlisted non-ts sorts fall back to deterministic offset paging."""
    run = uuid.uuid4().hex[:10]
    event_type = f"offset_{run}"
    now = datetime.now(timezone.utc).replace(microsecond=0)

    for index, severity in enumerate((1, 2, 3, 4, 5)):
        event = _event(event_type, now - timedelta(seconds=index), index=index)
        event["severity"] = severity
        _ingest(client, api_key, event)

    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)

    cursor = None
    seen: list[str] = []
    severities: list[int] = []
    for _ in range(10):
        params = {
            "event_type": event_type,
            "limit": 2,
            "sort_by": "severity",
            "sort_order": "asc",
        }
        if cursor:
            params["cursor"] = cursor
        response = client.get("/api/events", params=params)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["total"] == 5
        seen.extend(log["id"] for log in body["logs"])
        severities.extend(log["severity"] for log in body["logs"])
        cursor = body["newCursor"]
        if not cursor:
            break

    assert len(seen) == len(set(seen)) == 5
    assert severities == [1, 2, 3, 4, 5]

    # An offset cursor cannot silently be reused for a different sort mode.
    first_page = client.get(
        "/api/events",
        params={
            "event_type": event_type,
            "limit": 2,
            "sort_by": "severity",
            "sort_order": "asc",
        },
    ).json()
    mismatch = client.get(
        "/api/events",
        params={"event_type": event_type, "limit": 2, "cursor": first_page["newCursor"]},
    )
    assert mismatch.status_code == 400, mismatch.text


def test_invalid_cursor_returns_400(client, api_key):
    """Malformed or version-less cursors are client errors, never a 500."""
    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)

    response = client.get("/api/events", params={"limit": 5, "cursor": "not-a-cursor"})
    assert response.status_code == 400, response.text
    assert "cursor" in response.json()["detail"].lower()

    no_version = base64.urlsafe_b64encode(b'{"mode":"ts"}').decode("ascii").rstrip("=")
    response = client.get("/api/events", params={"limit": 5, "cursor": no_version})
    assert response.status_code == 400, response.text

    wrong_version = (
        base64.urlsafe_b64encode(json.dumps({"v": 999}).encode("utf-8"))
        .decode("ascii")
        .rstrip("=")
    )
    response = client.get("/api/events", params={"limit": 5, "cursor": wrong_version})
    assert response.status_code == 400, response.text


def test_viewer_pagination_and_total_stay_inside_their_tenant(
    client, api_key_demoa, api_key_demob
):
    """A demoa viewer paging with ?tenant=demob never sees or counts demob rows."""
    run = uuid.uuid4().hex[:10]
    event_type = f"isolation_{run}"
    now = datetime.now(timezone.utc).replace(microsecond=0)

    demoa_ids = {
        _ingest(
            client,
            api_key_demoa,
            _event(event_type, now - timedelta(seconds=index), index=index),
        )
        for index in range(7)
    }
    demob_ids = {
        _ingest(
            client,
            api_key_demob,
            _event(event_type, now - timedelta(seconds=index), index=100 + index),
        )
        for index in range(5)
    }

    login(client, VIEWER_A_EMAIL, VIEWER_A_PASSWORD)

    cursor = None
    seen: list[str] = []
    tenants: set[str] = set()
    for _ in range(10):
        params = {"event_type": event_type, "limit": 2, "tenant": "demob"}
        if cursor:
            params["cursor"] = cursor
        response = client.get("/api/events", params=params)
        assert response.status_code == 200, response.text
        body = response.json()

        assert body["total"] == 7, "viewer total must only count demoa rows"
        tenants.update(log["tenant"] for log in body["logs"])
        seen.extend(log["id"] for log in body["logs"])

        cursor = body["newCursor"]
        if not cursor:
            break

    assert tenants == {"demoa"}
    assert set(seen) == demoa_ids
    assert len(seen) == len(set(seen)) == 7
    assert demob_ids.isdisjoint(seen)
