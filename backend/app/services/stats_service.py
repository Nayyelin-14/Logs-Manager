from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select, func, desc, asc, and_
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.core.tenancy import normalize_tenant
from app.models.events import Event
from app.models.alert import Alert


TOP_FIELD_WHITELIST: dict[str, Any] = {
    "src_ip": Event.src_ip,
    "user": Event.user_name,
    "event_type": Event.event_type,
    "source": Event.source,
    "host": Event.host,
}


def _tenant_scope(current_user_role: str, current_user_tenant: Optional[str],
                  requested: Optional[str]) -> Optional[str]:
    role = current_user_role.value if hasattr(current_user_role, "value") else current_user_role
    own_tenant = (current_user_tenant or "").strip().lower()
    if role == "ADMIN" and not own_tenant:
        requested_tenant = (requested or "").strip().lower()
        if requested_tenant in ("", "all"):
            return None
        return normalize_tenant(requested)
    if not own_tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not assigned to a tenant",
        )
    return own_tenant


def _parse_time_range(from_str: Optional[str], to_str: Optional[str]) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=7)
    end = now
    if from_str:
        try:
            start = datetime.fromisoformat(from_str.replace("Z", "+00:00"))
        except ValueError:
            pass
    if to_str:
        try:
            end = datetime.fromisoformat(to_str.replace("Z", "+00:00"))
        except ValueError:
            pass
    return start, end


def _auto_interval(range_minutes: float) -> str:
    if range_minutes <= 60:
        return "1m"
    if range_minutes <= 480:
        return "5m"
    if range_minutes <= 4320:
        return "1h"
    return "1d"


def _trunc_unit(interval: str) -> str:
    return {"1m": "minute", "5m": "hour", "1h": "hour", "1d": "day"}.get(interval, "hour")


async def query_stats_top(
    session: AsyncSession,
    field: str,
    n: int,
    start: datetime,
    end: datetime,
    tenant: Optional[str],
    source: Optional[str],
) -> list[dict[str, Any]]:
    if field not in TOP_FIELD_WHITELIST:
        return []
    column = TOP_FIELD_WHITELIST[field]

    conditions = [column.isnot(None), Event.ts >= start, Event.ts <= end]
    if tenant:
        conditions.append(Event.tenant == tenant)
    if source:
        conditions.append(Event.source == source)

    result = await session.execute(
        select(column, func.count().label("cnt"))
        .where(and_(*conditions))
        .group_by(column)
        .order_by(desc("cnt"))
        .limit(n)
    )
    return [
        {"value": str(row[0]) if row[0] is not None else None, "count": int(row[1])}
        for row in result.all()
    ]


async def query_stats_timeline(
    session: AsyncSession,
    start: datetime,
    end: datetime,
    interval: str,
    tenant: Optional[str],
    source: Optional[str],
) -> list[dict[str, Any]]:
    conditions = [Event.ts >= start, Event.ts <= end]
    if tenant:
        conditions.append(Event.tenant == tenant)
    if source:
        conditions.append(Event.source == source)

    trunc_unit = _trunc_unit(interval)
    bucket = func.date_trunc(trunc_unit, Event.ts)

    result = await session.execute(
        select(bucket.label("bucket"), Event.source, func.count().label("cnt"))
        .where(and_(*conditions))
        .group_by(bucket, Event.source)
        .order_by(bucket)
    )

    buckets_map: dict[str, dict[str, Any]] = {}
    for row in result.all():
        bkey = row.bucket.isoformat() if hasattr(row.bucket, "isoformat") else str(row.bucket)
        if bkey not in buckets_map:
            buckets_map[bkey] = {"start": bkey, "count": 0, "by_source": {}}
        src = row.source.value if hasattr(row.source, "value") else str(row.source)
        buckets_map[bkey]["count"] += int(row.cnt)
        buckets_map[bkey]["by_source"][src] = buckets_map[bkey]["by_source"].get(src, 0) + int(row.cnt)

    return [
        {"start": v["start"], "count": v["count"], "by_source": v["by_source"]}
        for v in sorted(buckets_map.values(), key=lambda x: x["start"])
    ]


async def query_stats_summary(
    session: AsyncSession,
    start: datetime,
    end: datetime,
    tenant: Optional[str],
    source: Optional[str] = None,
) -> dict[str, Any]:
    conditions = [Event.ts >= start, Event.ts <= end]
    if tenant:
        conditions.append(Event.tenant == tenant)
    if source:
        conditions.append(Event.source == source)

    total_result = await session.execute(
        select(func.count()).select_from(Event).where(and_(*conditions))
    )
    total_events = int(total_result.scalar() or 0)

    failed_conditions = list(conditions) + [
        Event.outcome == "failure", Event.action == "login"
    ]
    failed_result = await session.execute(
        select(func.count()).select_from(Event).where(and_(*failed_conditions))
    )
    failed_logins = int(failed_result.scalar() or 0)

    alert_conditions = [Alert.status == "open"]
    if tenant:
        alert_conditions.append(Alert.tenant == tenant)
    alerts_result = await session.execute(
        select(func.count()).select_from(Alert).where(and_(*alert_conditions))
    )
    open_alerts = int(alerts_result.scalar() or 0)

    src_conditions = list(conditions) + [Event.src_ip.isnot(None)]
    sources_result = await session.execute(
        select(func.count(func.distinct(Event.source))).select_from(Event).where(and_(*src_conditions))
    )
    active_sources = int(sources_result.scalar() or 0)

    tenant_result = await session.execute(
        select(func.distinct(Event.tenant)).select_from(Event).where(and_(*conditions))
    )
    tenants = [row[0] for row in tenant_result.all() if row[0]]

    return {
        "total_events": total_events,
        "failed_logins": failed_logins,
        "open_alerts": open_alerts,
        "active_sources": active_sources,
        "tenants": tenants,
    }


async def query_sources_health(
    session: AsyncSession,
    start: datetime,
    end: datetime,
    tenant: Optional[str],
) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    active_cutoff = now - timedelta(minutes=15)

    conditions = [Event.ts >= start, Event.ts <= end]
    if tenant:
        conditions.append(Event.tenant == tenant)

    result = await session.execute(
        select(
            Event.source,
            func.count().label("cnt"),
            func.max(Event.ts).label("last_ts"),
        )
        .where(and_(*conditions))
        .group_by(Event.source)
        .order_by(desc("cnt"))
    )

    health: list[dict[str, Any]] = []
    for row in result.all():
        src = row.source.value if hasattr(row.source, "value") else str(row.source)
        cnt = int(row.cnt)
        last_ts = row.last_ts
        status = "active" if last_ts and last_ts >= active_cutoff else "inactive"
        health.append({
            "source": src,
            "event_count": cnt,
            "last_event_at": last_ts.isoformat() if last_ts else None,
            "status": status,
        })
    return health
