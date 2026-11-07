"""
Alert API Routes

Alert listing, status updates, and alert rule management.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Form
from pydantic import BaseModel
from sqlalchemy import select, func, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

from app.core.database import get_session
from app.core.dependencies import get_current_user, get_effective_tenant, require_admin
from app.core.security import TokenPayload
from app.models.alert import Alert, AlertRule, EmailNotification
from app.models.events import Event

router = APIRouter()


class AlertStatusUpdate(BaseModel):
    status: str


@router.get("/get-alerts", response_model=dict)
async def list_alerts(
    tenant: Optional[str] = None,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 25,
    cursor: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    current_user: "TokenPayload" = Depends(get_current_user),
):
    """List alerts with filtering and pagination."""
    requested_tenant = (tenant or "").strip()
    if current_user.role == "ADMIN":
        effective_tenant = None if requested_tenant in ("", "all") else requested_tenant
    else:
        effective_tenant = current_user.tenant

    query = select(Alert).options(selectinload(Alert.rule))
    if effective_tenant:
        query = query.where(Alert.tenant == effective_tenant)
    
    if status:
        query = query.where(Alert.status == status)
    if severity:
        query = query.where(Alert.severity == severity)
    if search:
        search_term = f"%{search}%"
        # Use func.array_to_string to search within tags array elements
        query = query.where(
            or_(
                Alert.title.ilike(f"%{search}%"),
                Alert.description.ilike(f"%{search}%"),
                func.array_to_string(Alert.tags, ',').ilike(f"%{search}%")
            )
        )
    
    query = query.order_by(desc(Alert.triggered_at), desc(Alert.id)).limit(limit + 1)
    if cursor:
        query = query.where(Alert.id > cursor)
    
    result = await session.execute(query)
    alerts = result.scalars().all()
    
    has_next = len(alerts) > limit
    if has_next:
        alerts = alerts[:limit]
    
    next_cursor = alerts[-1].id if has_next else None
    
    return {
        "alerts": [{
            "id": a.id,
            "tenant": a.tenant,
            "title": a.title,
            "description": a.description,
            "severity": a.severity,
            "status": a.status,
            "triggeredAt": a.triggered_at.isoformat() if a.triggered_at else None,
            "eventIds": a.event_ids,
            "tags": a.tags,
            "rule": {"name": a.rule.name, "description": a.rule.description} if a.rule else None,
            "dedupeKey": a.dedupe_key,
        } for a in alerts],
        "hasNextPage": has_next,
        "nextCursor": next_cursor,
    }


@router.patch("/alerts/{alert_id}", response_model=dict)
async def update_alert_status(
    alert_id: str,
    update: AlertStatusUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: "TokenPayload" = Depends(require_admin),
):
    """Update alert status (Admin only)."""
    if update.status not in ["open", "resolved"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    result = await session.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    alert.status = update.status
    await session.commit()
    
    return {"message": "Alert status updated", "alert": {"id": alert.id, "status": alert.status}}