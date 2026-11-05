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
from sqlalchemy import select, func, text, or_, and_
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
    
    async def evaluate_batch(self, events: List[SecurityEvent]) -> List[Dict[str, Any]]:
        """Evaluate a batch of events against all applicable rules.
        
        For each (tenant, rule, group_key) combination, runs ONE count query
        using the MAX @timestamp of matching events in the batch as window_end.
        """
        if not events:
            return []
        
        alerts = []
        
        # Get all unique tenants from events
        tenants = set(e.tenant for e in events if e.tenant)
        if not tenants:
            return alerts
        
        # Get all enabled rules for these tenants
        result = await self.session.execute(
            select(AlertRule).where(
                AlertRule.tenant.in_(tenants),
                AlertRule.enabled == True
            )
        )
        rules = result.scalars().all()
        
        if not rules:
            return alerts
        
        # Group events by tenant and filter for failures
        from collections import defaultdict
        events_by_tenant = defaultdict(list)
        for event in events:
            if event.tenant and event.outcome == "failure":
                events_by_tenant[event.tenant].append(event)
        
        # For each tenant and rule, evaluate
        for tenant, tenant_events in events_by_tenant.items():
            for rule in rules:
                if rule.tenant != tenant:
                    continue
                
                condition = rule.conditions[0] if rule.conditions else {}
                condition_type = condition.get("type")
                
                if condition_type != "repeated_failures":
                    continue
                
                group_by_field = condition.get("groupBy", "src_ip")
                threshold = int(condition.get("threshold", DEFAULT_THRESHOLD))
                window_seconds = int(condition.get("windowSeconds", DEFAULT_WINDOW_SECONDS))
                
                if group_by_field not in VALID_GROUP_BY_FIELDS:
                    continue
                
                # Group events by group_key value
                events_by_group = defaultdict(list)
                for event in tenant_events:
                    val = getattr(event, group_by_field, None)
                    if val:
                        events_by_group[val].append(event)
                
                # For each group_key, count events in window
                group_col = getattr(SecurityEvent, group_by_field)
                for group_value, group_events in events_by_group.items():
                    # window_end = newest stored matching event for this (tenant, group_key)
                    window_end = (await self.session.execute(
                        select(func.max(SecurityEvent.timestamp)).where(
                            SecurityEvent.tenant == tenant,
                            group_col == group_value,
                            SecurityEvent.outcome == "failure",
                        )
                    )).scalar_one_or_none()
                    if window_end is None:
                        continue
                    window_start = window_end - timedelta(seconds=window_seconds)
                    
                    # Count ALL matching events in the window (including pre-existing)
                    ts_col = SecurityEvent.timestamp
                    count_query = select(func.count()).select_from(SecurityEvent).where(
                        SecurityEvent.tenant == tenant,
                        ts_col >= window_start,
                        ts_col <= window_end,
                        group_col == group_value,
                        SecurityEvent.outcome == "failure",
                    )
                    
                    result = await self.session.execute(count_query)
                    count = result.scalar_one_or_none() or 0
                    
                    if count >= threshold:
                        event_ids, tags, first_seen, last_seen = await self._window_event_data(
                            tenant=tenant,
                            group_field=group_by_field,
                            group_value=group_value,
                            window_start=window_start,
                            window_end=window_end,
                        )
                        alert_data = await self._upsert_alert(
                            rule=rule,
                            tenant=tenant,
                            group_key=group_value,
                            count=count,
                            first_seen=first_seen,
                            last_seen=last_seen,
                            event_ids=event_ids,
                            tags=tags,
                        )
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
        
        ts_col = SecurityEvent.timestamp
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
        count = result.scalar_one_or_none() or 0
        return count
    
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
            logger.debug(f"_evaluate_repeated_failures: count {count} < threshold {threshold}, no alert")
            return None
        
        logger.debug(f"_evaluate_repeated_failures: count {count} >= threshold {threshold}, creating alert")
        window_end = event.timestamp
        window_start = window_end - timedelta(seconds=window_seconds)
        event_ids, tags, first_seen, last_seen = await self._window_event_data(
            tenant=event.tenant,
            group_field=group_by_field,
            group_value=group_value,
            window_start=window_start,
            window_end=window_end,
            outcome_required="failure",
        )
        return await self._upsert_alert(
            rule=rule,
            tenant=event.tenant,
            group_key=group_value,
            count=count,
            first_seen=first_seen,
            last_seen=last_seen,
            event_ids=event_ids,
            tags=tags,
        )
    
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
        
        window_end = event.timestamp
        window_start = window_end - timedelta(seconds=window_seconds)
        event_ids, tags, first_seen, last_seen = await self._window_event_data(
            tenant=event.tenant,
            group_field=group_by_field,
            group_value=group_value,
            window_start=window_start,
            window_end=window_end,
            outcome_required=outcome_required,
        )
        return await self._upsert_alert(
            rule=rule,
            tenant=event.tenant,
            group_key=group_value,
            count=count,
            first_seen=first_seen,
            last_seen=last_seen,
            event_ids=event_ids,
            tags=tags,
        )
    
    async def _window_event_data(
        self,
        *,
        tenant: str,
        group_field: str,
        group_value: str,
        window_start: datetime,
        window_end: datetime,
        outcome_required: Optional[str] = "failure",
    ):
        """Return (event_ids newest<=100, sorted unique tags, first_seen, last_seen) for a group window."""
        conditions = [
            SecurityEvent.tenant == tenant,
            SecurityEvent.timestamp >= window_start,
            SecurityEvent.timestamp <= window_end,
            getattr(SecurityEvent, group_field) == group_value,
        ]
        if outcome_required:
            conditions.append(SecurityEvent.outcome == outcome_required)
        
        result = await self.session.execute(
            select(SecurityEvent.id, SecurityEvent.tags, SecurityEvent.timestamp)
            .where(*conditions)
            .order_by(SecurityEvent.timestamp.desc())
            .limit(100)
        )
        rows = result.all()
        
        event_ids = [row.id for row in rows]
        tags = sorted({tag for row in rows for tag in (row.tags or [])})
        first_seen = min((row.timestamp for row in rows), default=window_start)
        last_seen = max((row.timestamp for row in rows), default=window_end)
        return event_ids, tags, first_seen, last_seen
    
    async def _upsert_alert(
        self,
        rule: AlertRule,
        tenant: str,
        group_key: str,
        count: int,
        first_seen: datetime,
        last_seen: datetime,
        event_ids: List[str],
        tags: List[str],
    ) -> Optional[Dict[str, Any]]:
        """Create or update the active alert atomically via INSERT ... ON CONFLICT DO UPDATE."""
        from sqlalchemy.dialects.postgresql import insert
        
        dedupe_key = f"{rule.id}:{tenant}:{group_key}"
        
        stmt = insert(Alert).values(
            id=uuid.uuid4().hex[:25],
            rule_id=rule.id,
            tenant=tenant,
            title=f"Alert: {rule.name}",
            description=f"[{rule.name}] {rule.description or f'Threshold reached for {group_key}'}",
            severity=rule.severity,
            status=AlertStatus.OPEN,
            event_ids=event_ids[:100],
            tags=tags,
            dedupe_key=dedupe_key,
            group_key=group_key,
            count=count,
            first_seen=first_seen,
            last_seen=last_seen,
        )
        
        stmt = stmt.on_conflict_do_update(
            index_elements=["dedupe_key"],
            index_where=text("status != 'resolved' AND dedupe_key IS NOT NULL"),
            set_={
                "count": stmt.excluded.count,
                "last_seen": func.greatest(Alert.last_seen, stmt.excluded.last_seen),
                "first_seen": func.least(Alert.first_seen, stmt.excluded.first_seen),
                "event_ids": stmt.excluded.event_ids,
                "tags": stmt.excluded.tags,
            },
        ).returning(Alert.id, Alert.title, Alert.description, Alert.severity, Alert.count)
        
        row = (await self.session.execute(stmt)).one()
        
        return {
            "id": row.id,
            "title": row.title,
            "description": row.description,
            "severity": row.severity,
            "count": row.count,
        }