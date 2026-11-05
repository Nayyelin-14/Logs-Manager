"""
Alerting Detection Engine

Evaluates events against alert rules and creates/updates alerts.
Uses event's @timestamp for time windows.
Creates or updates alerts with INSERT ... ON CONFLICT on dedupe_key.

No network calls (SMTP/webhook) - those are handled in Phase 2.
Optimized: ONE SQL query per group evaluation.
"""

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from sqlalchemy import select, func, text, or_, and_, column
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from app.models.alert import Alert, AlertRule, AlertStatus
from app.models.security_event import SecurityEvent

logger = logging.getLogger(__name__)

VALID_GROUP_BY_FIELDS = {"src_ip", "user", "host"}
MIN_WINDOW_SECONDS = 1
MAX_WINDOW_SECONDS = 86400
DEFAULT_THRESHOLD = 5
DEFAULT_WINDOW_SECONDS = 300


class AlertingEngine:
    """Event-based alerting engine with event-time windows."""
    
    # Column reference for @timestamp (Python-safe name)
    _ts_col = column("@timestamp")
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def evaluate_event(self, event: SecurityEvent) -> List[Dict[str, Any]]:
        """Evaluate a single event against all applicable rules for its tenant."""
        rules = await self._get_applicable_rules(event)
        if not rules:
            return []
        
        alerts = []
        for rule in rules:
            alert_data = await self._evaluate_rule(rule, event)
            if alert_data:
                alerts.append(alert_data)
        
        return alerts
    
    async def _get_applicable_rules(self, event: SecurityEvent) -> List[AlertRule]:
        """Get all enabled rules for the event's tenant."""
        result = await self.session.execute(
            select(AlertRule).where(
                AlertRule.tenant == event.tenant,
                AlertRule.enabled == True
            )
        )
        return result.scalars().all()
    
    async def _evaluate_rule(self, rule: AlertRule, event: SecurityEvent) -> Optional[Dict[str, Any]]:
        """Evaluate a rule against an event."""
        condition = rule.conditions[0] if rule.conditions else {}
        condition_type = condition.get("type")
        
        if condition_type == "repeated_failures":
            return await self._evaluate_repeated_failures(rule, event, condition)
        elif condition_type == "event_type":
            return await self._evaluate_count(rule, event, condition)
        elif condition_type == "severity_min":
            return await self._evaluate_count(rule, event, condition)
        elif condition_type == "field_value":
            return await self._evaluate_count(rule, event, condition)
        elif condition_type == "threshold_count":
            return await self._evaluate_count(rule, event, condition)
        
        return None
    
    async def _check_threshold_counts(
        self,
        tenant: str,
        group_field: str,
        group_value: str,
        window_end: datetime,
        window_seconds: int,
        event_type: Optional[str] = None,
        outcome_required: Optional[str] = None
    ) -> int:
        """Count events matching criteria in the window ending at window_end.
        
        SINGLE SQL QUERY - O(1) database operations.
        """
        window_start = window_end - timedelta(seconds=window_seconds)
        
        ts_col = self._ts_col
        query = select(func.count()).select_from(SecurityEvent).where(
            SecurityEvent.tenant == tenant,
            ts_col >= window_start,
            ts_col <= window_end,
            getattr(SecurityEvent, group_field) == group_value,
        )
        
        if event_type:
            query = query.where(SecurityEvent.canonical_event_type == event_type)
        
        if outcome_required:
            query = query.where(SecurityEvent.outcome == outcome_required)
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none() or 0
    
    async def _evaluate_repeated_failures(
        self,
        rule: AlertRule,
        event: SecurityEvent,
        condition: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Evaluate repeated failures rule: count failures in time window.
        
        Rule triggers when threshold failures from same src_ip within window.
        """
        threshold = int(condition.get("threshold", DEFAULT_THRESHOLD))
        window_seconds = int(condition.get("windowSeconds", DEFAULT_WINDOW_SECONDS))
        group_by_field = condition.get("groupBy", "src_ip")
        
        if group_by_field not in VALID_GROUP_BY_FIELDS:
            return None
        
        # Only count failures
        if event.outcome != "failure":
            return None
        
        group_value = getattr(event, group_by_field, None)
        if not group_value:
            return None
        
        # ONE SQL COUNT query using event's @timestamp
        count = await self._check_threshold_counts(
            tenant=event.tenant,
            group_field=group_by_field,
            group_value=group_value,
            window_end=event.timestamp,
            window_seconds=window_seconds,
            event_type=None,
            outcome_required="failure"
        )
        
        if count < threshold:
            return None
        
        return await self._upsert_alert(rule, event, group_value, count)
    
    async def _evaluate_count(
        self,
        rule: AlertRule,
        event: SecurityEvent,
        condition: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Evaluate a count-based rule (event_type, severity_min, field_value, threshold_count)."""
        threshold = int(condition.get("threshold", 1))
        window_seconds = int(condition.get("windowSeconds", DEFAULT_WINDOW_SECONDS))
        group_by_field = condition.get("groupBy", condition.get("group_by", "src_ip"))
        
        if group_by_field not in VALID_GROUP_BY_FIELDS:
            return None
        
        filters = condition.get("filters", {})
        outcome_required = filters.get("outcome") if isinstance(filters, dict) else None
        
        # Determine filters based on rule type
        event_type = None
        severity_min = None
        field = None
        expected_value = None
        
        condition_type = condition.get("type")
        if condition_type == "event_type":
            event_type = condition.get("value")
        elif condition_type == "severity_min":
            severity_min = int(condition.get("value", 0))
        elif condition_type == "field_value":
            field = condition.get("field")
            expected_value = condition.get("value")
        elif condition_type == "threshold_count":
            event_type = condition.get("value")
        
        group_value = getattr(event, group_by_field, None)
        if not group_value:
            return None
        
        count = await self._check_threshold_counts(
            tenant=event.tenant,
            group_field=group_by_field,
            group_value=group_value,
            window_end=event.timestamp,
            window_seconds=window_seconds,
            event_type=event_type,
            outcome_required=outcome_required
        )
        
        if count < threshold:
            return None
        
        return await self._upsert_alert(rule, event, group_value, count)
    
    async def _upsert_alert(
        self,
        rule: AlertRule,
        event: SecurityEvent,
        group_key: str,
        count: int
    ) -> Optional[Dict[str, Any]]:
        """Create or update alert using INSERT ... ON CONFLICT.
        
        If alert exists in OPEN state, update count and last_seen.
        Otherwise create new alert.
        """
        dedupe_key = f"{rule.id}:{group_key}"
        now = datetime.now(timezone.utc)
        
        # Try to update existing alert first
        result = await self.session.execute(
            select(Alert).where(
                Alert.dedupe_key == dedupe_key,
                Alert.status == AlertStatus.OPEN
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            existing.count = count
            existing.last_seen = event.timestamp
            if event.id not in existing.event_ids:
                existing.event_ids = list(existing.event_ids) + [event.id]
            if existing.first_seen is None or event.timestamp < existing.first_seen:
                existing.first_seen = event.timestamp
            # Merge tags from triggering event
            if event.tags:
                existing.tags = list(set(existing.tags or []) | set(event.tags))
            await self.session.merge(existing)
            return {
                "id": existing.id,
                "title": existing.title,
                "severity": existing.severity,
            }
        
        # Create new alert - include tags from the triggering event
        event_tags = event.tags or []
        
        # Combine rule description with tags marker if present
        base_description = rule.description or f"Threshold reached for {group_key}"
        
        stmt = insert(Alert).values(
            id=str(uuid.uuid4().hex[:25]),
            rule_id=rule.id,
            tenant=event.tenant,
            title=f"Alert: {rule.name}",
            description=base_description,
            severity=rule.severity,
            status=AlertStatus.OPEN,
            event_ids=[event.id],
            dedupe_key=dedupe_key,
            group_key=group_key,
            count=count,
            first_seen=event.timestamp,
            last_seen=event.timestamp,
            tags=list(event_tags),
        )
        
        stmt = stmt.on_conflict_do_nothing()
        
        await self.session.execute(stmt)
        await self.session.flush()
        
        # Get the newly created alert
        result = await self.session.execute(
            select(Alert).where(Alert.dedupe_key == dedupe_key)
        )
        created = result.scalar_one_or_none()
        
        if created:
            return {
                "id": created.id,
                "title": created.title,
                "severity": created.severity,
            }
        
        return None