from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, desc, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from uuid import uuid4
from typing import Optional, List, Dict, Any

from app.core.database import get_session
from app.core.dependencies import get_current_user, require_admin
from app.core.security import TokenPayload
from app.core.rule_validation import (
    AlertRuleCreate,
    AlertRuleUpdate,
    ConditionBase,
    _resolve_write_tenant,
    _check_duplicate_name,
    validate_filter_dict,
    validate_threshold_range,
    validate_window_minutes_range,
    validate_cooldown_range,
    VALID_RULE_TYPES,
    VALID_SEVERITIES,
    VALID_CONDITION_TYPES,
    VALID_GROUP_BY,
    _MAX_NAME_LENGTH,
    _MIN_NAME_LENGTH,
    _MAX_WINDOW_SECONDS,
)
from app.models.alert import AlertRule, Alert
from pydantic import BaseModel

router = APIRouter()


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


def _rule_payload(rule: AlertRule) -> dict:
    return {
        "id": rule.id,
        "name": rule.name,
        "description": rule.description,
        "tenant": rule.tenant,
        "enabled": rule.enabled,
        "severity": rule.severity,
        "conditions": rule.conditions,
        "createdAt": rule.created_at.isoformat() if rule.created_at else None,
        "updatedAt": rule.updated_at.isoformat() if rule.updated_at else None,
    }


@router.get("/get-rules", response_model=dict, include_in_schema=False)
async def list_alert_rules(
    tenant: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 25,
    cursor: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    current_user: "TokenPayload" = Depends(require_admin),
):
    # Use the shared read tenant resolver for consistency (H-8 / Phase 1).
    from app.core.tenancy import resolve_read_tenant

    effective_tenant = resolve_read_tenant(current_user, tenant)

    query = select(AlertRule)
    if effective_tenant:
        query = query.where(AlertRule.tenant == effective_tenant)

    if search:
        search_term = f"%{search}%"
        query = query.where(
            (AlertRule.name.ilike(f"%{search}%")) |
            (AlertRule.description.ilike(f"%{search}%"))
        )

    query = query.order_by(desc(AlertRule.created_at), desc(AlertRule.id)).limit(limit + 1)
    if cursor:
        cursor_rule = await session.get(AlertRule, cursor)
        if cursor_rule is None:
            return {
                "rules": [],
                "hasNextPage": False,
                "newCursor": None,
                "nextCursor": None,
            }
        query = query.where(
            or_(
                AlertRule.created_at < cursor_rule.created_at,
                and_(
                    AlertRule.created_at == cursor_rule.created_at,
                    AlertRule.id < cursor,
                ),
            )
        )

    result = await session.execute(query)
    rules = result.scalars().all()

    has_next = len(rules) > limit
    if has_next:
        rules = rules[:limit]

    next_cursor = rules[-1].id if has_next else None

    return {
        "rules": [_rule_payload(r) for r in rules],
        "hasNextPage": has_next,
        "newCursor": next_cursor,
        "nextCursor": next_cursor,
    }


@router.post("/create-alertRule", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_alert_rule(
    rule: AlertRuleCreate,
    session: AsyncSession = Depends(get_session),
    current_user: "TokenPayload" = Depends(require_admin),
):
    # Explicit validation layer (H-2, H-6, H-11): Pydantic field validators
    # provide defense-in-depth, but we validate explicitly here to ensure
    # invalid requests are always rejected with 4xx, regardless of framework
    # behavior.

    # Validate conditions are present and not blank (H-1, H-2).
    if not rule.conditions or len(rule.conditions) != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exactly one condition is required",
        )

    # Validate name (H-11).
    stripped_name = rule.name.strip()
    if len(stripped_name) < _MIN_NAME_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="rule name must not be empty or whitespace",
        )
    if len(stripped_name) > _MAX_NAME_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"rule name must be at most {_MAX_NAME_LENGTH} characters",
        )

    # Validate severity (H-11).
    normalized_severity = rule.severity.strip().lower()
    if normalized_severity not in VALID_SEVERITIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid severity: {rule.severity}. "
                f"Supported values: {', '.join(sorted(VALID_SEVERITIES))}"
            ),
        )

    # Validate threshold range (H-2).
    if rule.threshold is not None:
        rule.threshold = validate_threshold_range(rule.threshold)

    # Validate window_minutes range (H-2).
    if rule.window_minutes is not None:
        rule.window_minutes = validate_window_minutes_range(rule.window_minutes)

    # Validate cooldown_minutes range (H-2).
    if rule.cooldown_minutes is not None:
        rule.cooldown_minutes = validate_cooldown_range(rule.cooldown_minutes)

    # Resolve and validate tenant (H-11).
    tenant = await _resolve_write_tenant(current_user, rule.tenant, session)

    # Check for duplicate name within tenant scope (H-11).
    await _check_duplicate_name(session, stripped_name, tenant)

    # Validate rule_type against evaluator-supported types (H-6).
    rule_type = rule.rule_type or "threshold"
    if rule_type not in VALID_RULE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported rule type: {rule_type}. "
                f"Supported types: {', '.join(sorted(VALID_RULE_TYPES))}"
            ),
        )

    # Persist condition in the shape the evaluator consumes.
    cond = rule.conditions[0]

    # Validate condition-level threshold (H-2).
    if cond.threshold is not None:
        cond.threshold = validate_threshold_range(cond.threshold)

    # Validate condition-level window_seconds (H-2).
    if cond.window_seconds is not None:
        if cond.window_seconds < 1:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="window_seconds must be at least 1",
            )
        if cond.window_seconds > _MAX_WINDOW_SECONDS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"window_seconds must be at most {_MAX_WINDOW_SECONDS}",
            )
        cond.window_seconds = validate_window_minutes_range(
            max(1, int(cond.window_seconds / 60))
        ) * 60

    # Validate condition-level group_by (H-6).
    if cond.group_by is not None:
        stripped_gb = cond.group_by.strip()
        if stripped_gb not in VALID_GROUP_BY:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid group_by: {cond.group_by}",
            )
        cond.group_by = stripped_gb

    condition_dict = {
        "type": cond.type,
    }
    if cond.value is not None:
        condition_dict["value"] = cond.value
    if cond.threshold is not None:
        condition_dict["threshold"] = cond.threshold
    if cond.window_seconds is not None:
        condition_dict["windowSeconds"] = cond.window_seconds
    if cond.group_by is not None:
        condition_dict["groupBy"] = cond.group_by
    if cond.field is not None:
        condition_dict["field"] = cond.field

    # Build the evaluator filter dict from the condition (H-1).
    filter_json: dict[str, Any] = {}
    ctype = cond.type
    cvalue = cond.value
    if ctype == "event_type" and cvalue:
        filter_json["event_type"] = cvalue
    elif ctype == "severity_min" and cvalue:
        try:
            filter_json["severity_gte"] = int(cvalue)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid severity value: {cvalue}",
            )
    elif ctype == "threshold_count" and cvalue:
        filter_json["event_type"] = cvalue
    elif ctype == "field_value" and cond.field and cvalue:
        # Normalize action values to lowercase for case-insensitive matching
        # against stored event data (e.g., "DENY" vs "deny").
        normalized_value = cvalue.lower() if cond.field == "action" else cvalue
        filter_json[cond.field] = normalized_value
    elif ctype == "repeated_failures":
        # repeated_failures maps to outcome=failure, action=login in evaluator.
        filter_json.setdefault("outcome", "failure")
        filter_json.setdefault("action", "login")

    # Validate the built filter dict (H-2, H-6).
    filter_json = validate_filter_dict(filter_json, ctype, cvalue)

    # Validate explicit filter dict if provided via API payload.
    if rule.filter is not None:
        filter_json = validate_filter_dict(rule.filter, ctype, cvalue)

    group_by = rule.group_by or "src_ip"
    threshold = (
        rule.threshold
        if rule.threshold is not None
        else (cond.threshold if cond.threshold is not None else 5)
    )
    window_minutes = (
        rule.window_minutes
        if rule.window_minutes is not None
        else max(1, int((cond.window_seconds or 300) / 60))
    )
    cooldown_minutes = rule.cooldown_minutes if rule.cooldown_minutes is not None else 0

    new_rule = AlertRule(
        id=uuid4().hex[:25],
        name=stripped_name,
        description=rule.description,
        tenant=tenant,
        enabled=rule.enabled,
        severity=normalized_severity,
        conditions=[condition_dict],
        rule_type=rule_type,
        filter=filter_json,
        group_by=group_by,
        threshold=threshold,
        window_minutes=window_minutes,
        cooldown_minutes=cooldown_minutes,
        notify=rule.notify or {},
    )

    session.add(new_rule)
    await session.commit()
    await session.refresh(new_rule)

    return {"message": "Alert rule created", "createdRule": _rule_payload(new_rule)}


@router.put("/update-rule/{rule_id}", response_model=dict, include_in_schema=False)
async def update_alert_rule(
    rule_id: str,
    rule: AlertRuleUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: "TokenPayload" = Depends(require_admin),
):
    result = await session.execute(
        select(AlertRule).where(AlertRule.id == rule_id, AlertRule.tenant == current_user.tenant)
    )
    existing = result.scalar_one_or_none()
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")

    # Validate name if provided (H-11).
    if rule.name is not None:
        stripped_name = rule.name.strip()
        if len(stripped_name) < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="rule name must not be empty or whitespace",
            )
        if len(stripped_name) > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="rule name must be at most 100 characters",
            )
        await _check_duplicate_name(session, stripped_name, existing.tenant, exclude_id=rule_id)
        existing.name = stripped_name

    if rule.description is not None:
        existing.description = rule.description

    # Validate and apply conditions if provided (H-1, H-2, H-6).
    if rule.conditions is not None:
        if len(rule.conditions) != 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Exactly one condition is required",
            )
        cond = rule.conditions[0]
        condition_dict = {
            "type": cond.type,
        }
        if cond.value is not None:
            condition_dict["value"] = cond.value
        if cond.threshold is not None:
            condition_dict["threshold"] = cond.threshold
        if cond.window_seconds is not None:
            condition_dict["windowSeconds"] = cond.window_seconds
        if cond.group_by is not None:
            condition_dict["groupBy"] = cond.group_by
        if cond.field is not None:
            condition_dict["field"] = cond.field

        # Build the evaluator filter dict from the condition (H-1).
        filter_json: dict[str, Any] = {}
        ctype = cond.type
        cvalue = cond.value
        if ctype == "event_type" and cvalue:
            filter_json["event_type"] = cvalue
        elif ctype == "severity_min" and cvalue:
            try:
                filter_json["severity_gte"] = int(cvalue)
            except (ValueError, TypeError):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid severity value: {cvalue}",
                )
        elif ctype == "threshold_count" and cvalue:
            filter_json["event_type"] = cvalue
        elif ctype == "field_value" and cond.field and cvalue:
            # Normalize action values to lowercase for case-insensitive matching
            # against stored event data (e.g., "DENY" vs "deny").
            normalized_value = cvalue.lower() if cond.field == "action" else cvalue
            filter_json[cond.field] = normalized_value
        elif ctype == "repeated_failures":
            filter_json.setdefault("outcome", "failure")
            filter_json.setdefault("action", "login")

        # Validate the built filter dict (H-2, H-6).
        filter_json = validate_filter_dict(filter_json, ctype, cvalue)

        existing.conditions = [condition_dict]
        existing.filter = filter_json

    if rule.enabled is not None:
        existing.enabled = rule.enabled

    # Validate and apply severity if provided (H-11).
    if rule.severity is not None:
        normalized_severity = rule.severity.strip().lower()
        if normalized_severity not in VALID_SEVERITIES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Invalid severity: {rule.severity}. "
                    f"Supported values: {', '.join(sorted(VALID_SEVERITIES))}"
                ),
            )
        existing.severity = normalized_severity

    # Validate and apply rule_type if provided (H-6).
    if rule.rule_type is not None:
        normalized_rule_type = rule.rule_type.strip().lower()
        if normalized_rule_type not in VALID_RULE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Unsupported rule type: {rule.rule_type}. "
                    f"Supported types: {', '.join(sorted(VALID_RULE_TYPES))}"
                ),
            )
        existing.rule_type = normalized_rule_type

    # Preserve omitted settings during partial updates (H-6): only fields
    # explicitly provided are changed; existing values are kept for the rest.
    if rule.group_by is not None:
        stripped_gb = rule.group_by.strip()
        if stripped_gb not in VALID_GROUP_BY:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid group_by: {rule.group_by}",
            )
        existing.group_by = stripped_gb
    if rule.threshold is not None:
        existing.threshold = validate_threshold_range(rule.threshold)
    if rule.window_minutes is not None:
        existing.window_minutes = validate_window_minutes_range(rule.window_minutes)
    if rule.cooldown_minutes is not None:
        existing.cooldown_minutes = validate_cooldown_range(rule.cooldown_minutes)
    if rule.notify is not None:
        existing.notify = rule.notify

    await session.commit()
    await session.refresh(existing)

    return {"message": "Alert rule updated", "rule": _rule_payload(existing)}


@router.patch("/rules/{rule_id}/enabled", response_model=dict, include_in_schema=False)
async def toggle_rule_enabled(
    rule_id: str,
    enabled: bool = Query(..., description="Desired enabled state"),
    session: AsyncSession = Depends(get_session),
    current_user: "TokenPayload" = Depends(require_admin),
):
    result = await session.execute(
        select(AlertRule).where(AlertRule.id == rule_id, AlertRule.tenant == current_user.tenant)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")

    rule.enabled = enabled
    await session.commit()

    return {"message": f"Rule {'enabled' if enabled else 'disabled'}", "rule": {
        "id": rule.id,
        "enabled": rule.enabled,
    }}


@router.delete("/delete-rule/{rule_id}", response_model=dict, include_in_schema=False)
async def delete_alert_rule(
    rule_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: "TokenPayload" = Depends(require_admin),
):
    result = await session.execute(
        select(AlertRule).where(AlertRule.id == rule_id, AlertRule.tenant == current_user.tenant)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        return {"success": False, "message": "Rule not found"}

    rule_data = {
        "id": rule.id,
        "name": rule.name,
        "tenant": rule.tenant,
        "enabled": rule.enabled,
        "severity": rule.severity,
    }

    alert_count = await session.execute(
        select(func.count()).select_from(Alert).where(Alert.rule_id == rule_id)
    )
    if alert_count.scalar() > 0:
        return {"success": False, "message": "Cannot delete rule with existing alerts"}

    await session.delete(rule)
    await session.commit()

    return {"success": True, "message": "Alert rule deleted", "rule": rule_data}
