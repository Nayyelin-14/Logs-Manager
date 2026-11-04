"""
Search API Routes

Event search and filtering endpoints.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc, asc, or_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from pydantic import BaseModel, Field

from app.core.database import get_session
from app.core.dependencies import get_current_user, get_effective_tenant
from app.core.security import TokenPayload
from app.models.security_event import SecurityEvent

router = APIRouter()


def _iso_utc(value):
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _severity_level(value):
    if value is None:
        return None
    if value >= 9:
        return "critical"
    if value >= 7:
        return "high"
    if value >= 4:
        return "medium"
    return "low"


class LogFilters(BaseModel):
    tenant: Optional[str] = None
    source: Optional[str] = None
    event_type: Optional[str] = None
    eventType: Optional[str] = None
    severity: Optional[str] = None
    date: Optional[str] = None
    action: Optional[str] = None
    user: Optional[str] = None
    src_ip: Optional[str] = None
    dst_ip: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    search: Optional[str] = None
    limit: int = 50
    cursor: Optional[str] = None
    sort_by: str = "@timestamp"
    sort_order: str = "desc"


class PaginatedLogsResponse(BaseModel):
    logs: List[dict]
    next_cursor: Optional[str] = None
    total: int


@router.get("/get-logs", response_model=dict)
async def search_logs(
    filters: LogFilters = Depends(),
    session: AsyncSession = Depends(get_session),
    current_user: "TokenPayload" = Depends(get_current_user),
):
    """Search and filter security events with cursor pagination."""
    requested_tenant = (filters.tenant or "").strip()
    if current_user.role == "ADMIN":
        tenant = None if requested_tenant in ("", "all") else requested_tenant
    else:
        tenant = current_user.tenant

    query = select(SecurityEvent)
    if tenant:
        query = query.where(SecurityEvent.tenant == tenant)
    
    # Apply filters
    if filters.source:
        query = query.where(SecurityEvent.source == filters.source)
    event_type = filters.event_type or filters.eventType
    if event_type:
        query = query.where(SecurityEvent.event_type == event_type)
    if filters.severity:
        sev = str(filters.severity).strip().lower()
        ranges = {"low": (0, 3), "medium": (4, 6), "high": (7, 8), "critical": (9, 10)}
        if sev in ranges:
            low, high = ranges[sev]
            query = query.where(SecurityEvent.severity.between(low, high))
        elif sev.isdigit():
            query = query.where(SecurityEvent.severity >= int(sev))
    if filters.date:
        try:
            day = datetime.fromisoformat(filters.date).replace(tzinfo=timezone.utc)
            query = query.where(SecurityEvent.timestamp >= day)
            query = query.where(SecurityEvent.timestamp < day + timedelta(days=1))
        except ValueError:
            pass
    if filters.action:
        query = query.where(SecurityEvent.action == filters.action)
    if filters.user:
        query = query.where(SecurityEvent.user.ilike(f"%{filters.user}%"))
    if filters.src_ip:
        query = query.where(SecurityEvent.src_ip == filters.src_ip)
    if filters.dst_ip:
        query = query.where(SecurityEvent.dst_ip == filters.dst_ip)
    if filters.start_time:
        query = query.where(SecurityEvent.timestamp >= filters.start_time)
    if filters.end_time:
        query = query.where(SecurityEvent.timestamp <= filters.end_time)
    if filters.search:
        search_term = f"%{filters.search}%"
        query = query.where(
            or_(
                SecurityEvent.description.ilike(f"%{filters.search}%"),
                SecurityEvent.user.ilike(f"%{filters.search}%"),
                SecurityEvent.src_ip.ilike(f"%{filters.search}%"),
                SecurityEvent.event_type.ilike(f"%{filters.search}%"),
            )
        )
    
    # Sorting
    sort_column = getattr(SecurityEvent, filters.sort_by, SecurityEvent.timestamp)
    if filters.sort_order == "asc":
        query = query.order_by(asc(sort_column))
    else:
        query = query.order_by(desc(sort_column))
    
    # Cursor-based pagination
    if filters.cursor:
        query = query.where(SecurityEvent.id > filters.cursor)
    
    query = query.limit(filters.limit + 1)
    result = await session.execute(query)
    logs = result.scalars().all()
    
    has_next = len(logs) > filters.limit
    if has_next:
        logs = logs[:filters.limit]
    
    next_cursor = logs[-1].id if has_next else None
    
    # Convert to dict (camelCase contract expected by the frontend)
    log_dicts = []
    for log in logs:
        log_dicts.append({
            "id": log.id,
            "timestamp": _iso_utc(log.timestamp),
            "eventType": log.event_type,
            "user": log.user,
            "srcIp": log.src_ip,
            "dstIp": log.dst_ip,
            "description": log.description,
            "severity": log.severity,
            "severityLevel": _severity_level(log.severity),
            "tenant": log.tenant,
            "action": log.action.value if log.action else None,
            "source": log.source.value if log.source else None,
            "host": log.host,
            "process": log.process,
            "protocol": log.protocol,
            "statusCode": log.status_code,
            "priority": log.priority,
            "sha256": log.sha256,
            "raw": log.raw,
            "createdAt": _iso_utc(log.created_at),
        })
    
    return {
        "logs": log_dicts,
        "newCursor": next_cursor,
        "prevCursor": None,
        "total": len(log_dicts),
    }


@router.delete("/delete-log/{log_id}", response_model=dict)
async def delete_log(
    log_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: "TokenPayload" = Depends(get_current_user),
):
    """Delete a log entry (Admin only)."""
    from app.core.dependencies import require_admin
    await require_admin(current_user)
    
    from app.models.security_event import SecurityEvent
    from sqlalchemy import select
    
    result = await session.execute(
        select(SecurityEvent).where(SecurityEvent.id == log_id)
    )
    log = result.scalar_one_or_none()
    if not log:
        return {"success": False, "message": "Log not found"}
    
    await session.delete(log)
    await session.commit()
    
    return {"success": True, "message": "Log deleted"}