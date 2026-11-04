"""
Alert Service

Alert rule evaluation engine and alert management.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert, AlertRule
from app.models.security_event import SecurityEvent
from app.integrations.queue import enqueue_alert_email
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

DEFAULT_WINDOW_SECONDS = 300
DEFAULT_COOLDOWN_SECONDS = 600
BRUTE_FORCE_THRESHOLD = 5
BRUTE_FORCE_WINDOW_SECONDS = 300
MALWARE_SEVERITY = 8


class AlertService:
    """Alert rule evaluation engine."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def check_alerts(self, event: "SecurityEvent") -> List[dict]:
        """Check event against all enabled alert rules for the tenant."""
        result = await self.session.execute(
            select(AlertRule).where(
                AlertRule.tenant == event.tenant,
                AlertRule.enabled == True
            )
        )
        rules = result.scalars().all()
        
        triggered = []
        for rule in rules:
            if await self._evaluate_rule(rule, event):
                alert = await self._create_alert(rule, event)
                if alert:
                    triggered.append({
                        "id": alert.id,
                        "title": alert.title,
                        "severity": alert.severity,
                    })
        
        return triggered
    
    async def _evaluate_rule(self, rule: AlertRule, event: "SecurityEvent") -> bool:
        """Evaluate a single rule against an event."""
        if not rule.conditions or len(rule.conditions) == 0:
            return False
        
        condition = rule.conditions[0]
        ctype = condition.get("type")
        
        if ctype == "event_type":
            # Match on canonical event type
            return event.canonical_event_type == condition.get("value")
        
        elif ctype == "severity_min":
            return (event.severity or 0) >= condition.get("value", 0)
        
        elif ctype == "field_value":
            field = condition.get("field")
            value = condition.get("value")
            if not field or value is None:
                return False
            return getattr(event, field, None) == value
        
        elif ctype in ["threshold_count", "repeated_failures"]:
            return await self._evaluate_threshold(rule, event, condition)
        
        return False
    
    async def _evaluate_threshold(
        self,
        rule: AlertRule,
        event: "SecurityEvent",
        condition: Dict[str, Any]
    ) -> bool:
        """Evaluate threshold-based conditions."""
        threshold = condition.get("threshold", BRUTE_FORCE_THRESHOLD)
        window = condition.get("windowSeconds", BRUTE_FORCE_WINDOW_SECONDS)
        
        window_start = datetime.now(timezone.utc) - timedelta(seconds=window)
        
        # Build query based on condition type
        query = select(func.count()).select_from(SecurityEvent).where(
            SecurityEvent.tenant == event.tenant,
            SecurityEvent.timestamp >= window_start,
        )
        
        if condition.get("type") == "repeated_failures":
            # Count authentication failures from same source
            query = query.where(
                (SecurityEvent.action == "LOGIN") & (SecurityEvent.severity >= 5) |
                (SecurityEvent.canonical_event_type.in_(["ad_logon_failed", "login_failed", "logon_failed"])) |
                (SecurityEvent.canonical_event_type == "UserLoggedIn" and SecurityEvent.status == "Failure") |
                (SecurityEvent.canonical_event_type == "MailboxLogin" and SecurityEvent.status == "Failure")
            )
        else:
            # threshold_count uses canonical event type
            query = query.where(SecurityEvent.canonical_event_type == event.canonical_event_type)
        
        # Group by source IP
        query = query.where(SecurityEvent.src_ip == event.src_ip)
        
        count = await self.session.execute(query)
        return count.scalar() >= threshold
    
    async def _create_alert(self, rule: AlertRule, event: "SecurityEvent") -> Optional["Alert"]:
        """Create an alert record with deduplication."""
        from app.models.alert import Alert
        
        condition = rule.conditions[0]
        window_start = datetime.now(timezone.utc) - timedelta(
            seconds=condition.get("windowSeconds", DEFAULT_WINDOW_SECONDS)
        )
        
        # Generate deduplication key
        group_field = "src_ip"
        group_value = event.src_ip or event.user or event.host or "unknown"
        dedupe_key = f"{rule.id}:{rule.conditions[0]['type']}:{group_field}:{group_value}"
        
        # Check for existing alert in cooldown window
        cooldown = condition.get("cooldownSeconds", DEFAULT_COOLDOWN_SECONDS)
        cooldown_start = datetime.now(timezone.utc) - timedelta(seconds=cooldown)
        
        existing = await self.session.execute(
            select(Alert).where(
                Alert.rule_id == rule.id,
                Alert.dedupe_key == dedupe_key,
                Alert.triggered_at >= cooldown_start
            )
        )
        if existing.scalar_one_or_none():
            return None
        
        # Determine severity
        severity = rule.severity
        condition_type = rule.conditions[0].get("type") if rule.conditions else None
        if condition_type == "severity_min":
            severity = rule.conditions[0].get("value", severity)
        elif condition_type == "event_type":
            # For event_type-based rules (e.g., malware), ensure severity >= 8
            # if the rule name or condition suggests a threat/malware type event
            lower_name = rule.name.lower() if rule.name else ""
            lower_cond_val = str(rule.conditions[0].get("value", "")).lower() if rule.conditions else ""
            if any(kw in lower_name or kw in lower_cond_val for kw in ["malware", "threat", "detect", " virus"]):
                severity = max(severity, MALWARE_SEVERITY)
            # Otherwise keep the rule's configured severity
        
        # Find recipient
        recipient_email = await self._find_recipient(event, event.tenant)
        
        # Create alert
        from app.models.alert import Alert as AlertModel
        alert_obj = AlertModel(
            id=uuid.uuid4().hex[:25],
            rule_id=rule.id,
            tenant=event.tenant,
            title=f"Alert: {rule.name}",
            description=rule.description or f"{rule.name} triggered for {event.src_ip or event.user or 'unknown'}",
            severity=severity,
            status="open",
            event_ids=[event.id],
            dedupe_key=dedupe_key,
        )
        
        self.session.add(alert_obj)
        await self.session.flush()
        
        # Queue email notification (best-effort: never fail alert creation on Redis)
        if recipient_email:
            try:
                await enqueue_alert_email(
                    email=recipient_email,
                    username=event.user or "analyst",
                    tenant=event.tenant,
                    title=alert_obj.title,
                    description=alert_obj.description,
                    severity=alert_obj.severity,
                    alert_id=alert_obj.id,
                )
            except Exception as exc:
                logger.warning("alert email enqueue failed: %s", exc)
        
        return alert_obj
    
    async def _find_recipient(self, event: "SecurityEvent", tenant: str) -> Optional[str]:
        """Find email recipient for alert notification."""
        from app.models.user import User
        
        if event.user:
            result = await self.session.execute(
                select(User).where(
                    User.tenant == tenant,
                    User.status == "ACTIVE",
                    or_(User.username == event.user, User.email == event.user)
                )
            )
            user = result.scalar_one_or_none()
            if user and user.email:
                return user.email
        
        # Fallback to tenant admin
        result = await self.session.execute(
            select(User).where(
                User.tenant == tenant,
                User.role == "ADMIN",
                User.status == "ACTIVE"
            )
        )
        admin = result.scalar_one_or_none()
        return admin.email if admin else None