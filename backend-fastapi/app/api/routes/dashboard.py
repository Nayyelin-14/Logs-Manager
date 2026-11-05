"""
Dashboard API Routes

Dashboard statistics and analytics endpoints.
"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, func, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

from app.core.database import get_session
from app.core.dependencies import get_current_user, get_effective_tenant
from app.core.security import TokenPayload
from app.models.security_event import SecurityEvent
from app.models.alert import Alert, AlertRule

router = APIRouter()


def _iso_utc(value):
    """Serialize a datetime as ISO-8601, assuming UTC when it is naive."""
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
    session: AsyncSession = Depends(get_session),
    current_user: "TokenPayload" = Depends(get_current_user),
):
    """Get dashboard statistics."""
    # Admins may view all tenants or a specific one; regular users are locked to theirs.
    requested_tenant = (tenant or "").strip()
    if current_user.role == "ADMIN":
        tenant = None if requested_tenant in ("", "all") else requested_tenant
    else:
        tenant = current_user.tenant
    range_days = {"1d": 1, "3d": 3, "7d": 7, "30d": 30}.get(range, 7)
    
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=range_days)
    
    date_filter = {
        "gte": start_date,
        "lte": end_date
    }
    
    tenant_filter = {"tenant": tenant} if tenant else {}
    
    # Parallel queries for performance
    total_events = await session.execute(
        select(func.count()).select_from(SecurityEvent).where(
            SecurityEvent.tenant == tenant,
            SecurityEvent.timestamp.between(start_date, end_date)
        ) if tenant else select(func.count()).select_from(SecurityEvent).where(
            SecurityEvent.timestamp.between(start_date, end_date)
        )
    )
    
    # Top IPs
    top_ips = await session.execute(
        select(SecurityEvent.src_ip, func.count().label("count"))
        .where(SecurityEvent.tenant == tenant if tenant else True)
        .where(SecurityEvent.timestamp.between(start_date, end_date))
        .where(SecurityEvent.src_ip.isnot(None))
        .group_by(SecurityEvent.src_ip)
        .order_by(desc("count"))
        .limit(10)
    )
    
    # Top Users
    top_users = await session.execute(
        select(SecurityEvent.user, func.count().label("count"))
        .where(SecurityEvent.tenant == tenant if tenant else True)
        .where(SecurityEvent.timestamp.between(start_date, end_date))
        .where(SecurityEvent.user.isnot(None))
        .group_by(SecurityEvent.user)
        .order_by(desc("count"))
        .limit(10)
    )
    
    # Top Event Types
    top_event_types = await session.execute(
        select(SecurityEvent.event_type, func.count().label("count"))
        .where(SecurityEvent.tenant == tenant if tenant else True)
        .where(SecurityEvent.timestamp.between(start_date, end_date))
        .group_by(SecurityEvent.event_type)
        .order_by(desc("count"))
        .limit(10)
    )
    
    # Events by source per day (used for the daily volume series)
    events_by_source = await session.execute(
        select(
            SecurityEvent.tenant,
            func.date_trunc("day", SecurityEvent.timestamp).label("day"),
            SecurityEvent.source,
            func.count().label("count"),
        )
        .where(SecurityEvent.tenant == tenant if tenant else True)
        .where(SecurityEvent.timestamp.between(start_date, end_date))
        .group_by(SecurityEvent.tenant, "day", SecurityEvent.source)
        .order_by("day")
    )
    
    # Recent Alerts
    recent_alerts = await session.execute(
        select(Alert)
        .where(Alert.tenant == tenant if tenant else True)
        .order_by(desc(Alert.triggered_at))
        .limit(5)
    )
    
    # Sources
    sources = await session.execute(
        select(SecurityEvent.source, func.count().label("count"), func.max(SecurityEvent.timestamp).label("latest"))
        .where(SecurityEvent.tenant == tenant if tenant else True)
        .where(SecurityEvent.timestamp.between(start_date, end_date))
        .group_by(SecurityEvent.source)
        .order_by(desc("count"))
    )
    
    # Severity counts
    severity_counts = await session.execute(
        select(SecurityEvent.severity, func.count().label("count"))
        .where(SecurityEvent.tenant == tenant if tenant else True)
        .where(SecurityEvent.timestamp.between(start_date, end_date))
        .group_by(SecurityEvent.severity)
        .order_by(SecurityEvent.severity)
    )
    
    # Events by tenant
    events_by_tenant = await session.execute(
        select(SecurityEvent.tenant, func.count().label("count"))
        .where(SecurityEvent.timestamp.between(start_date, end_date))
        .group_by(SecurityEvent.tenant)
        .order_by(desc("count"))
        .limit(8)
    )
    
    # Alert counts by status
    alert_counts_by_status = await session.execute(
        select(Alert.status, func.count().label("count"))
        .where(Alert.tenant == tenant if tenant else True)
        .where(Alert.triggered_at.between(start_date, end_date))
        .group_by(Alert.status)
    )
    
    # Alert counts by severity
    alert_counts_by_severity = await session.execute(
        select(Alert.severity, func.count().label("count"))
        .where(Alert.tenant == tenant if tenant else True)
        .where(Alert.triggered_at.between(start_date, end_date))
        .group_by(Alert.severity)
    )
    
    # Alerts per day
    alerts_by_day = await session.execute(
        select(
            Alert.tenant,
            func.date_trunc("day", Alert.triggered_at).label("day"),
            func.count().label("count"),
        )
        .where(Alert.tenant == tenant if tenant else True)
        .where(Alert.triggered_at.between(start_date, end_date))
        .group_by(Alert.tenant, "day")
        .order_by("day")
    )
    
    # Alerts per rule per day
    alerts_rule_by_day = await session.execute(
        select(
            func.date_trunc("day", Alert.triggered_at).label("day"),
            AlertRule.name.label("rule_name"),
            func.count().label("count"),
        )
        .join(AlertRule, Alert.rule_id == AlertRule.id)
        .where(Alert.tenant == tenant if tenant else True)
        .where(Alert.triggered_at.between(start_date, end_date))
        .group_by("day", "rule_name")
        .order_by("day", "rule_name")
    )
    
    # Rule counts by enabled
    rule_counts = await session.execute(
        select(AlertRule.enabled, func.count().label("count"))
        .where(AlertRule.tenant == tenant if tenant else True)
        .group_by(AlertRule.enabled)
    )

    # Tenants
    tenants = await session.execute(
        select(SecurityEvent.tenant).distinct().where(SecurityEvent.tenant == tenant if tenant else True)
    )
    
    return {
        "totalEvents": total_events.scalar() or 0,
        "topIPs": [{"ip": row[0], "count": row[1]} for row in top_ips],
        "topUsers": [{"user": row[0], "count": row[1]} for row in top_users],
        "topEventTypes": [{"type": row[0], "count": row[1]} for row in top_event_types],
        "eventsBySource": [
            {
                "tenant": row[0],
                "timestamp": _iso_utc(row[1]),
                "source": row[2].value if row[2] else None,
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
            {"source": row[0].value if row[0] else None, "_count": row[1], "latestEventAt": _iso_utc(row[2])}
            for row in sources
        ],
        "eventsByTenant": [{"tenant": row[0], "count": row[1]} for row in events_by_tenant],
        "alertCountsByStatus": [{"status": row[0], "count": row[1]} for row in alert_counts_by_status],
        "alertCountsBySeverity": [{"severity": row[0], "count": row[1]} for row in alert_counts_by_severity],
        "ruleCountsByEnabled": [{"enabled": row[0], "count": row[1]} for row in rule_counts],
        "tenants": [{"tenant": t[0]} for t in tenants],
        "tenant": tenant or "all",
    }