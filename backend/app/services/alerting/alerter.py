from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert, AlertStatus
from app.services.notifier import (
    build_webhook_payload,
    send_webhook,
    append_notification,
    send_email,
)

logger = logging.getLogger(__name__)


def _dedupe_key(rule_id: str, tenant: str, group_value: str) -> str:
    return f"{rule_id}:{tenant}:{group_value}"


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
    notifications: list[dict[str, Any]] = []

    webhook_url = (notify or {}).get("webhook_url") if isinstance(notify, dict) else None
    email = (notify or {}).get("email") if isinstance(notify, dict) else None

    if webhook_url:
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
        notifications = append_notification(notifications, "webhook", attempts, webhook_url)

    if email:
        email_result = await send_email(
            recipient=email,
            subject=f"[ALERT] {rule_name} - {severity}",
            body=f"Alert triggered for {group_by}={group_value} "
            f"({count} events in {window_minutes} min) on tenant {tenant}",
            smtp_host="",
            smtp_port=587,
            smtp_username=None,
            smtp_password=None,
            use_tls=True,
        )
        notifications = append_notification(notifications, "email", [], email)
        if notifications and notifications[-1]["channel"] == "email":
            notifications[-1]["attempts"] = [{
                "attempt": 1,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": email_result.get("status", "failed"),
                "http_code": None,
                "error": email_result.get("error"),
            }]
            notifications[-1]["final_status"] = email_result.get("status", "failed")

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
