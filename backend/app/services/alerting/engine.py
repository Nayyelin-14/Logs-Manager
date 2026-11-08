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

    def __init__(self, session: AsyncSession):
        self.session = session

    async def evaluate_event(self, event: Event) -> List[Dict[str, Any]]:

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
            rule_id = rule.id
            rule_name = rule.name
            try:
                rule_alerts = await evaluate_rule(self.session, rule, now)
                alerts.extend(rule_alerts)
            except Exception as exc:  # noqa: BLE001
                await self.session.rollback()
                logger.exception("rule %s (%s) evaluation failed: %s", rule_id, rule_name, exc)
        return alerts
