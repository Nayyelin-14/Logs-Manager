"""
Alert Rules API Routes

Alert rule CRUD operations.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Form
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Annotated
from pydantic import BaseModel, Field, field_validator, ValidationError

from app.core.database import get_session
from app.core.dependencies import get_current_user, get_effective_tenant, require_admin
from app.core.security import TokenPayload
from app.models.alert import AlertRule, Alert
from app.core.config import get_settings

router = APIRouter()


VALID_CONDITION_TYPES = ["event_type", "severity_min", "field_value", "threshold_count", "repeated_failures"]


class ConditionBase(BaseModel):
    type: str
    value: Optional[str] = None
    threshold: Optional[int] = None
    windowSeconds: Optional[int] = None
    groupBy: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    field: Optional[str] = None
    
    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in VALID_CONDITION_TYPES:
            raise ValueError(f"Unknown condition type: {v}")
        return v
    
    @field_validator("threshold")
    @classmethod
    def validate_threshold(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("threshold must be non-negative")
        return v
    
    @field_validator("windowSeconds")
    @classmethod
    def validate_window(cls, v: Optional[int]) -> Optional[int]:
        if v is not None:
            if v < 1:
                raise ValueError("windowSeconds must be at least 1")
            if v > 86400:
                raise ValueError("windowSeconds must be at most 86400")
        return v
    
    @field_validator("groupBy")
    @classmethod
    def validate_group_by(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("src_ip", "user", "host"):
            raise ValueError(f"Invalid groupBy field: {v}")
        return v


class AlertRuleCreate(BaseModel):
    name: str
    tenant: str
    description: Optional[str] = None
    conditions: List[Annotated[ConditionBase, "ConditionBase"]] = Field(default_factory=list)
    enabled: bool = True
    severity: str = "medium"


class AlertRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    conditions: Optional[List[dict]] = None
    enabled: Optional[bool] = None
    severity: Optional[str] = None


class AlertRuleResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    tenant: str
    enabled: bool
    severity: str
    conditions: List[dict]
    createdAt: datetime
    updatedAt: datetime


@router.get("/get-rules", response_model=dict)
async def list_alert_rules(
    tenant: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 25,
    cursor: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    current_user: "TokenPayload" = Depends(require_admin),
):
    """List alert rules."""
    tenant = current_user.tenant
    
    query = select(AlertRule).where(AlertRule.tenant == tenant)
    
    if search:
        search_term = f"%{search}%"
        query = query.where(
            (AlertRule.name.ilike(f"%{search}%")) |
            (AlertRule.description.ilike(f"%{search}%"))
        )
    
    query = query.order_by(desc(AlertRule.created_at)).limit(limit + 1)
    if cursor:
        query = query.where(AlertRule.id > cursor)
    
    result = await session.execute(query)
    rules = result.scalars().all()
    
    has_next = len(rules) > limit
    if has_next:
        rules = rules[:limit]
    
    next_cursor = rules[-1].id if has_next else None
    
    return {
        "rules": [{
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "tenant": r.tenant,
            "enabled": r.enabled,
            "severity": r.severity,
            "conditions": r.conditions,
            "createdAt": r.created_at.isoformat() if r.created_at else None,
            "updatedAt": r.updated_at.isoformat() if r.updated_at else None,
        } for r in rules],
        "hasNextPage": has_next,
        "nextCursor": next_cursor,
    }


@router.post("/create-alertRule", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_alert_rule(
    rule: AlertRuleCreate,
    session: AsyncSession = Depends(get_session),
    current_user: "TokenPayload" = Depends(require_admin),
):
    """Create a new alert rule."""
    if not rule.conditions or len(rule.conditions) != 1:
        raise HTTPException(status_code=400, detail="Exactly one condition required")
    
    import uuid
    if rule.tenant != current_user.tenant:
        raise HTTPException(status_code=403, detail="Cannot create rule for different tenant")
    
    new_rule = AlertRule(
        id=uuid.uuid4().hex[:25],
        name=rule.name,
        description=rule.description,
        tenant=rule.tenant,
        enabled=rule.enabled,
        severity=rule.severity,
        conditions=[c.model_dump(exclude_none=True) for c in rule.conditions],
    )
    
    session.add(new_rule)
    await session.commit()
    await session.refresh(new_rule)
    
    return {"message": "Alert rule created", "createdRule": {
        "id": new_rule.id,
        "name": new_rule.name,
        "tenant": new_rule.tenant,
        "enabled": new_rule.enabled,
        "severity": new_rule.severity,
        "conditions": new_rule.conditions,
    }}


@router.put("/update-rule/{rule_id}", response_model=dict)
async def update_alert_rule(
    rule_id: str,
    rule: "AlertRuleUpdate",
    session: AsyncSession = Depends(get_session),
    current_user: "TokenPayload" = Depends(require_admin),
):
    """Update an alert rule."""
    from pydantic import BaseModel
    from typing import Optional, List, Dict, Any
    
    class AlertRuleUpdate(BaseModel):
        name: Optional[str] = None
        description: Optional[str] = None
        conditions: Optional[List[dict]] = None
        enabled: Optional[bool] = None
        severity: Optional[str] = None
    
    result = await session.execute(
        select(AlertRule).where(AlertRule.id == rule_id, AlertRule.tenant == current_user.tenant)
    )
    existing = result.scalar_one_or_none()
    if not existing:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    # Check for duplicate name
    if rule.name and rule.name != existing.name:
        result = await session.execute(
            select(AlertRule).where(
                AlertRule.name == rule.name,
                AlertRule.tenant == current_user.tenant,
                AlertRule.id != rule_id
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Rule with this name already exists")
    
    update_data = rule.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(existing, key, value)
    
    await session.commit()
    await session.refresh(existing)
    
    return {"message": "Alert rule updated", "rule": {
        "id": existing.id,
        "name": existing.name,
        "tenant": existing.tenant,
        "enabled": existing.enabled,
        "severity": existing.severity,
        "conditions": existing.conditions,
    }}


@router.patch("/rules/{rule_id}/enabled", response_model=dict)
async def toggle_rule_enabled(
    rule_id: str,
    enabled: bool = Form(...),
    session: AsyncSession = Depends(get_session),
    current_user: "TokenPayload" = Depends(require_admin),
):
    """Enable or disable an alert rule."""
    result = await session.execute(
        select(AlertRule).where(AlertRule.id == rule_id, AlertRule.tenant == current_user.tenant)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    rule.enabled = enabled
    await session.commit()
    
    return {"message": f"Rule {'enabled' if enabled else 'disabled'}", "rule": {
        "id": rule.id,
        "enabled": rule.enabled,
    }}


@router.delete("/delete-rule/{rule_id}", response_model=dict)
async def delete_alert_rule(
    rule_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: "TokenPayload" = Depends(require_admin),
):
    """Delete an alert rule."""
    result = await session.execute(
        select(AlertRule).where(AlertRule.id == rule_id, AlertRule.tenant == current_user.tenant)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        return {"success": False, "message": "Rule not found"}
    
    # Capture rule data before deletion for response
    rule_data = {
        "id": rule.id,
        "name": rule.name,
        "tenant": rule.tenant,
        "enabled": rule.enabled,
        "severity": rule.severity,
    }
    
    # Check if rule has triggered alerts
    alert_count = await session.execute(
        select(func.count()).select_from(Alert).where(Alert.rule_id == rule_id)
    )
    if alert_count.scalar() > 0:
        return {"success": False, "message": "Cannot delete rule with existing alerts"}
    
    await session.delete(rule)
    await session.commit()
    
    return {"success": True, "message": "Alert rule deleted", "rule": rule_data}