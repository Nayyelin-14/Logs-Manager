from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert, AlertRule
from app.models.events import Event
from app.core.config import get_settings
from app.services.alerting.evaluator import evaluate_rule
settings = get_settings()
logger = logging.getLogger(__name__)

class AlertService:
    def __init__(self, session: AsyncSession):
        self.session = session
    async def check_alerts(self, event: Event) -> List[dict]:

        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(AlertRule).where(
                AlertRule.tenant == event.tenant,
                AlertRule.enabled == True,  # noqa: E712
            )
        )
        rules = result.scalars().all()

        triggered: List[dict] = []
        for rule in rules:
            try:
                rule_alerts = await evaluate_rule(self.session, rule, now)
                for alert_data in rule_alerts:
                    triggered.append({
                        "id": alert_data.get("id"),
                        "title": alert_data.get("title", f"Alert: {rule.name}"),
                        "severity": alert_data.get("severity", rule.severity),
                        "dedupe_key": alert_data.get("dedupe_key"),
                        "group_value": alert_data.get("group_value"),
                        "count": alert_data.get("count"),
                        "notified": alert_data.get("notified", False),
                    })
            except Exception as exc:  # noqa: BLE001
                logger.exception("rule %s check failed: %s", rule.id, exc)
        return triggered
