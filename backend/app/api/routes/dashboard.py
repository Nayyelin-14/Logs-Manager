from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

from app.core.database import get_session
from app.core.dependencies import get_current_user, get_effective_tenant
from app.core.security import TokenPayload
from app.core.tenancy import resolve_read_tenant
from app.api.routes.search import VALID_SOURCES
from app.models.events import Event
from app.models.alert import Alert, AlertRule
from app.models.tenant import Tenant

router = APIRouter()


def _validate_source(source: Optional[str]) -> Optional[str]:
    if source is None or not str(source).strip():
        return None
    value = str(source).strip().lower()
    if value not in VALID_SOURCES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Unsupported source '{source}'. "
                f"Valid sources: {', '.join(sorted(VALID_SOURCES))}."
            ),
        )
    return value


def _iso_utc(value):
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


class DashboardStats(BaseModel):
    totalEvents: int
    topIPs: List[Dict[str, Any]]
    topUsers: List[Dict[str, Any]]
    topEventTypes: List[Dict[str, Any]]
    eventsBySource: List[Dict[str, Any]]
    alertsByDay: List[Dict[str, Any]]
    alertsRuleByDay: List[Dict[str, Any]]
    recentAlert: List[Dict[str, Any]]
    severityCounts: List[Dict[str, Any]]
    sources: List[Dict[str, Any]]
    eventsByTenant: List[Dict[str, Any]]
    alertCountsByStatus: List[Dict[str, Any]]
    alertCountsBySeverity: List[Dict[str, Any]]
    ruleCountsByEnabled: List[Dict[str, Any]]
    tenants: List[Dict[str, Any]]


@router.get("/dashboard", response_model=dict)
async def get_dashboard_stats(
    tenant: Optional[str] = None,
    range: str = "7d",
    source: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    current_user: "TokenPayload" = Depends(get_current_user),
):

    source = _validate_source(source)
    tenant = resolve_read_tenant(current_user, tenant)
    range_days = {"1d": 1, "3d": 3, "7d": 7, "30d": 30}.get(range, 7)

    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=range_days)
    # A one-day window is only useful at hour resolution; wider windows use days.
    bucket_unit = "hour" if range_days <= 1 else "day"

    # Source and tenant filters are applied to every event aggregate, so the
    # top lists, timeline and source distribution all describe the same scope.
    event_conditions = [Event.ts.between(start_date, end_date)]
    if tenant:
        event_conditions.append(Event.tenant == tenant)
    if source:
        event_conditions.append(Event.source == source)

    alert_conditions = []
    if tenant:
        alert_conditions.append(Alert.tenant == tenant)

    total_events = await session.execute(
        select(func.count()).select_from(Event).where(*event_conditions)
    )

    top_ips = await session.execute(
        select(Event.src_ip, func.count().label("count"))
        .where(*event_conditions)
        .where(Event.src_ip.isnot(None))
        .group_by(Event.src_ip)
        .order_by(desc("count"))
        .limit(10)
    )

    top_users = await session.execute(
        select(Event.user_name, func.count().label("count"))
        .where(*event_conditions)
        .where(Event.user_name.isnot(None))
        .group_by(Event.user_name)
        .order_by(desc("count"))
        .limit(10)
    )

    top_event_types = await session.execute(
        select(Event.event_type, func.count().label("count"))
        .where(*event_conditions)
        .group_by(Event.event_type)
        .order_by(desc("count"))
        .limit(10)
    )

    events_by_source = await session.execute(
        select(
            Event.tenant,
            func.date_trunc(bucket_unit, Event.ts).label("day"),
            Event.source,
            func.count().label("count"),
        )
        .where(*event_conditions)
        .group_by(Event.tenant, "day", Event.source)
        .order_by("day")
    )

    recent_alerts = await session.execute(
        select(Alert)
        .where(*alert_conditions)
        .order_by(desc(Alert.triggered_at))
        .limit(5)
    )

    sources = await session.execute(
        select(Event.source, func.count().label("count"), func.max(Event.ts).label("latest"))
        .where(*event_conditions)
        .group_by(Event.source)
        .order_by(desc("count"))
    )

    severity_counts = await session.execute(
        select(Event.severity, func.count().label("count"))
        .where(*event_conditions)
        .group_by(Event.severity)
        .order_by(Event.severity)
    )

    events_by_tenant = await session.execute(
        select(Event.tenant, func.count().label("count"))
        .where(*event_conditions)
        .group_by(Event.tenant)
        .order_by(desc("count"))
        .limit(8)
    )

    alert_counts_by_status = await session.execute(
        select(Alert.status, func.count().label("count"))
        .where(*alert_conditions)
        .where(Alert.triggered_at.between(start_date, end_date))
        .group_by(Alert.status)
    )

    alert_counts_by_severity = await session.execute(
        select(Alert.severity, func.count().label("count"))
        .where(*alert_conditions)
        .where(Alert.triggered_at.between(start_date, end_date))
        .group_by(Alert.severity)
    )

    alerts_by_day = await session.execute(
        select(
            Alert.tenant,
            func.date_trunc(bucket_unit, Alert.triggered_at).label("day"),
            func.count().label("count"),
        )
        .where(*alert_conditions)
        .where(Alert.triggered_at.between(start_date, end_date))
        .group_by(Alert.tenant, "day")
        .order_by("day")
    )

    alerts_rule_by_day = await session.execute(
        select(
            func.date_trunc(bucket_unit, Alert.triggered_at).label("day"),
            AlertRule.name.label("rule_name"),
            func.count().label("count"),
        )
        .join(AlertRule, Alert.rule_id == AlertRule.id)
        .where(*alert_conditions)
        .where(Alert.triggered_at.between(start_date, end_date))
        .group_by("day", "rule_name")
        .order_by("day", "rule_name")
    )

    rule_counts = await session.execute(
        select(AlertRule.enabled, func.count().label("count"))
        .where(AlertRule.tenant == tenant if tenant else True)
        .group_by(AlertRule.enabled)
    )

    if tenant:
        tenant_rows = [(tenant,)]
    else:
        # Platform admins can switch between every provisioned tenant, even one
        # with no events in the selected window.
        tenant_result = await session.execute(
            select(Tenant.name)
            .where(Tenant.is_active == True)  # noqa: E712
            .order_by(Tenant.name)
        )
        tenant_rows = [(row[0],) for row in tenant_result if row[0]]

    return {
        "totalEvents": total_events.scalar() or 0,
        "topIPs": [{"ip": row[0], "count": row[1]} for row in top_ips],
        "topUsers": [{"user": row[0], "count": row[1]} for row in top_users],
        "topEventTypes": [{"type": row[0], "count": row[1]} for row in top_event_types],
        "eventsBySource": [
            {
                "tenant": row[0],
                "timestamp": _iso_utc(row[1]),
                "source": row[2].value if hasattr(row[2], "value") else row[2],
                "_count": {"id": row[3]},
            }
            for row in events_by_source
        ],
        "alertsByDay": [
            {
                "tenant": row[0],
                "triggeredAt": _iso_utc(row[1]),
                "_count": {"id": row[2]},
            }
            for row in alerts_by_day
        ],
        "alertsRuleByDay": [
            {
                "tenant": tenant,
                "createdAt": _iso_utc(row[0]),
                "rule": row[1],
                "_count": {"id": row[2]},
            }
            for row in alerts_rule_by_day
        ],
        "recentAlert": [
            {
                "id": a.id,
                "tenant": a.tenant,
                "title": a.title,
                "severity": a.severity,
                "status": a.status,
                "triggeredAt": _iso_utc(a.triggered_at),
            } for a in recent_alerts.scalars()
        ],
        "severityCounts": [{"severity": row[0], "count": row[1]} for row in severity_counts],
        "sources": [
            {"source": row[0].value if hasattr(row[0], "value") else row[0], "_count": row[1], "latestEventAt": _iso_utc(row[2])}
            for row in sources
        ],
        "eventsByTenant": [{"tenant": row[0], "count": row[1]} for row in events_by_tenant],
        "alertCountsByStatus": [{"status": row[0], "count": row[1]} for row in alert_counts_by_status],
        "alertCountsBySeverity": [{"severity": row[0], "count": row[1]} for row in alert_counts_by_severity],
        "ruleCountsByEnabled": [{"enabled": row[0], "count": row[1]} for row in rule_counts],
        "tenants": [{"tenant": t[0]} for t in tenant_rows],
        "bucket": bucket_unit,
        "range": range,
        "tenant": tenant or "all",
    }
