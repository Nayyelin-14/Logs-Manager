"""Alert rule create/update validation with strict condition schema.

Provides shared validation logic for both rule creation and updates, ensuring
that only evaluator-supported condition fields are accepted, blank/malformed
conditions are rejected, and tenant/name/severity are validated consistently.
"""

from __future__ import annotations

import re
from typing import Any, Optional
from uuid import uuid4

from fastapi import HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.tenancy import (
    is_platform_admin,
    normalize_tenant,
    resolve_read_tenant,
    tenant_key,
)
from app.models.alert import AlertRule
from app.models.enums import Action
from app.models.events import ActionEnum, OutcomeEnum
from app.models.tenant import Tenant

settings = get_settings()

# Condition types that the evaluator actually consumes.
VALID_CONDITION_TYPES = {
    "event_type",
    "severity_min",
    "field_value",
    "threshold_count",
    "repeated_failures",
}

# Rule types that correspond to actual evaluator behavior.
VALID_RULE_TYPES = {"threshold", "repeated_failures"}

# Severity values supported by the evaluator and frontend.
VALID_SEVERITIES = {"low", "medium", "high", "critical"}

# Field names that the evaluator's _build_filter_conditions actually checks.
# Fields outside this set are silently ignored by the evaluator, so accepting
# them would create rules with no effect (H-1).
EVALUATOR_FILTER_FIELDS = {
    "outcome",
    "action",
    "source",
    "event_type",
    "severity_gte",
    "src_ip",
    "dst_ip",
    "user_name",
    "host",
    "process",
    "status_code",
}

# group_by values supported by the evaluator.
VALID_GROUP_BY = {"src_ip", "user_name", "host"}

_MAX_NAME_LENGTH = 100
_MIN_NAME_LENGTH = 1

_MIN_SEVERITY = 0
_MAX_SEVERITY = 10
_MIN_THRESHOLD = 1
_MAX_THRESHOLD = 10000
_MIN_WINDOW_SECONDS = 1
_MAX_WINDOW_SECONDS = 86400
_MIN_COOLDOWN_MINUTES = 0
_MAX_COOLDOWN_MINUTES = 43200  # 30 days


def validate_filter_dict(
    filter_json: Any, condition_type: Optional[str] = None, condition_value: Optional[str] = None
) -> dict[str, Any]:
    """Validate and canonicalize a rule filter dict (H-2, H-6).

    Rejects:
      - Empty filter object {}
      - Unexpected condition keys not in EVALUATOR_FILTER_FIELDS
      - Blank/null/whitespace string values for supported fields
      - Invalid severity_gte values (must be 0-10 integer)

    Returns the normalized filter dict.
    """
    if not isinstance(filter_json, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="filter must be a JSON object",
        )
    if not filter_json:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="filter must not be empty",
        )

    normalized: dict[str, Any] = {}
    for key, value in filter_json.items():
        if key not in EVALUATOR_FILTER_FIELDS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Unsupported filter key: {key}. "
                    f"Supported keys: {', '.join(sorted(EVALUATOR_FILTER_FIELDS))}"
                ),
            )
        # Reject blank/null/whitespace string values.
        if value is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Filter key '{key}' must not be null.",
            )
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Filter key '{key}' must not be empty or whitespace.",
                )
            normalized[key] = stripped
        elif isinstance(value, bool):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Filter key '{key}' must not be a boolean.",
            )
        elif isinstance(value, (int, float)):
            # Reject numeric values for enum-constrained fields (action, outcome).
            if key in ("action", "outcome"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Filter key '{key}' must be a valid enum string value, not a number.",
                )
            normalized[key] = value
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Filter key '{key}' has unsupported value type.",
            )

    # Validate action against Action enum.
    if "action" in normalized:
        action_val = str(normalized["action"]).strip().lower()
        valid_actions = {e.value for e in Action}
        if action_val not in valid_actions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Filter key 'action' must be one of: "
                    f"{', '.join(sorted(valid_actions))}. "
                    f"Got '{normalized['action']}'."
                ),
            )
        normalized["action"] = action_val

    # Validate outcome against Outcome enum.
    if "outcome" in normalized:
        outcome_val = str(normalized["outcome"]).strip().lower()
        # OutcomeEnum values: success, failure, unknown
        valid_outcomes = {"success", "failure", "unknown"}
        if outcome_val not in valid_outcomes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Filter key 'outcome' must be one of: "
                    f"{', '.join(sorted(valid_outcomes))}. "
                    f"Got '{normalized['outcome']}'."
                ),
            )
        normalized["outcome"] = outcome_val

    # Validate severity_gte range when present.
    if "severity_gte" in normalized:
        sev = normalized["severity_gte"]
        if not isinstance(sev, int) or isinstance(sev, bool):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="severity_gte must be an integer.",
            )
        if sev < _MIN_SEVERITY or sev > _MAX_SEVERITY:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"severity_gte must be between {_MIN_SEVERITY} and {_MAX_SEVERITY}, "
                    f"got {sev}."
                ),
            )

    return normalized


def validate_threshold_range(v: Optional[int]) -> Optional[int]:
    """Validate threshold is within allowed range."""
    if v is not None:
        if v < _MIN_THRESHOLD:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"threshold must be at least {_MIN_THRESHOLD}.",
            )
        if v > _MAX_THRESHOLD:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"threshold must be at most {_MAX_THRESHOLD}.",
            )
    return v


def validate_cooldown_range(v: Optional[int]) -> Optional[int]:
    """Validate cooldown_minutes is within allowed range."""
    if v is not None:
        if v < _MIN_COOLDOWN_MINUTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"cooldown_minutes must be at least {_MIN_COOLDOWN_MINUTES}.",
            )
        if v > _MAX_COOLDOWN_MINUTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"cooldown_minutes must be at most {_MAX_COOLDOWN_MINUTES}.",
            )
    return v


def validate_window_minutes_range(v: Optional[int]) -> Optional[int]:
    """Validate window_minutes is within allowed range."""
    if v is not None:
        if v < 1:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="window_minutes must be at least 1.",
            )
        if v > _MAX_WINDOW_SECONDS // 60:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"window_minutes must be at most {_MAX_WINDOW_SECONDS // 60}.",
            )
    return v


class ConditionBase(BaseModel):
    """A single alert rule condition, validated against the evaluator schema."""

    type: str
    value: Optional[str] = None
    threshold: Optional[int] = None
    window_seconds: Optional[int] = Field(None, alias="windowSeconds")
    group_by: Optional[str] = Field(None, alias="groupBy")
    field: Optional[str] = None

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in VALID_CONDITION_TYPES:
            raise ValueError(f"Unknown condition type: {v}")
        return v

    @field_validator("value")
    @classmethod
    def validate_value(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            stripped = v.strip()
            if not stripped:
                raise ValueError("condition value must not be empty or whitespace")
            return stripped
        return v

    @field_validator("threshold")
    @classmethod
    def validate_threshold(cls, v: Optional[int]) -> Optional[int]:
        return validate_threshold_range(v)

    @field_validator("window_seconds")
    @classmethod
    def validate_window(cls, v: Optional[int]) -> Optional[int]:
        if v is not None:
            if v < 1:
                raise ValueError("window_seconds must be at least 1")
            if v > 86400:
                raise ValueError("window_seconds must be at most 86400")
        return v

    @field_validator("group_by")
    @classmethod
    def validate_group_by(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            stripped = v.strip()
            if not stripped:
                raise ValueError("group_by must not be empty or whitespace")
            if stripped not in VALID_GROUP_BY:
                raise ValueError(f"Invalid group_by field: {v}")
            return stripped
        return v

    @field_validator("field")
    @classmethod
    def validate_field(cls, v: Optional[str], info) -> Optional[str]:
        if v is not None:
            stripped = v.strip().lower()
            if not stripped:
                raise ValueError("condition field must not be empty or whitespace")
            if stripped not in EVALUATOR_FILTER_FIELDS:
                raise ValueError(
                    f"Unsupported condition field: {v}. "
                    f"Supported fields: {', '.join(sorted(EVALUATOR_FILTER_FIELDS))}"
                )
            return stripped
        return v


class AlertRuleCreate(BaseModel):
    name: str
    tenant: str
    description: Optional[str] = None
    conditions: list[ConditionBase] = Field(default_factory=list)
    enabled: bool = True
    severity: str = "medium"
    rule_type: Optional[str] = None
    group_by: Optional[str] = None
    threshold: Optional[int] = None
    window_minutes: Optional[int] = None
    cooldown_minutes: Optional[int] = None
    notify: Optional[dict[str, Any]] = None
    filter: Optional[dict[str, Any]] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        stripped = v.strip()
        if len(stripped) < _MIN_NAME_LENGTH:
            raise ValueError("rule name must not be empty or whitespace")
        if len(stripped) > _MAX_NAME_LENGTH:
            raise ValueError(f"rule name must be at most {_MAX_NAME_LENGTH} characters")
        return stripped

    @field_validator("tenant")
    @classmethod
    def validate_tenant(cls, v: str) -> str:
        # Never treat empty/null/missing tenant as all-tenant scope.
        normalized = normalize_tenant(v)
        return normalized

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        normalized = v.strip().lower()
        if normalized not in VALID_SEVERITIES:
            raise ValueError(
                f"Invalid severity: {v}. "
                f"Supported values: {', '.join(sorted(VALID_SEVERITIES))}"
            )
        return normalized

    @field_validator("rule_type")
    @classmethod
    def validate_rule_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            normalized = v.strip().lower()
            if normalized not in VALID_RULE_TYPES:
                raise ValueError(
                    f"Unsupported rule type: {v}. "
                    f"Supported types: {', '.join(sorted(VALID_RULE_TYPES))}"
                )
            return normalized
        return v

    @field_validator("group_by")
    @classmethod
    def validate_top_level_group_by(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_GROUP_BY:
            raise ValueError(f"Invalid group_by: {v}")
        return v


class AlertRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    conditions: Optional[list[ConditionBase]] = None
    enabled: Optional[bool] = None
    severity: Optional[str] = None
    rule_type: Optional[str] = None
    group_by: Optional[str] = None
    threshold: Optional[int] = None
    window_minutes: Optional[int] = None
    cooldown_minutes: Optional[int] = None
    notify: Optional[dict[str, Any]] = None
    filter: Optional[dict[str, Any]] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            stripped = v.strip()
            if len(stripped) < _MIN_NAME_LENGTH:
                raise ValueError("rule name must not be empty or whitespace")
            if len(stripped) > _MAX_NAME_LENGTH:
                raise ValueError(
                    f"rule name must be at most {_MAX_NAME_LENGTH} characters"
                )
            return stripped
        return v

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            normalized = v.strip().lower()
            if normalized not in VALID_SEVERITIES:
                raise ValueError(
                    f"Invalid severity: {v}. "
                    f"Supported values: {', '.join(sorted(VALID_SEVERITIES))}"
                )
            return normalized
        return v

    @field_validator("rule_type")
    @classmethod
    def validate_rule_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            normalized = v.strip().lower()
            if normalized not in VALID_RULE_TYPES:
                raise ValueError(
                    f"Unsupported rule type: {v}. "
                    f"Supported types: {', '.join(sorted(VALID_RULE_TYPES))}"
                )
            return normalized
        return v

    @field_validator("group_by")
    @classmethod
    def validate_top_level_group_by(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_GROUP_BY:
            raise ValueError(f"Invalid group_by: {v}")
        return v


def _validate_conditions_non_empty(conditions: list[ConditionBase]) -> None:
    """Reject empty condition lists or blank condition structures (H-2)."""
    if not conditions or len(conditions) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one condition is required",
        )
    if len(conditions) > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only one condition is allowed per rule",
        )


async def _resolve_write_tenant(
    current_user: Any,
    requested_tenant: Optional[str],
    session: AsyncSession,
) -> str:
    """Resolve and validate the tenant for write operations (H-11).

    Tenant-bound administrators are restricted to their own tenant.
    Platform administrators must explicitly name an existing, active tenant.
    Empty/null tenant is never treated as an all-tenant scope.
    """
    if not requested_tenant or not requested_tenant.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="tenant is required",
        )

    if is_platform_admin(current_user):
        # Platform admin must name an existing, active tenant.
        normalized = normalize_tenant(requested_tenant)
        result = await session.execute(
            select(Tenant).where(Tenant.name == normalized, Tenant.is_active == True)  # noqa: E712
        )
        tenant_row = result.scalar_one_or_none()
        if not tenant_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant '{normalized}' not found or not active",
            )
        return normalized

    # Tenant-bound admin: restricted to their own tenant.
    user_tenant = tenant_key(getattr(current_user, "tenant", None))
    if not user_tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not assigned to a tenant",
        )
    if requested_tenant.strip().lower() != user_tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot create rule for different tenant",
        )
    return user_tenant


async def _check_duplicate_name(
    session: AsyncSession,
    name: str,
    tenant: str,
    exclude_id: Optional[str] = None,
) -> None:
    """Reject duplicate rule names within the same tenant scope (H-11)."""
    query = select(AlertRule).where(
        AlertRule.name == name,
        AlertRule.tenant == tenant,
    )
    if exclude_id is not None:
        query = query.where(AlertRule.id != exclude_id)
    result = await session.execute(query)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Rule with name '{name}' already exists in tenant '{tenant}'",
        )
