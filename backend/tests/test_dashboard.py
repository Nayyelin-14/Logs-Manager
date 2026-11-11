"""Dashboard acceptance tests.

The dashboard must expose Top IP, Top User, Event Type, a timeline/source
breakdown, and tenant/time scoping. The tests seed one event per tenant and
then check both the widget values and the isolation rules.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.core.database import async_session_maker
from app.models.alert import Alert, AlertRule
from app.models.enums import Action, Source
from app.models.events import Event

from conftest import ADMIN_EMAIL, ADMIN_PASSWORD, VIEWER_A_EMAIL, VIEWER_A_PASSWORD, login

RUN = uuid.uuid4().hex[:8]
DEMOA_IP = "198.51.100.10"
DEMOB_IP = "198.51.100.20"
DEMOA_USER = f"dash-demoa-{RUN}"
DEMOB_USER = f"dash-demob-{RUN}"
DEMOA_TYPE = f"DashDemoA{RUN}"
DEMOB_TYPE = f"DashDemoB{RUN}"
DEMOA_RULE = f"Dash Rule A {RUN}"
DEMOB_RULE = f"Dash Rule B {RUN}"
DEMOA_ALERT = f"Dash Alert A {RUN}"
DEMOB_ALERT = f"Dash Alert B {RUN}"

DEMOB_MARKERS = [DEMOB_IP, DEMOB_USER, DEMOB_TYPE, DEMOB_RULE, DEMOB_ALERT]


async def _seed_dashboard_data() -> None:
    now = datetime.now(timezone.utc)
    async with async_session_maker() as session:
        session.add_all(
            [
                Event(
                    id=f"dash-evt-a-{RUN}",
                    ts=now - timedelta(hours=1),
                    tenant="demoa",
                    source=Source.FIREWALL,
                    event_type=DEMOA_TYPE,
                    action=Action.DENY,
                    severity=4,
                    user_name=DEMOA_USER,
                    host="dash-a-host",
                    src_ip=DEMOA_IP,
                    raw={"dashboard": True},
                    _tags=["dashboard"],
                ),
                Event(
                    id=f"dash-evt-b-{RUN}",
                    ts=now - timedelta(hours=2),
                    tenant="demob",
                    source=Source.AWS,
                    event_type=DEMOB_TYPE,
                    action=Action.CREATE,
                    severity=6,
                    user_name=DEMOB_USER,
                    host="dash-b-host",
                    src_ip=DEMOB_IP,
                    raw={"dashboard": True},
                    _tags=["dashboard"],
                ),
                AlertRule(
                    id=f"dash-rule-a-{RUN}",
                    name=DEMOA_RULE,
                    description="Dashboard test rule",
                    tenant="demoa",
                    enabled=False,
                    severity="high",
                    conditions=[{"type": "event_type"}],
                ),
                AlertRule(
                    id=f"dash-rule-b-{RUN}",
                    name=DEMOB_RULE,
                    description="Dashboard test rule",
                    tenant="demob",
                    enabled=False,
                    severity="high",
                    conditions=[{"type": "event_type"}],
                ),
                Alert(
                    id=f"dash-alert-a-{RUN}",
                    rule_id=f"dash-rule-a-{RUN}",
                    tenant="demoa",
                    description="Dashboard test alert",
                    triggered_at=now - timedelta(minutes=30),
                    event_ids=[f"dash-evt-a-{RUN}"],
                    severity="high",
                    status="open",
                    title=DEMOA_ALERT,
                    tags=[],
                    dedupe_key=f"dash-a-{RUN}",
                    group_key="dashboard",
                    group_value="a",
                    count=1,
                    first_seen=now - timedelta(hours=1),
                    last_seen=now - timedelta(hours=1),
                ),
                Alert(
                    id=f"dash-alert-b-{RUN}",
                    rule_id=f"dash-rule-b-{RUN}",
                    tenant="demob",
                    description="Dashboard test alert",
                    triggered_at=now - timedelta(minutes=30),
                    event_ids=[f"dash-evt-b-{RUN}"],
                    severity="high",
                    status="open",
                    title=DEMOB_ALERT,
                    tags=[],
                    dedupe_key=f"dash-b-{RUN}",
                    group_key="dashboard",
                    group_value="b",
                    count=1,
                    first_seen=now - timedelta(hours=2),
                    last_seen=now - timedelta(hours=2),
                ),
            ]
        )
        await session.commit()


@pytest.fixture(scope="module", autouse=True)
def dashboard_seed(test_database):
    asyncio.run(_seed_dashboard_data())
    yield


def _assert_viewer_scoped(data: dict, requested_tenant: str) -> None:
    payload = json.dumps(data)
    for marker in DEMOB_MARKERS:
        assert json.dumps(marker) not in payload, (
            f"tenant leak with ?tenant={requested_tenant}: {marker}"
        )

    assert data["tenant"] == "demoa"
    assert data["totalEvents"] >= 1
    assert all(row["ip"] != DEMOB_IP for row in data["topIPs"])
    assert all(row["user"] != DEMOB_USER for row in data["topUsers"])
    assert all(row["type"] != DEMOB_TYPE for row in data["topEventTypes"])

    for widget in ("eventsByTenant", "eventsBySource", "alertsByDay", "recentAlert"):
        for row in data[widget]:
            assert row.get("tenant") == "demoa", f"{widget} leaked {row}"


def test_dashboard_returns_top_widgets_and_timeline(admin_client):
    response = admin_client.get("/api/dashboard")
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["totalEvents"] >= 2
    assert any(row["ip"] == DEMOA_IP for row in data["topIPs"])
    assert any(row["ip"] == DEMOB_IP for row in data["topIPs"])
    assert any(row["user"] == DEMOA_USER for row in data["topUsers"])
    assert any(row["type"] == DEMOA_TYPE for row in data["topEventTypes"])

    timeline = data["eventsBySource"]
    assert timeline, "dashboard timeline must not be empty"
    assert any(row["source"] == "firewall" for row in timeline)
    assert any(row["source"] == "aws" for row in timeline)
    assert all(row["timestamp"] for row in timeline)
    assert data["alertsByDay"], "dashboard alert timeline must not be empty"


def test_viewer_dashboard_is_tenant_scoped(client):
    login(client, VIEWER_A_EMAIL, VIEWER_A_PASSWORD)

    for params in ({}, {"tenant": "demob"}):
        response = client.get("/api/dashboard", params=params)
        assert response.status_code == 200, response.text
        _assert_viewer_scoped(response.json(), params.get("tenant", "<none>"))


def test_admin_dashboard_sees_all_tenants(admin_client):
    response = admin_client.get("/api/dashboard")
    assert response.status_code == 200, response.text
    data = response.json()

    tenant_counts = {row["tenant"]: row["count"] for row in data["eventsByTenant"]}
    assert tenant_counts.get("demoa", 0) >= 1
    assert tenant_counts.get("demob", 0) >= 1

    tenant_names = {row["tenant"] for row in data["tenants"]}
    assert {"demoa", "demob"}.issubset(tenant_names)

    payload = json.dumps(data)
    assert json.dumps(DEMOA_IP) in payload
    assert json.dumps(DEMOB_IP) in payload
