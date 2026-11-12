from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4
from typing import Any

from app.core.database import get_session
from app.core.dependencies import require_admin
from app.core.security import TokenPayload
from app.core.rule_validation import (
    AlertRuleCreate,
    _resolve_write_tenant,
    _check_duplicate_name,
    validate_filter_dict,
    validate_threshold_range,
    validate_window_minutes_range,
    validate_cooldown_range,
    VALID_RULE_TYPES,
    VALID_SEVERITIES,
    VALID_GROUP_BY,
    _MAX_NAME_LENGTH,
    _MIN_NAME_LENGTH,
    _MAX_WINDOW_SECONDS,
)
from app.models.alert import AlertRule

router = APIRouter()


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
