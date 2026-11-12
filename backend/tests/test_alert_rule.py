import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from app.core.database import async_session_maker
from app.models.alert import Alert, AlertRule
from app.models.events import Event


@pytest.mark.asyncio
async def test_crowdstrike_malware_detected_case_mismatch_fires(test_database):
    """CrowdStrike emits MalwareDetected; the seeded rule uses malware_detected."""
    from app.services.alerting.evaluator import evaluate_rule

    tenant = f"crowdstrike-case-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)
    async with async_session_maker() as session:
        rule = AlertRule(
            id=uuid.uuid4().hex[:25],
            name="CrowdStrike malware case test",
            description="case mismatch regression",
            tenant=tenant,
            conditions=[
                {
                    "type": "event_type",
                    "value": "malware_detected",
                    "groupBy": "src_ip",
                    "threshold": 1,
                    "windowSeconds": 300,
                }
            ],
            filter={"event_type": "malware_detected", "severity_gte": 8},
            enabled=True,
            severity="critical",
            rule_type="threshold",
            group_by="src_ip",
            threshold=1,
            window_minutes=5,
            cooldown_minutes=15,
            notify={},
        )
        session.add(rule)

        event = Event(
            id=uuid.uuid4().hex[:20],
            ts=now,
            tenant=tenant,
            source="crowdstrike",
            event_type="MalwareDetected",
            severity=9,
            action="alert",
            src_ip="203.0.113.99",
            raw={"EventType": "MalwareDetected"},
            _tags=["crowdstrike"],
            ingested_at=now,
        )
        session.add(event)
        await session.commit()

        alerts = await evaluate_rule(session, rule, now)
        await session.commit()

        assert alerts, "MalwareDetected must match the malware_detected rule"
        alert = await session.get(Alert, alerts[0]["id"])
        assert alert is not None

        await session.execute(delete(Alert).where(Alert.id == alerts[0]["id"]))
        await session.execute(delete(Event).where(Event.id == event.id))
        await session.execute(delete(AlertRule).where(AlertRule.id == rule.id))
        await session.commit()
