"""
Alerting Detection Engine

Thin wrapper around the shared evaluator (app/services/alerting/evaluator.py).
Keeps backward compatibility with the ingest service which calls
evaluate_batch([event]) on ingestion.

All threshold evaluation now goes through evaluate_rule() which runs a single
parameterized GROUP BY ... HAVING query per rule.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import AlertRule
from app.models.events import Event
from app.services.alerting.evaluator import evaluate_rule

logger = logging.getLogger(__name__)


class AlertingEngine:
    """Event-based alerting engine (delegates to shared evaluator)."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def evaluate_event(self, event: Event) -> List[Dict[str, Any]]:
        """Evaluate a single event against all enabled rules for its tenant."""
        now = datetime.now(timezone.utc)
        from sqlalchemy import select, or_
        result = await self.session.execute(
            select(AlertRule).where(
                or_(AlertRule.tenant == event.tenant, AlertRule.tenant == "*"),
                AlertRule.enabled == True,  # noqa: E712
            )
        )
        rules = result.scalars().all()

        alerts: List[Dict[str, Any]] = []
        for rule in rules:
            # Read ORM attributes into locals before any DB call so except blocks
            # never touch expired/detached ORM state after a failure.
            rule_id = rule.id
            rule_name = rule.name
            try:
                rule_alerts = await evaluate_rule(self.session, rule, now)
                alerts.extend(rule_alerts)
            except Exception as exc:  # noqa: BLE001
                await self.session.rollback()
                logger.exception("rule %s (%s) evaluation failed: %s", rule_id, rule_name, exc)
        return alerts

    async def evaluate_batch(self, events: List[Event]) -> List[Dict[str, Any]]:
        """Evaluate a batch of events against all enabled rules.

        Evaluates each enabled rule once against all events in the window
        (not once per event), so a batch of N events costs O(rules) queries
        instead of O(N x rules). Results are consistent with the 30s sweep.
        """
        if not events:
            return []

        now = datetime.now(timezone.utc)
        from sqlalchemy import select, or_

        tenants = list({e.tenant for e in events if e.tenant})
        if not tenants:
            return []

        result = await self.session.execute(
            select(AlertRule).where(
                or_(*[AlertRule.tenant == t for t in tenants], AlertRule.tenant == "*"),
                AlertRule.enabled == True,  # noqa: E712
            )
        )
        rules = result.scalars().all()

        alerts: List[Dict[str, Any]] = []
        for rule in rules:
            # Read ORM attributes into locals before any DB call so except blocks
            # never touch expired/detached ORM state after a failure.
            rule_id = rule.id
            rule_name = rule.name
            try:
                rule_alerts = await evaluate_rule(self.session, rule, now)
                alerts.extend(rule_alerts)
            except Exception as exc:  # noqa: BLE001
                await self.session.rollback()
                logger.exception("rule %s (%s) evaluation failed: %s", rule_id, rule_name, exc)
        return alerts