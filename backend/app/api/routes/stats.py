from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel

from app.core.database import get_session
from app.core.dependencies import get_current_user
from app.core.security import TokenPayload
from app.core.tenancy import resolve_read_tenant
from app.services import stats_service

router = APIRouter()
class TopItem(BaseModel):
    value: Optional[str]
    count: int


class TopResponse(BaseModel):
    field: str
    items: list[TopItem]


class TimelineBucket(BaseModel):
    start: str
    count: int
    by_source: dict[str, int] = {}

class TimelineResponse(BaseModel):
    interval: str
    buckets: list[TimelineBucket]


class SummaryResponse(BaseModel):
    total_events: int
    failed_logins: int
    open_alerts: int
    active_sources: int
    tenants: list[str]
class SourceHealth(BaseModel):
    source: str
    event_count: int
    last_event_at: Optional[str]
    status: str
def _tenant_scope(current_user: TokenPayload, requested: Optional[str]) -> Optional[str]:
    return resolve_read_tenant(current_user, requested)
def _parse_range(from_str: Optional[str], to_str: Optional[str]) -> tuple[datetime, datetime]:
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
@router.get("/stats/top", response_model=TopResponse)
async def stats_top(
    field: str = Query("src_ip"),
    n: int = Query(10, ge=1, le=100),
    from_: Optional[str] = Query(None, alias="from"),
    to: Optional[str] = Query(None),
    tenant: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    current_user: TokenPayload = Depends(get_current_user),
    session=Depends(get_session),
):
    effective_tenant = _tenant_scope(current_user, tenant)
    start, end = _parse_range(from_, to)
    items = await stats_service.query_stats_top(
        session, field, n, start, end, effective_tenant, source
    )
    return TopResponse(field=field, items=[TopItem(**i) for i in items])
@router.get("/stats/timeline", response_model=TimelineResponse)
async def stats_timeline(
    from_: Optional[str] = Query(None, alias="from"),
    to: Optional[str] = Query(None),
    interval: Optional[str] = Query(None, description="auto|1m|5m|1h|1d"),
    tenant: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    current_user: TokenPayload = Depends(get_current_user),
    session=Depends(get_session),
):
    effective_tenant = _tenant_scope(current_user, tenant)
    start, end = _parse_range(from_, to)
    range_minutes = (end - start).total_seconds() / 60
    if interval not in ("1m", "5m", "1h", "1d"):
        interval = stats_service._auto_interval(range_minutes)
    buckets = await stats_service.query_stats_timeline(
        session, start, end, interval, effective_tenant, source
    )
    return TimelineResponse(
        interval=interval,
        buckets=[TimelineBucket(**b) for b in buckets],
    )
@router.get("/stats/summary", response_model=SummaryResponse)
async def stats_summary(
    tenant: Optional[str] = Query(None),
    current_user: TokenPayload = Depends(get_current_user),
    session=Depends(get_session),
):
    effective_tenant = _tenant_scope(current_user, tenant)
    start, end = _parse_range(None, None)
    data = await stats_service.query_stats_summary(
        session, start, end, effective_tenant
    )
    return SummaryResponse(**data)
@router.get("/sources/health", response_model=list[SourceHealth])
async def sources_health(
    tenant: Optional[str] = Query(None),
    current_user: TokenPayload = Depends(get_current_user),
    session=Depends(get_session),
):
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Admin only")
    effective_tenant = _tenant_scope(current_user, tenant)
    start, end = _parse_range(None, None)
    data = await stats_service.query_sources_health(
        session, start, end, effective_tenant
    )
    return [SourceHealth(**h) for h in data]
