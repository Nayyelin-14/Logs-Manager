from __future__ import annotations
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, func, and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.alert import AlertRule
from app.models.events import Event
from app.services.alerting.alerter import create_or_update_alert
logger = logging.getLogger(__name__)

VALID_GROUP_BY = {"src_ip", "user_name", "host"}


def _normalize_identifier(value: Any) -> str:
    """Case- and separator-insensitive identifier for rule filters.

    CrowdStrike emits ``MalwareDetected`` while seed rules use
    ``malware_detected``; both must match. Underscores and hyphens are ignored.
    """
    return str(value or "").strip().lower().replace("_", "").replace("-", "")


def _sql_normalized(column):
    return func.lower(func.replace(func.replace(column, "_", ""), "-", ""))


def _build_filter_conditions(rule: AlertRule) -> list:
    conditions: list = []
    filter_json = rule.filter or {}
    if not isinstance(filter_json, dict):
        filter_json = {}
    if not filter_json:
        cond_json = rule.conditions or {}
        if isinstance(cond_json, dict):
            ctype = cond_json.get("type", "")
            cvalue = cond_json.get("value", "")
            if ctype == "event_type" and cvalue:
                filter_json["event_type"] = cvalue
            elif ctype == "severity_min" and cvalue:
                try:
                    filter_json["severity_gte"] = int(cvalue)
                except (ValueError, TypeError):
                    pass
            elif ctype == "threshold_count" and cvalue:
                filter_json["event_type"] = cvalue
            elif ctype == "field_value":
                cfield = cond_json.get("field", "")
                if cfield:
                    filter_json[cfield] = cvalue
    if filter_json.get("outcome"):
        conditions.append(Event.outcome == filter_json["outcome"])
    if filter_json.get("action"):
        conditions.append(Event.action == filter_json["action"])
    if filter_json.get("source"):
        conditions.append(Event.source == filter_json["source"])
    if filter_json.get("event_type"):
        value = _normalize_identifier(filter_json["event_type"])
        if value:
            conditions.append(_sql_normalized(Event.event_type) == value)
    severity_gte = filter_json.get("severity_gte")
    if severity_gte is not None:
        try:
            conditions.append(Event.severity >= int(severity_gte))
        except (ValueError, TypeError):
            pass
    return conditions
async def _get_evidence_ids(
    session: AsyncSession,
    tenant: str,
    group_by: str,
    group_value: str,
    window_start: datetime,
    rule: AlertRule,
) -> tuple[list[str], list[str]]:
    group_column = getattr(Event, group_by, None)
    if group_column is None:
        return [], []
    conditions = [
        Event.tenant == tenant,
        Event.ts >= window_start,
        group_column == group_value,
    ]
    conditions.extend(_build_filter_conditions(rule))
    result = await session.execute(
        select(Event.id, Event._tags)
        .where(*conditions)
        .order_by(Event.ts.desc())
        .limit(100)
    )
    rows = result.all()
    event_ids = [row[0] for row in rows]
    tags = sorted({tag for row in rows for tag in (row[1] or [])})
    return event_ids, tags
async def evaluate_rule(
    session: AsyncSession,
    rule: AlertRule,
    now: datetime,
) -> list[dict[str, Any]]:
    if not rule.enabled:
        return []
    rule_id = rule.id
    rule_name = rule.name
    rule_tenant = rule.tenant or None
    condition_type = getattr(rule, "rule_type", None) or "threshold"
    if condition_type not in ("threshold", "repeated_failures"):
        return []
    group_by = getattr(rule, "group_by", None) or "src_ip"
    if isinstance(group_by, str):
        group_by = group_by.strip().strip("'").strip('"')
    if group_by not in VALID_GROUP_BY:
        logger.warning("rule %s has invalid group_by=%s, skipping", rule_id, group_by)
        return []
    threshold = int(getattr(rule, "threshold", 5) or 5)
    window_minutes = int(getattr(rule, "window_minutes", 5) or 5)
    window_seconds = window_minutes * 60
    group_column = getattr(Event, group_by, None)
    if group_column is None:
        return []
    window_start = now - timedelta(seconds=window_seconds)
    count_col = func.count(Event.id)
    select_cols = [
        group_column.label("group_value"),
        count_col.label("cnt"),
        func.min(Event.ts).label("first_seen"),
        func.max(Event.ts).label("last_seen"),
    ]
    group_by_cols = [group_column]
    filter_conditions = _build_filter_conditions(rule)
    query = select(*select_cols).where(Event.ts >= window_start, *filter_conditions)
    if rule_tenant and rule_tenant != "*":
        query = query.where(Event.tenant == rule_tenant)
    else:
        select_cols.append(Event.tenant.label("tenant"))
        query = select(*select_cols).where(Event.ts >= window_start, *filter_conditions)
        group_by_cols.append(Event.tenant)
    query = query.having(count_col >= threshold).group_by(*group_by_cols)
    try:
        result = await session.execute(query)
        rows = result.all()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        logger.exception("rule %s evaluation query failed: %s", rule_id, exc)
        return []
    alerts_created: list[dict[str, Any]] = []
    notify = getattr(rule, "notify", None) or {}
    for row in rows:
        if rule_tenant and rule_tenant != "*":
            group_value = row.group_value
            tenant = rule_tenant
            first_seen = row.first_seen
            last_seen = row.last_seen
            count = row.cnt
        else:
            tenant = row.tenant
            group_value = row.group_value
            first_seen = row.first_seen
            last_seen = row.last_seen
            count = row.cnt

        if not group_value:
            continue

        evidence_ids, tags = await _get_evidence_ids(
            session, tenant, group_by, str(group_value), window_start, rule
        )
        try:
            alert_data = await create_or_update_alert(
                session,
                rule_id=rule_id,
                rule_name=rule_name,
                rule_severity=rule.severity,
                tenant=tenant,
                group_by=group_by,
                group_value=str(group_value),
                count=int(count),
                first_seen=first_seen or now,
                last_seen=last_seen or now,
                evidence_ids=evidence_ids,
                tags=tags,
                window_minutes=window_minutes,
                notify=notify,
                now=now,
            )
            alerts_created.append(alert_data)
        except IntegrityError:
            await session.rollback()
            logger.exception(
                "alert creation hit duplicate dedupe_key for rule %s (%s); converted to update",
                rule_id,
                rule_name,
            )
            continue
        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            logger.exception("alert creation failed for rule %s (%s): %s", rule_id, rule_name, exc)
    return alerts_created
async def evaluate_all_rules(
    session: AsyncSession,
    now: datetime,
) -> list[dict[str, Any]]:
    result = await session.execute(
        select(AlertRule).where(AlertRule.enabled == True)  # noqa: E712
    )
    rules = result.scalars().all()
    all_alerts: list[dict[str, Any]] = []
    for rule in rules:

        rule_id = rule.id
        rule_name = rule.name
        try:
            rule_alerts = await evaluate_rule(session, rule, now)
            all_alerts.extend(rule_alerts)
        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            logger.exception("rule %s (%s) evaluation failed: %s", rule_id, rule_name, exc)
    return all_alerts
