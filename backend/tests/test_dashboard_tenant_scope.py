import asyncio
import json
from datetime import datetime, timedelta, timezone

import pytest

from app.core.database import async_session_maker
from app.models.alert import Alert, AlertRule
from app.models.enums import Action, Source
from app.models.events import Event
from conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    VIEWER_A_EMAIL,
    VIEWER_A_PASSWORD,
)

DEMOA_IP = "198.51.100.10"
DEMOB_IP = "198.51.100.20"
DEMOA_USER = "scope-dashboard-demoa"
DEMOB_USER = "scope-dashboard-demob"
DEMOA_TYPE = "ScopeDashboardDemoA"
DEMOB_TYPE = "ScopeDashboardDemoB"
DEMOA_RULE = "Scope Dashboard Rule A"
DEMOB_RULE = "Scope Dashboard Rule B"
DEMOA_ALERT = "Scope Dashboard Alert A"
DEMOB_ALERT = "Scope Dashboard Alert B"

DEMOB_MARKERS = [DEMOB_IP, DEMOB_USER, DEMOB_TYPE, DEMOB_RULE, DEMOB_ALERT]


async def _seed_dashboard_scope_data():
    now = datetime.now(timezone.utc)
    async with async_session_maker() as session:
        session.add_all(
            [
                Event(
                    id="scope_dash_evt_a",
                    ts=now - timedelta(hours=1),
                    tenant="demoa",
                    source=Source.FIREWALL,
                    event_type=DEMOA_TYPE,
                    action=Action.DENY,
                    severity=4,
                    user_name=DEMOA_USER,
                    host="scope-a-host",
                    src_ip=DEMOA_IP,
                    raw={"scope_dashboard": True},
                    _tags=["scope-dashboard"],
                ),
                Event(
                    id="scope_dash_evt_b",
                    ts=now - timedelta(hours=2),
                    tenant="demob",
                    source=Source.AWS,
                    event_type=DEMOB_TYPE,
                    action=Action.CREATE,
                    severity=6,
                    user_name=DEMOB_USER,
                    host="scope-b-host",
                    src_ip=DEMOB_IP,
                    raw={"scope_dashboard": True},
                    _tags=["scope-dashboard"],
                ),
                AlertRule(
                    id="scope_dash_rule_a",
                    name=DEMOA_RULE,
                    description="Scope dashboard test rule",
                    tenant="demoa",
                    enabled=False,
                    severity="high",
                    conditions=[{"type": "event_type"}],
                ),
                AlertRule(
                    id="scope_dash_rule_b",
                    name=DEMOB_RULE,
                    description="Scope dashboard test rule",
                    tenant="demob",
                    enabled=False,
                    severity="high",
                    conditions=[{"type": "event_type"}],
                ),
                Alert(
                    id="scope_dash_alert_a",
                    rule_id="scope_dash_rule_a",
                    tenant="demoa",
                    description="Scope dashboard test alert",
                    triggered_at=now - timedelta(minutes=30),
                    event_ids=["scope_dash_evt_a"],
                    severity="high",
                    status="open",
                    title=DEMOA_ALERT,
                    tags=[],
                    dedupe_key="scope-dashboard-a",
                    group_key="scope-dashboard",
                    group_value="a",
                    count=1,
                    first_seen=now - timedelta(hours=1),
                    last_seen=now - timedelta(hours=1),
                ),
                Alert(
                    id="scope_dash_alert_b",
                    rule_id="scope_dash_rule_b",
                    tenant="demob",
                    description="Scope dashboard test alert",
                    triggered_at=now - timedelta(minutes=30),
                    event_ids=["scope_dash_evt_b"],
                    severity="high",
                    status="open",
                    title=DEMOB_ALERT,
                    tags=[],
                    dedupe_key="scope-dashboard-b",
                    group_key="scope-dashboard",
                    group_value="b",
                    count=1,
                    first_seen=now - timedelta(hours=2),
                    last_seen=now - timedelta(hours=2),
                ),
            ]
        )
        await session.commit()


@pytest.fixture(scope="module", autouse=True)
def dashboard_scope_seed(test_database):
    asyncio.run(_seed_dashboard_scope_data())
    yield


def _login(client, email, password):
    response = client.post(
        "/api/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text
    return response


def _assert_viewer_scoped(data, requested_tenant):
    payload = json.dumps(data)
    for marker in DEMOB_MARKERS:
        assert json.dumps(marker) not in payload, (
            f"tenant leak with ?tenant={requested_tenant}: {marker} "
            f"appeared in dashboard payload"
        )

    assert data["tenant"] == "demoa"
    assert data["totalEvents"] >= 1

    for widget in ("eventsByTenant", "eventsBySource", "alertsByDay", "recentAlert"):
        for row in data[widget]:
            assert row.get("tenant") == "demoa", f"{widget} leaked {row}"

    for widget in ("tenants",):
        for row in data[widget]:
            assert row.get("tenant") == "demoa", f"{widget} leaked {row}"

    # alertsRuleByDay is labelled from the effective tenant, not each row.
    for row in data["alertsRuleByDay"]:
        assert row.get("tenant") == "demoa", f"alertsRuleByDay leaked {row}"
        assert DEMOB_RULE not in json.dumps(row)

    # Widgets without tenant fields still must not carry demob markers.
    for widget in (
        "topIPs",
        "topUsers",
        "topEventTypes",
        "severityCounts",
        "sources",
        "alertCountsByStatus",
        "alertCountsBySeverity",
        "ruleCountsByEnabled",
    ):
        assert json.dumps(DEMOB_MARKERS[0]) not in json.dumps(data[widget])
        assert json.dumps(DEMOB_MARKERS[1]) not in json.dumps(data[widget])


def test_viewer_dashboard_ignores_other_tenant_parameter(client):
    _login(client, VIEWER_A_EMAIL, VIEWER_A_PASSWORD)
    response = client.get("/api/dashboard?tenant=demob")
    assert response.status_code == 200, response.text
    _assert_viewer_scoped(response.json(), "demob")


def test_viewer_dashboard_without_tenant_is_scoped(client):
    _login(client, VIEWER_A_EMAIL, VIEWER_A_PASSWORD)
    response = client.get("/api/dashboard")
    assert response.status_code == 200, response.text
    _assert_viewer_scoped(response.json(), "<none>")


def test_admin_dashboard_sees_both_tenants(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    response = client.get("/api/dashboard")
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
    assert json.dumps(DEMOA_ALERT) in payload
    assert json.dumps(DEMOB_ALERT) in payload
