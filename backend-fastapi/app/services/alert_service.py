"""
Alert Service

Alert rule evaluation engine and alert management.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert, AlertRule, EmailNotification, EmailType, EmailStatus
from app.models.security_event import SecurityEvent
from app.integrations.email import send_alert_email
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

DEFAULT_WINDOW_SECONDS = 300
DEFAULT_COOLDOWN_SECONDS = 600
BRUTE_FORCE_THRESHOLD = 5
BRUTE_FORCE_WINDOW_SECONDS = 300
MALWARE_SEVERITY = 8

GROUP_BY_FIELDS = {
    "srcIp": "src_ip",
    "user": "user",
    "host": "host",
}

FIELD_ALIASES = {
    "eventType": "event_type",
    "srcIp": "src_ip",
    "dstIp": "dst_ip",
    "sourceIp": "src_ip",
    "destinationIp": "dst_ip",
}

SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}


def _as_int(value: Any, default: int) -> int:
    """Coerce rule values (which the UI sends as strings) to int."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _severity_name(value: Any) -> str:
    """Normalize a severity to one of low/medium/high/critical."""
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in SEVERITY_RANK:
            return normalized
        try:
            value = int(normalized)
        except ValueError:
            return "medium"

    try:
        score = int(value)
    except (TypeError, ValueError):
        return "medium"

    if score >= 9:
        return "critical"
    if score >= 7:
        return "high"
    if score >= 4:
        return "medium"
    return "low"


def _group_field(condition: Dict[str, Any]) -> str:
    """Resolve the groupBy option to the SecurityEvent column name."""
    return GROUP_BY_FIELDS.get(condition.get("groupBy"), "src_ip")


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
            return (event.severity or 0) >= _as_int(condition.get("value"), 0)
        
        elif ctype == "field_value":
            field = FIELD_ALIASES.get(condition.get("field"), condition.get("field"))
            value = condition.get("value")
            if not field or value is None:
                return False
            actual = getattr(event, field, None)
            if isinstance(actual, (int, float)) and not isinstance(actual, bool) and isinstance(value, str):
                try:
                    value = type(actual)(value)
                except ValueError:
                    return False
            return actual == value
        
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
        threshold = _as_int(condition.get("threshold"), BRUTE_FORCE_THRESHOLD)
        window = _as_int(condition.get("windowSeconds"), BRUTE_FORCE_WINDOW_SECONDS)
        
        window_start = datetime.now(timezone.utc) - timedelta(seconds=window)
        
        # Build query based on condition type
        query = select(func.count()).select_from(SecurityEvent).where(
            SecurityEvent.tenant == event.tenant,
            SecurityEvent.timestamp >= window_start,
        )
        
        if condition.get("type") == "repeated_failures":
            # Count authentication failures from the same group
            query = query.where(
                or_(
                    and_(SecurityEvent.action == "LOGIN", SecurityEvent.severity >= 5),
                    SecurityEvent.canonical_event_type.in_(
                        ["ad_logon_failed", "login_failed", "logon_failed"]
                    ),
                )
            )
        else:
            # threshold_count uses canonical event type
            query = query.where(SecurityEvent.canonical_event_type == event.canonical_event_type)
        
        # Group by the configured field (src IP by default)
        group_field = _group_field(condition)
        query = query.where(
            getattr(SecurityEvent, group_field) == getattr(event, group_field, None)
        )
        
        count = await self.session.execute(query)
        return count.scalar() >= threshold
    
    async def _create_alert(self, rule: AlertRule, event: "SecurityEvent") -> Optional["Alert"]:
        """Create an alert record with deduplication."""
        from app.models.alert import Alert
        
        condition = rule.conditions[0]
        
        # Generate deduplication key using the same field the rule groups by
        group_field = _group_field(condition)
        group_value = getattr(event, group_field, None) or "unknown"
        dedupe_key = f"{rule.id}:{condition['type']}:{group_field}:{group_value}"
        
        # Check for existing alert in cooldown window
        cooldown = _as_int(condition.get("cooldownSeconds"), DEFAULT_COOLDOWN_SECONDS)
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
        
        # Determine severity (always a UI-compatible string)
        severity = _severity_name(rule.severity)
        condition_type = condition.get("type")
        if condition_type == "event_type":
            # For event_type-based rules (e.g., malware), ensure severity is at
            # least the malware floor if the rule suggests a threat/malware event.
            lower_name = rule.name.lower() if rule.name else ""
            lower_cond_val = str(condition.get("value", "")).lower()
            if any(kw in lower_name or kw in lower_cond_val for kw in ["malware", "threat", "detect", " virus"]):
                malware_floor = _severity_name(MALWARE_SEVERITY)
                if SEVERITY_RANK[severity] < SEVERITY_RANK[malware_floor]:
                    severity = malware_floor

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

        # Deliver alert notifications. Never fail alert creation because of SMTP.
        if settings.ALERT_EMAIL_ENABLED:
            recipients = await self._find_recipients(event, event.tenant)
            for recipient_email in recipients:
                await self._send_alert_notification(alert_obj, event, recipient_email)

        return alert_obj

    async def _send_alert_notification(
        self,
        alert_obj: "Alert",
        event: "SecurityEvent",
        recipient_email: str,
    ) -> None:
        """Send (and track) an alert email for one recipient."""
        severity = _severity_name(alert_obj.severity)
        notification_id = f"alert:{alert_obj.id}:type:alert:to:{recipient_email}"
        notification = await self.session.get(EmailNotification, notification_id)
        if notification is None:
            notification = EmailNotification(
                id=notification_id,
                alert_id=alert_obj.id,
                email_type=EmailType.ALERT,
                tenant=alert_obj.tenant,
                recipient_email=recipient_email,
                subject=f"[ALERT] {alert_obj.title} - Severity: {severity.upper()} at {alert_obj.tenant}",
                status=EmailStatus.PENDING,
                attempts=0,
            )
            self.session.add(notification)

        notification.status = EmailStatus.RETRYING
        notification.attempts += 1
        notification.last_attempt_at = datetime.now(timezone.utc)
        await self.session.flush()

        try:
            result = await send_alert_email(
                email=recipient_email,
                username=event.user or "analyst",
                tenant=alert_obj.tenant,
                title=alert_obj.title,
                description=alert_obj.description,
                severity=severity,
            )
            if result.get("success"):
                notification.status = EmailStatus.SENT
                notification.sent_at = datetime.now(timezone.utc)
                notification.last_error = None
            else:
                notification.status = EmailStatus.FAILED
                notification.last_error = result.get("message")
                logger.warning(
                    "alert email not sent to %s: %s",
                    recipient_email,
                    result.get("message"),
                )
        except Exception as exc:
            notification.status = EmailStatus.FAILED
            notification.last_error = str(exc)
            logger.exception("alert email failed for %s: %s", recipient_email, exc)

        await self.session.flush()

    async def _find_recipients(self, event: "SecurityEvent", tenant: str) -> List[str]:
        """Find email recipients for alert notification (deduplicated)."""
        from app.models.user import User

        recipients: List[str] = []

        if event.user:
            result = await self.session.execute(
                select(User).where(
                    User.tenant == tenant,
                    User.status == "ACTIVE",
                    or_(User.username == event.user, User.email == event.user)
                )
            )
            user = result.scalars().first()
            if user and user.email:
                recipients.append(user.email)

        # Fallback to tenant admin
        result = await self.session.execute(
            select(User).where(
                User.tenant == tenant,
                User.role == "ADMIN",
                User.status == "ACTIVE"
            )
        )
        admin = result.scalars().first()
        if admin and admin.email:
            recipients.append(admin.email)

        # Explicit extra recipients from ALERT_EMAIL_RECIPIENTS
        for addr in settings.ALERT_EMAIL_RECIPIENTS.replace(";", ",").split(","):
            addr = addr.strip()
            if addr:
                recipients.append(addr)

        return list(dict.fromkeys(recipients))
