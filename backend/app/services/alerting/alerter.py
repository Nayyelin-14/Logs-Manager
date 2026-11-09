from __future__ import annotations

import hashlib
import html
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import (
    Alert,
    AlertStatus,
    EmailNotification,
    EmailStatus,
    EmailType,
)
from app.core.config import get_settings
from app.services.notifier import (
    build_webhook_payload,
    is_valid_email,
    send_email_notification,
    send_webhook,
    append_notification,
)

logger = logging.getLogger(__name__)


def _dedupe_key(rule_id: str, tenant: str, group_value: str) -> str:
    return f"{rule_id}:{tenant}:{group_value}"


def _email_notification_id(alert_id: str, recipient: str) -> str:
    """Deterministic id so a redelivery upserts instead of duplicating."""
    digest = hashlib.sha256(
        f"{alert_id}|{EmailType.ALERT.value}|{recipient}".encode("utf-8")
    ).hexdigest()
    return digest[:40]


async def _persist_email_notification(
    session: AsyncSession,
    alert_obj: Alert,
    *,
    tenant: str,
    subject: str,
    recipient: str,
    result: dict[str, Any],
) -> None:
    """Record an email attempt in the existing ``email_notifications`` table.

    The insert/update is isolated in a savepoint so a persistence problem can
    never roll back the alert itself or block webhook delivery.
    """
    if not is_valid_email(recipient):
        return
    status_value = result.get("status")
    if status_value == "sent":
        email_status = EmailStatus.SENT
    elif status_value == "failed":
        email_status = EmailStatus.FAILED
    else:
        # Disabled/skipped providers did not attempt a delivery.
        return

    attempts = result.get("attempts") or []
    now = datetime.now(timezone.utc)
    notification_id = _email_notification_id(alert_obj.id, recipient)

    try:
        async with session.begin_nested():
            existing = await session.execute(
                select(EmailNotification).where(EmailNotification.id == notification_id)
            )
            row = existing.scalar_one_or_none()
            if row is None:
                row = EmailNotification(
                    id=notification_id,
                    alert_id=alert_obj.id,
                    email_type=EmailType.ALERT,
                    tenant=tenant,
                    recipient_email=recipient,
                    subject=subject[:500],
                    status=email_status,
                    attempts=0,
                )
                session.add(row)
            row.status = email_status
            row.attempts = int(row.attempts or 0) + max(1, len(attempts))
            row.last_attempt_at = now
            row.last_error = result.get("error")
            if email_status == EmailStatus.SENT:
                row.sent_at = now
            await session.flush()
    except Exception:  # noqa: BLE001 - notification bookkeeping is best-effort
        logger.exception(
            "failed to persist email notification: alert=%s recipient=%s",
            alert_obj.id,
            recipient,
        )


async def _deliver_notifications(
    session: AsyncSession,
    alert_obj: Alert,
    *,
    rule_id: str,
    rule_name: str,
    severity: str,
    tenant: str,
    group_by: str,
    group_value: str,
    count: int,
    window_minutes: int,
    first_seen: datetime,
    last_seen: datetime,
    notify: dict[str, Any],
) -> list[dict[str, Any]]:
    notifications: list[dict[str, Any]] = list(alert_obj.notifications or [])

    webhook_url = (notify or {}).get("webhook_url") if isinstance(notify, dict) else None
    email = (notify or {}).get("email") if isinstance(notify, dict) else None

    if webhook_url:
        try:
            payload = build_webhook_payload(
                alert_id=alert_obj.id,
                rule={
                    "id": rule_id,
                    "name": rule_name,
                    "severity": severity,
                    "type": "threshold",
                    "filter": (notify or {}).get("filter", {}),
                    "group_by": group_by,
                    "threshold": int((notify or {}).get("threshold", 5) or 5),
                    "window_minutes": window_minutes,
                },
                tenant=tenant,
                severity=severity,
                group_value=str(group_value),
                count=int(count),
                window_minutes=window_minutes,
                first_seen=(first_seen or last_seen).isoformat(),
                last_seen=(last_seen or first_seen).isoformat(),
                link=f"/alerts/{alert_obj.id}",
            )
            attempts = await send_webhook(webhook_url=webhook_url, payload=payload)
        except Exception as exc:  # noqa: BLE001 - webhook must not block email
            logger.exception("webhook delivery crashed: alert=%s", alert_obj.id)
            attempts = [{
                "attempt": 1,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "failed",
                "http_code": None,
                "error": f"{type(exc).__name__}: {exc}",
            }]
        notifications = append_notification(notifications, "webhook", attempts, webhook_url)

    settings = get_settings()
    email_recipient = (settings.ALERT_EMAIL_TO or "").strip() or (email or "").strip()

    if email_recipient and is_valid_email(email_recipient):
        subject = f"[{severity.upper()}] {rule_name}"
        alert_description = alert_obj.description or rule_name
        safe = {
            "rule_name": html.escape(str(rule_name)),
            "tenant": html.escape(str(tenant)),
            "description": html.escape(str(alert_description)),
            "group_by": html.escape(str(group_by)),
            "group_value": html.escape(str(group_value)),
        }
        html_body = (
            f"<h2>Security Alert: {safe['rule_name']}</h2>"
            f"<p><b>Severity:</b> {severity.upper()}</p>"
            f"<p><b>Tenant:</b> {safe['tenant']}</p>"
            f"<p><b>Alert ID:</b> {alert_obj.id}</p>"
            f"<p><b>Description:</b> {safe['description']}</p>"
            f"<p><b>Group field:</b> {safe['group_by']}</p>"
            f"<p><b>Group value:</b> {safe['group_value']}</p>"
            f"<p><b>Event count:</b> {count}</p>"
            f"<p><b>Window:</b> {window_minutes} minutes</p>"
            f"<p><b>First seen:</b> {first_seen or last_seen}</p>"
            f"<p><b>Last seen:</b> {last_seen or first_seen}</p>"
        )
        text_body = (
            f"Security Alert: {rule_name}\n"
            f"Severity: {severity.upper()}\n"
            f"Tenant: {tenant}\n"
            f"Alert ID: {alert_obj.id}\n"
            f"Description: {alert_description}\n"
            f"Group field: {group_by}\n"
            f"Group value: {group_value}\n"
            f"Event count: {count}\n"
            f"Window: {window_minutes} minutes\n"
            f"First seen: {first_seen or last_seen}\n"
            f"Last seen: {last_seen or first_seen}\n"
        )
        try:
            email_result = await send_email_notification(
                recipient=email_recipient,
                subject=subject,
                html_body=html_body,
                text_body=text_body,
            )
        except Exception as exc:  # noqa: BLE001 - email must not block the alert
            logger.exception("email delivery crashed: alert=%s", alert_obj.id)
            email_result = {
                "status": "failed",
                "error": f"{type(exc).__name__}: {exc}",
                "attempts": [],
            }

        attempts = email_result.get("attempts") or []
        notifications = append_notification(
            notifications, "email", attempts, email_recipient
        )
        notification = notifications[-1]
        email_status = email_result.get("status") or notification["status"]
        notification["status"] = email_status
        notification["final_status"] = email_status
        notification["error"] = email_result.get("error")
        notification["sent_at"] = (
            datetime.now(timezone.utc).isoformat()
            if email_status == "sent"
            else notification.get("sent_at")
        )
        await _persist_email_notification(
            session,
            alert_obj,
            tenant=tenant,
            subject=subject,
            recipient=email_recipient,
            result=email_result,
        )
    elif email_recipient:
        # Recipient configured but invalid; record a safe failure without
        # leaking the value.
        notifications = append_notification(
            notifications,
            "email",
            [{
                "attempt": 1,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "failed",
                "http_code": None,
                "error": "invalid_recipient",
            }],
            "<invalid-recipient>",
        )

    alert_obj.notifications = notifications
    await session.flush()
    return notifications


async def create_or_update_alert(
    session: AsyncSession,
    *,
    rule_id: str,
    rule_name: str,
    rule_severity: str,
    tenant: str,
    group_by: str,
    group_value: str,
    count: int,
    first_seen: datetime,
    last_seen: datetime,
    evidence_ids: list[str],
    tags: list[str],
    window_minutes: int,
    notify: dict[str, Any],
    now: datetime,
) -> dict[str, Any]:
    dedupe_key = _dedupe_key(rule_id, tenant, str(group_value))
    severity = str(rule_severity or "medium")


    cooldown_minutes = int((notify or {}).get("cooldown_minutes", 15) or 15)
    cooldown_start = now - timedelta(minutes=cooldown_minutes)

    def _merge_event_ids(existing_ids: list[str] | None, new_ids: list[str]) -> list[str]:
        merged = list(
            dict.fromkeys(
                list(existing_ids or [])
                + [eid for eid in new_ids if eid not in (existing_ids or [])]
            )
        )
        return merged[:100]


    existing = await session.execute(
        select(Alert).where(
            Alert.dedupe_key == dedupe_key,
            Alert.status != AlertStatus.RESOLVED,
        )
    )
    existing_alert = existing.scalar_one_or_none()

    if existing_alert:
        was_within_cooldown = (
            existing_alert.last_seen is not None and existing_alert.last_seen >= cooldown_start
        )


        new_eids = [
            eid for eid in evidence_ids
            if eid not in (existing_alert.event_ids or [])
        ]
        existing_alert.count = int(existing_alert.count or 0) + len(new_eids)
        existing_alert.last_seen = last_seen or now
        existing_alert.event_ids = _merge_event_ids(existing_alert.event_ids, evidence_ids)
        await session.flush()

        notified = False
        if not was_within_cooldown:

            await _deliver_notifications(
                session,
                existing_alert,
                rule_id=rule_id,
                rule_name=rule_name,
                severity=severity,
                tenant=tenant,
                group_by=group_by,
                group_value=str(group_value),
                count=int(count),
                window_minutes=window_minutes,
                first_seen=first_seen or now,
                last_seen=last_seen or now,
                notify=notify,
            )
            notified = True

        return {
            "id": existing_alert.id,
            "rule_id": rule_id,
            "tenant": tenant,
            "dedupe_key": dedupe_key,
            "group_value": str(group_value),
            "count": int(existing_alert.count),
            "status": existing_alert.status,
            "notified": notified,
        }




    alert_obj = Alert(
        id=uuid.uuid4().hex[:25],
        rule_id=rule_id,
        tenant=tenant,
        title=f"Alert: {rule_name}",
        description=f"[{rule_name}] threshold reached for {group_by}={group_value} "
        f"({count} events in {window_minutes} min)",
        severity=severity,
        status=AlertStatus.OPEN,
        event_ids=evidence_ids[:100],
        dedupe_key=dedupe_key,
        group_value=str(group_value),
        count=int(count),
        first_seen=first_seen or now,
        last_seen=last_seen or now,
        tags=tags[:50],
        notifications=[],
    )
    session.add(alert_obj)

    try:
        async with session.begin_nested():
            await session.flush()
    except IntegrityError:
        existing = await session.execute(
            select(Alert).where(
                Alert.dedupe_key == dedupe_key,
                Alert.status != AlertStatus.RESOLVED,
            )
        )
        existing_alert = existing.scalar_one_or_none()
        if existing_alert is None:
            raise
        new_eids = [
            eid for eid in evidence_ids
            if eid not in (existing_alert.event_ids or [])
        ]
        existing_alert.count = int(existing_alert.count or 0) + len(new_eids)
        existing_alert.last_seen = last_seen or now
        existing_alert.event_ids = _merge_event_ids(existing_alert.event_ids, evidence_ids)
        await session.flush()



        was_within_cooldown = (
            existing_alert.last_seen is not None and existing_alert.last_seen >= cooldown_start
        )
        notified = False
        if not was_within_cooldown:
            await _deliver_notifications(
                session,
                existing_alert,
                rule_id=rule_id,
                rule_name=rule_name,
                severity=severity,
                tenant=tenant,
                group_by=group_by,
                group_value=str(group_value),
                count=int(count),
                window_minutes=window_minutes,
                first_seen=first_seen or now,
                last_seen=last_seen or now,
                notify=notify,
            )
            notified = True

        return {
            "id": existing_alert.id,
            "rule_id": rule_id,
            "tenant": tenant,
            "dedupe_key": dedupe_key,
            "group_value": str(group_value),
            "count": int(existing_alert.count),
            "status": existing_alert.status,
            "notified": notified,
        }


    await _deliver_notifications(
        session,
        alert_obj,
        rule_id=rule_id,
        rule_name=rule_name,
        severity=severity,
        tenant=tenant,
        group_by=group_by,
        group_value=str(group_value),
        count=int(count),
        window_minutes=window_minutes,
        first_seen=first_seen or now,
        last_seen=last_seen or now,
        notify=notify,
    )

    return {
        "id": alert_obj.id,
        "rule_id": rule_id,
        "tenant": tenant,
        "dedupe_key": dedupe_key,
        "group_value": str(group_value),
        "count": int(count),
        "status": "open",
        "notified": True,
    }
