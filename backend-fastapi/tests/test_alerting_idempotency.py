"""
Idempotency and failure-isolation tests for alerting.

(a) create_or_update_alert called twice with the same dedupe_key yields
    one alert row with count updated (never a UniqueViolation).
(b) A forced IntegrityError in one rule does not stop other rules from
    evaluating (evaluate_all_rules continues).
(c) seed_demo_data.py runs twice without error and creates no duplicates.
"""

import asyncio
import os
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.core.database import async_session_maker
from app.models.alert import Alert, AlertRule, AlertStatus
from app.models.events import Event
from app.models.tenant import Tenant
from app.services.alerting.alerter import create_or_update_alert
from app.services.alerting.evaluator import evaluate_all_rules, evaluate_rule

RULE_NAME = "test-idempotency-rule"
NOW = datetime.now(timezone.utc)


async def _make_rule(session, tenant="demoa", name=RULE_NAME, enabled=True, rule_id=None):
    result = await session.execute(select(AlertRule).where(AlertRule.name == name))
    rule = result.scalar_one_or_none()
    if rule is None:
        rule = AlertRule(
            id=rule_id or uuid.uuid4().hex[:25],
            name=name,
            description="idempotency test rule",
            tenant=tenant,
            enabled=enabled,
            severity="high",
            filter={"outcome": "failure", "action": "login"},
            conditions=[{"type": "event_type", "value": "LogonFailed"}],
            group_by="src_ip",
            threshold=5,
            window_minutes=5,
            cooldown_minutes=15,
        )
        session.add(rule)
        await session.flush()
    return rule


async def _make_tenant(session, name="demoa"):
    result = await session.execute(select(Tenant).where(Tenant.name == name))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        tenant = Tenant(
            id="test-tenant-id",
            name=name,
            api_key_hash="x",
            is_active=True,
        )
        session.add(tenant)
        await session.flush()
    return tenant


@pytest.mark.asyncio
async def test_create_or_update_alert_twice_same_dedupe_key():
    """(a) Calling create_or_update_alert twice with the same dedupe_key
    yields one alert row with count updated, never an exception."""
    async with async_session_maker() as session:
        await _make_tenant(session)
        rule = await _make_rule(session)

        kwargs = dict(
            session=session,
            rule_id=rule.id,
            rule_name=rule.name,
            rule_severity="high",
            tenant="demoa",
            group_by="src_ip",
            group_value="203.0.113.77",
            count=3,
            first_seen=NOW,
            last_seen=NOW,
            evidence_ids=["e1", "e2"],
            tags=["demo"],
            window_minutes=5,
            notify={"webhook_url": None, "cooldown_minutes": 15},
            now=NOW,
        )

        result1 = await create_or_update_alert(**kwargs)
        result2 = await create_or_update_alert(**kwargs)

        dedupe_key = result1["dedupe_key"]
        assert dedupe_key == f"{rule.id}:demoa:203.0.113.77"
        assert result2["dedupe_key"] == dedupe_key
        assert result1["id"] == result2["id"], "Same alert row expected"
        assert result1["count"] == 3, f"First count should be 3, got {result1['count']}"
        # Same evidence_ids re-sent: count must NOT double-count (idempotent).
        assert result2["count"] == 3, f"Second count should stay 3 (no new events), got {result2['count']}"

        # New event IDs on same dedupe_key: count increases by new IDs only.
        kwargs2 = dict(kwargs, evidence_ids=["e3", "e4"])
        result3 = await create_or_update_alert(**kwargs2)
        assert result3["id"] == result1["id"], "Same alert row for new events too"
        assert result3["count"] == 5, f"Third count should be 5 (3+2 new), got {result3['count']}"

        # Verify exactly one alert row exists for this dedupe_key
        alerts = await session.execute(
            select(Alert).where(Alert.dedupe_key == dedupe_key)
        )
        rows = alerts.scalars().all()
        assert len(rows) == 1, f"Expected 1 alert row, got {len(rows)}"
        assert rows[0].count == 5, f"Expected count=5, got {rows[0].count}"


@pytest.mark.asyncio
async def test_integrity_error_in_one_rule_does_not_stop_others():
    """(b) A forced IntegrityError in one rule does not stop other rules
    from evaluating. evaluate_rule catches the IntegrityError, rolls back,
    returns [], and subsequent rules still evaluate."""
    async with async_session_maker() as session:
        await _make_tenant(session, "demoa")
        rule_a = await _make_rule(session, "demoa", "rule-a")
        rule_b = await _make_rule(session, "demoa", "rule-b")

        def _add_events(src_ip):
            for i in range(5):
                session.add(Event(
                    id=f"evt-{src_ip}-{i}",
                    ts=NOW - timedelta(minutes=i),
                    tenant="demoa",
                    source="ad",
                    event_type="LogonFailed",
                    outcome="failure",
                    action="login",
                    severity=7,
                    src_ip=src_ip,
                    raw={},
                    _tags=[],
                ))

        results = {"a": 0, "b": 0}

        async def fake_create_or_update(session_, *, rule_id, **_kwargs):
            if rule_id == rule_a.id:
                results["a"] += 1
                raise IntegrityError("duplicate dedupe_key", None, None)
            results["b"] += 1
            return {
                "id": "alert-" + rule_id,
                "rule_id": rule_id,
                "tenant": "demoa",
                "dedupe_key": rule_id + ":demoa:x",
                "count": 1,
                "status": "open",
                "notified": True,
            }

            with patch(
                "app.services.alerting.evaluator.create_or_update_alert",
                side_effect=fake_create_or_update,
            ):
                # Rule A: create_or_update_alert raises IntegrityError ->
                # evaluate_rule catches it, rolls back, returns [].
                _add_events("1.1.1.1")
                await session.flush()
                result_a = await evaluate_rule(session, rule_a, NOW)
                assert result_a == []
                assert results["a"] >= 1

                # Remove rule A's events so rule B's query sees only its own groups.
                await session.execute(
                    text("DELETE FROM events WHERE src_ip = '1.1.1.1'")
                )
                await session.flush()

                # Re-flush events for rule B.
                _add_events("2.2.2.2")
                await session.flush()
                result_b = await evaluate_rule(session, rule_b, NOW)
                assert len(result_b) == 1
                assert results["b"] >= 1


def _run_seed():
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script = os.path.join(backend_dir, "scripts", "seed_demo_data.py")

    env = dict(os.environ)
    # Always point the subprocess at the local test database, regardless of
    # any DATABASE_URL the parent test process may have set.
    # Inside a container, db is reachable at db:5432; on the host at localhost:55432.
    db_host = "db" if os.path.exists("/.dockerenv") else "localhost"
    db_port = "5432" if os.path.exists("/.dockerenv") else "55432"
    env["DATABASE_URL"] = f"postgresql+asyncpg://logs:postgres_pass@{db_host}:{db_port}/logs_manager_test?sslmode=disable"
    env["SEED_ADMIN_PASSWORD"] = "TestPassword123!"
    env["SEED_VIEWER_A_PASSWORD"] = "TestViewerPassword1!"
    env["SEED_VIEWER_B_PASSWORD"] = "TestViewerBP@ssw0rd!"
    env["SAAS_MODE"] = "false"

    return subprocess.run(
        [sys.executable, script],
        cwd=backend_dir,
        env=env,
        capture_output=True,
        text=True,
    )


def test_seed_demo_data_runs_twice():
    """(c) Running seed_demo_data.py twice succeeds without error."""
    for run in (1, 2):
        result = _run_seed()
        output = f"{result.stdout}\n{result.stderr}"
        assert result.returncode == 0, f"Seed run {run} failed:\n{output}"
        assert "Seed error" not in output, f"Seed run {run} had an error:\n{output}"
        assert "Seed complete!" in output, f"Seed run {run} did not complete:\n{output}"


def test_seed_twice_no_duplicate_tenants_users_alerts():
    """(c continued) After running seed twice, no duplicate tenants,
    users, or alert dedupe_keys exist."""
    for _ in range(2):
        result = _run_seed()
        assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"

    async def _check():
        async with async_session_maker() as session:
            tenants = await session.execute(select(Tenant))
            assert len(tenants.scalars().all()) == 2, "Expected exactly 2 tenants"

            from app.models.user import User
            users = await session.execute(select(User))
            assert len(users.scalars().all()) == 3, "Expected exactly 3 users"

            alerts = await session.execute(select(Alert))
            alert_rows = alerts.scalars().all()
            dedupe_keys = [a.dedupe_key for a in alert_rows if a.dedupe_key]
            assert len(dedupe_keys) == len(set(dedupe_keys)), "Duplicate dedupe_keys found"

    asyncio.run(_check())
