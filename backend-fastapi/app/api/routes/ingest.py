from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, asc
from sqlalchemy.orm import selectinload
from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone
from app.core.config import get_settings
from app.core.database import get_session
from app.core.dependencies import get_current_user, get_effective_tenant, verify_api_key, require_admin
from app.core.exceptions import ValidationError
from app.core.security import TokenPayload
from app.models.security_event import SecurityEvent
from app.models.alert import Alert, AlertRule, EmailNotification, EmailType, EmailStatus
from app.models.user import User
from app.models.tenant import Tenant
from app.services.ingest_service import IngestionService
from app.integrations.queue import enqueue_alert_email
from pydantic import BaseModel, ConfigDict, Field
from typing import Any
import json
import secrets
import hashlib

router = APIRouter()
settings = get_settings()


def resolve_tenant(api_user: TokenPayload, requested: Optional[str]) -> str:
    """Return the effective tenant, rejecting cross-tenant ingestion attempts."""
    effective = (api_user.tenant or "").strip()
    if not effective:
        raise HTTPException(
            status_code=403,
            detail="Ingestion credentials are not scoped to a tenant.",
        )
    if requested:
        normalized = str(requested).strip().lower()
        if normalized and normalized != effective:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Cannot ingest into tenant '{requested}'. "
                    f"Credential is scoped to '{effective}'."
                ),
            )
    return effective


def as_validation_http_error(exc: ValidationError) -> HTTPException:
    return HTTPException(status_code=400, detail=exc.message)


def owns_tenant(current_user: TokenPayload, tenant: Optional[str]) -> bool:
    """Admins may act on any tenant; other users only on their own."""
    if current_user.role == "ADMIN":
        return True
    return (current_user.tenant or "") == (tenant or "")


# =============================================================================
# Ingestion Endpoints
# =============================================================================

class IngestEventRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    source: Optional[str] = None
    tenant: Optional[str] = None

class IngestBatchRequest(BaseModel):
    events: List[dict]
    source: Optional[str] = None
    tenant: Optional[str] = None

class IngestResponse(BaseModel):
    success: bool
    eventId: Optional[str] = None
    message: str = ""
    alerts: List[dict] = []
    ingested: int = 0
    rejected: int = 0
    parsed: int = 0
    format: Optional[str] = None
    errors: List[dict] = []

@router.post("/ingest", response_model=IngestResponse)
async def ingest_single_event(
    request: IngestEventRequest,
    session: AsyncSession = Depends(get_session),
    api_user: TokenPayload = Depends(verify_api_key),
):
    """Ingest a single log event."""
    tenant = resolve_tenant(api_user, request.tenant)
    event_data = request.model_dump()
    source = event_data.pop("source", None)
    event_data.pop("tenant", None)

    service = IngestionService(session)
    try:
        result = await service.ingest(
            event_data, source, {"tenant": tenant, "username": api_user.username, "email": api_user.email}
        )
    except ValidationError as e:
        raise as_validation_http_error(e)

    return IngestResponse(
        success=True,
        eventId=result["event"].id,
        message="Event ingested",
        alerts=result["alerts"],
        ingested=1,
        parsed=1,
    )

@router.post("/ingest/batch", response_model=IngestResponse)
async def ingest_batch_events(
    request: IngestBatchRequest,
    session: AsyncSession = Depends(get_session),
    api_user: TokenPayload = Depends(verify_api_key),
):
    """Ingest multiple log events in batch."""
    tenant = resolve_tenant(api_user, request.tenant)
    if len(request.events) > settings.INGEST_BATCH_MAX_EVENTS:
        raise HTTPException(
            status_code=413,
            detail=f"Batch exceeds the limit of {settings.INGEST_BATCH_MAX_EVENTS} events.",
        )
    if not request.events:
        raise HTTPException(status_code=400, detail="Batch must contain at least one event.")

    service = IngestionService(session)
    try:
        result = await service.ingest_batch(
            request.events,
            request.source,
            {"tenant": tenant, "username": api_user.username, "email": api_user.email},
        )
    except ValidationError as e:
        raise as_validation_http_error(e)

    return IngestResponse(
        success=result["ingested"] > 0,
        ingested=result["ingested"],
        rejected=result["failed"],
        parsed=len(request.events),
        alerts=result.get("alerts", []),
        errors=[r for r in result["results"] if not r.get("success")],
    )

@router.post("/ingest/file", response_model=IngestResponse)
async def ingest_file(
    file: UploadFile = File(...),
    source: Optional[str] = Form(None),
    tenant: Optional[str] = Form(None),
    session: AsyncSession = Depends(get_session),
    api_user: TokenPayload = Depends(verify_api_key),
):
    """Ingest events from a file (JSON, JSONL, CSV, syslog text)."""
    effective_tenant = resolve_tenant(api_user, tenant)

    content = await file.read(settings.INGEST_MAX_FILE_BYTES + 1)
    if len(content) > settings.INGEST_MAX_FILE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {settings.INGEST_MAX_FILE_BYTES} byte upload limit.",
        )

    service = IngestionService(session)
    try:
        result = await service.ingest_file(
            content,
            file.filename or "",
            file.content_type,
            source,
            effective_tenant,
            {"tenant": effective_tenant, "username": api_user.username, "email": api_user.email},
        )
    except ValidationError as e:
        raise as_validation_http_error(e)

    return IngestResponse(
        success=result["ingested"] > 0,
        ingested=result["ingested"],
        rejected=result["failed"],
        parsed=result.get("parsed", 0),
        format=result.get("format"),
        alerts=result.get("alerts", []),
        errors=[r for r in result["results"] if not r.get("success")],
        message=(
            f"Parsed {result.get('parsed', 0)} records from {file.filename} "
            f"as {result.get('format')}: {result['ingested']} accepted, "
            f"{result['failed']} rejected."
        ),
    )


# =============================================================================
# Alert Endpoints
# =============================================================================

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
    current_user: TokenPayload = Depends(get_current_user),
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
        query = query.where(
            (Alert.title.ilike(f"%{search}%")) |
            (Alert.description.ilike(f"%{search}%"))
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
            "rule": {"name": a.rule.name, "description": a.rule.description} if a.rule else None,
            "dedupeKey": a.dedupe_key,
        } for a in alerts],
        "hasNextPage": has_next,
        "newCursor": next_cursor,
    }

@router.patch("/alerts/{alert_id}", response_model=dict)
async def update_alert_status(
    alert_id: str,
    update: AlertStatusUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: TokenPayload = Depends(require_admin),
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


# =============================================================================
# Alert Rules Endpoints
# =============================================================================

class AlertRuleCreate(BaseModel):
    name: str
    tenant: str
    description: Optional[str] = None
    conditions: List[dict]
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
    current_user: TokenPayload = Depends(require_admin),
):
    """List alert rules."""
    requested_tenant = (tenant or "").strip()
    if current_user.role == "ADMIN":
        effective_tenant = None if requested_tenant in ("", "all") else requested_tenant
    else:
        effective_tenant = current_user.tenant

    query = select(AlertRule)
    if effective_tenant:
        query = query.where(AlertRule.tenant == effective_tenant)
    
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
        "newCursor": next_cursor,
    }

@router.post("/create-alertRule", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_alert_rule(
    rule: AlertRuleCreate,
    session: AsyncSession = Depends(get_session),
    current_user: TokenPayload = Depends(require_admin),
):
    """Create a new alert rule."""
    # Validate tenant ownership (admin may target any tenant)
    if not owns_tenant(current_user, rule.tenant):
        raise HTTPException(status_code=403, detail="Cannot create rule for different tenant")
    
    # Validate conditions
    if not rule.conditions or len(rule.conditions) != 1:
        raise HTTPException(status_code=400, detail="Exactly one condition required")
    
    condition = rule.conditions[0]
    if condition["type"] not in ["event_type", "severity_min", "field_value", "threshold_count", "repeated_failures"]:
        raise HTTPException(status_code=400, detail="Invalid condition type")
    
    new_rule = AlertRule(
        name=rule.name,
        description=rule.description,
        tenant=rule.tenant,
        enabled=rule.enabled,
        severity=rule.severity,
        conditions=rule.conditions,
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
    rule: AlertRuleUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: TokenPayload = Depends(require_admin),
):
    """Update an alert rule."""
    result = await session.execute(
        select(AlertRule).where(AlertRule.id == rule_id)
    )
    existing = result.scalar_one_or_none()
    if not existing or not owns_tenant(current_user, existing.tenant):
        raise HTTPException(status_code=404, detail="Rule not found")
    
    # Check for duplicate name
    if rule.name and rule.name != existing.name:
        result = await session.execute(
            select(AlertRule).where(
                AlertRule.name == rule.name,
                AlertRule.tenant == existing.tenant,
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
    enabled: bool,
    session: AsyncSession = Depends(get_session),
    current_user: TokenPayload = Depends(require_admin),
):
    """Enable or disable an alert rule."""
    result = await session.execute(
        select(AlertRule).where(AlertRule.id == rule_id)
    )
    rule = result.scalar_one_or_none()
    if not rule or not owns_tenant(current_user, rule.tenant):
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
    current_user: TokenPayload = Depends(require_admin),
):
    """Delete an alert rule."""
    result = await session.execute(
        select(AlertRule).where(AlertRule.id == rule_id)
    )
    rule = result.scalar_one_or_none()
    if not rule or not owns_tenant(current_user, rule.tenant):
        raise HTTPException(status_code=404, detail="Rule not found")
    
    # Check if rule has triggered alerts
    alert_count = await session.execute(
        select(func.count()).select_from(Alert).where(Alert.rule_id == rule_id)
    )
    if alert_count.scalar() > 0:
        raise HTTPException(status_code=409, detail="Cannot delete rule with existing alerts")
    
    await session.delete(rule)
    await session.commit()
    
    return {"message": "Alert rule deleted"}


# =============================================================================
# User Management Endpoints (Admin only)
# =============================================================================

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    tenant: str
    status: str
    createAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None

@router.get("/get-users", response_model=dict)
async def list_users(
    tenant: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 25,
    cursor: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    current_user: TokenPayload = Depends(require_admin),
):
    """List all users (Admin only)."""
    requested_tenant = (tenant or "").strip()
    effective_tenant = None if requested_tenant in ("", "all") else requested_tenant

    query = select(User)
    if effective_tenant:
        query = query.where(User.tenant == effective_tenant)
    if search:
        search_term = f"%{search}%"
        query = query.where(
            (User.username.ilike(f"%{search}%")) |
            (User.email.ilike(f"%{search}%"))
        )
    
    query = query.order_by(desc(User.create_at)).limit(limit + 1)
    if cursor:
        query = query.where(User.id > cursor)
    
    result = await session.execute(query)
    users = result.scalars().all()
    
    has_next = len(users) > limit
    if has_next:
        users = users[:limit]
    
    next_cursor = users[-1].id if has_next else None
    
    return {
        "usersList": [{
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "role": u.role,
            "tenant": u.tenant,
            "status": u.status,
            "createAt": u.create_at.isoformat() if u.create_at else None,
            "updatedAt": u.updated_at.isoformat() if u.updated_at else None,
        } for u in users],
        "newCursor": next_cursor,
    }

@router.post("/create-user", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    username: str = Form(...),
    email: str = Form(...),
    tenant: str = Form(...),
    role: str = Form("VIEWER"),
    status: str = Form("ACTIVE"),
    password: str = Form(...),
    session: AsyncSession = Depends(get_session),
    current_user: TokenPayload = Depends(require_admin),
):
    """Create a new user (Admin only)."""
    if not owns_tenant(current_user, tenant):
        raise HTTPException(status_code=403, detail="Cannot create user for different tenant")
    
    from app.core.security import hash_password
    
    existing = await session.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")
    
    hashed = hash_password(password)
    user = User(
        username=username,
        email=email,
        tenant=tenant,
        role=role,
        status=status,
        password=hashed,
    )
    
    session.add(user)
    await session.commit()
    await session.refresh(user)
    
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        tenant=user.tenant,
        status=user.status,
        createAt=user.create_at,
        updatedAt=user.updated_at,
    )

@router.put("/update-user", response_model=UserResponse)
async def update_user(
    id: int = Form(...),
    username: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    tenant: Optional[str] = Form(None),
    role: Optional[str] = Form(None),
    status: Optional[str] = Form(None),
    session: AsyncSession = Depends(get_session),
    current_user: TokenPayload = Depends(require_admin),
):
    """Update a user (Admin only)."""
    result = await session.execute(select(User).where(User.id == id))
    user = result.scalar_one_or_none()
    if not user or not owns_tenant(current_user, user.tenant):
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent self-demotion or self-disabling
    if user.id == current_user.user_id:
        if role is not None and role != "ADMIN":
            raise HTTPException(status_code=403, detail="Cannot change your own role from ADMIN")
        if status is not None and status != "ACTIVE":
            raise HTTPException(status_code=403, detail="Cannot deactivate yourself")
    
    # Prevent demoting/disabling the last admin
    if role is not None and user.role == "ADMIN" and role != "ADMIN":
        admin_count = await session.execute(select(func.count()).select_from(User).where(User.role == "ADMIN", User.status == "ACTIVE"))
        if admin_count.scalar() <= 1:
            raise HTTPException(status_code=403, detail="Cannot demote the last active admin")
    if status is not None and user.role == "ADMIN" and user.status == "ACTIVE" and status != "ACTIVE":
        admin_count = await session.execute(select(func.count()).select_from(User).where(User.role == "ADMIN", User.status == "ACTIVE"))
        if admin_count.scalar() <= 1:
            raise HTTPException(status_code=403, detail="Cannot deactivate the last active admin")
    
    if username is not None:
        user.username = username
    if email is not None:
        user.email = email
    if tenant is not None:
        user.tenant = tenant
    if role is not None:
        user.role = role
    if status is not None:
        user.status = status
    
    await session.commit()
    await session.refresh(user)
    
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        tenant=user.tenant,
        status=user.status,
        createAt=user.create_at,
        updatedAt=user.updated_at,
    )

@router.delete("/delete-user/{user_id}", response_model=dict)
async def delete_user(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: TokenPayload = Depends(require_admin),
):
    """Delete a user (Admin only)."""
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not owns_tenant(current_user, user.tenant):
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent self-deletion
    if user.id == current_user.user_id:
        raise HTTPException(status_code=403, detail="Cannot delete yourself")
    
    # Prevent deleting the last active admin
    if user.role == "ADMIN" and user.status == "ACTIVE":
        admin_count = await session.execute(select(func.count()).select_from(User).where(User.role == "ADMIN", User.status == "ACTIVE"))
        if admin_count.scalar() <= 1:
            raise HTTPException(status_code=403, detail="Cannot delete the last active admin")
    
    await session.delete(user)
    await session.commit()
    
    return {"message": "User deleted successfully"}

@router.get("/get-all-data", response_model=dict)
async def get_all_data(
    tenant: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    current_user: TokenPayload = Depends(require_admin),
):
    """Get aggregated data counts for dashboard (admin cross-tenant view)."""
    requested = (tenant or "").strip()
    if current_user.role != "ADMIN":
        requested = current_user.tenant or ""
    effective_tenant = None if requested in ("", "all") else requested

    def tenant_filter(model):
        return [model.tenant == effective_tenant] if effective_tenant else []

    total_events = await session.execute(
        select(func.count()).select_from(SecurityEvent).where(*tenant_filter(SecurityEvent))
    )
    total_alerts = await session.execute(
        select(func.count()).select_from(Alert).where(*tenant_filter(Alert))
    )
    total_rules = await session.execute(
        select(func.count()).select_from(AlertRule).where(*tenant_filter(AlertRule))
    )
    total_users = await session.execute(
        select(func.count()).select_from(User).where(*tenant_filter(User))
    )

    result: Dict[str, Any] = {
        "data": {
            "allLogs": total_events.scalar() or 0,
            "allUsers": total_users.scalar() or 0,
            "allAlerts": total_alerts.scalar() or 0,
            "allRules": total_rules.scalar() or 0,
        }
    }
    if effective_tenant is None:
        by_tenant = await session.execute(
            select(SecurityEvent.tenant, func.count()).group_by(SecurityEvent.tenant)
        )
        result["data"]["logsByTenant"] = {row[0]: row[1] for row in by_tenant}
    return result


# =============================================================================
# Tenant Management Endpoints (Admin Only)
# =============================================================================

class TenantCreateRequest(BaseModel):
    name: str
    is_active: bool = True


class TenantCreateResponse(BaseModel):
    id: str
    name: str
    api_key: str  # Returned ONLY once
    is_active: bool
    created_at: str


class TenantResponse(BaseModel):
    id: str
    name: str
    is_active: bool
    created_at: str
    alert_webhook_url: Optional[str] = None
    alert_emails: Optional[List[str]] = None


class TenantUpdateRequest(BaseModel):
    is_active: Optional[bool] = None


@router.post("/tenants", response_model=TenantCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    request: TenantCreateRequest,
    session: AsyncSession = Depends(get_session),
    current_user: TokenPayload = Depends(require_admin),
):
    """Create a new tenant. Returns the API key ONCE - store it securely."""
    from app.models.enums import Role

    # Validate tenant name using normalize_tenant logic
    name = (request.name or "").strip().lower()
    if not name:
        raise HTTPException(status_code=422, detail="Tenant name is required")
    if name == "all":
        raise HTTPException(status_code=422, detail="Tenant name 'all' is reserved")
    import re
    if not re.match(r"^[a-z0-9_-]{2,50}$", name):
        raise HTTPException(
            status_code=422,
            detail=(
                f"Tenant name '{name}' is invalid. "
                f"Must be 2-50 chars: lowercase letters, digits, underscore, hyphen."
            ),
        )

    # Check for duplicate
    existing = await session.execute(select(Tenant).where(Tenant.name == name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Tenant '{name}' already exists")

    # Generate a 32-byte url-safe API key
    api_key = secrets.token_urlsafe(32)
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    tenant_id = hashlib.sha256(name.encode()).hexdigest()[:25]

    tenant = Tenant(
        id=tenant_id,
        name=name,
        api_key_hash=api_key_hash,
        is_active=request.is_active,
    )
    session.add(tenant)
    await session.commit()
    await session.refresh(tenant)

    return TenantCreateResponse(
        id=tenant.id,
        name=tenant.name,
        api_key=api_key,  # Returned ONLY once
        is_active=tenant.is_active,
        created_at=tenant.created_at.isoformat() if tenant.created_at else "",
    )


@router.get("/tenants", response_model=List[TenantResponse])
async def list_tenants(
    session: AsyncSession = Depends(get_session),
    current_user: TokenPayload = Depends(require_admin),
):
    """List all tenants. API keys and hashes are NOT exposed."""
    result = await session.execute(select(Tenant).order_by(Tenant.name))
    tenants = result.scalars().all()
    return [
        TenantResponse(
            id=t.id,
            name=t.name,
            is_active=t.is_active,
            created_at=t.created_at.isoformat() if t.created_at else "",
            alert_webhook_url=t.alert_webhook_url,
            alert_emails=t.alert_emails,
        )
        for t in tenants
    ]


@router.patch("/tenants/{name}", response_model=TenantResponse)
async def update_tenant(
    name: str,
    request: TenantUpdateRequest,
    session: AsyncSession = Depends(get_session),
    current_user: TokenPayload = Depends(require_admin),
):
    """Activate or deactivate a tenant. Deactivating blocks all its users' logins."""
    result = await session.execute(select(Tenant).where(Tenant.name == name))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant '{name}' not found")

    if request.is_active is not None:
        tenant.is_active = request.is_active
        await session.commit()
        await session.refresh(tenant)

    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        is_active=tenant.is_active,
        created_at=tenant.created_at.isoformat() if tenant.created_at else "",
        alert_webhook_url=tenant.alert_webhook_url,
        alert_emails=tenant.alert_emails,
    )


@router.post("/tenants/{name}/rotate-key", response_model=TenantCreateResponse)
async def rotate_tenant_key(
    name: str,
    session: AsyncSession = Depends(get_session),
    current_user: TokenPayload = Depends(require_admin),
):
    """Rotate a tenant's API key. The old key is invalidated immediately."""
    result = await session.execute(select(Tenant).where(Tenant.name == name))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant '{name}' not found")

    # Generate a new 32-byte url-safe API key
    new_api_key = secrets.token_urlsafe(32)
    new_key_hash = hashlib.sha256(new_api_key.encode()).hexdigest()

    tenant.api_key_hash = new_key_hash
    await session.commit()
    await session.refresh(tenant)

    return TenantCreateResponse(
        id=tenant.id,
        name=tenant.name,
        api_key=new_api_key,  # Returned ONLY once
        is_active=tenant.is_active,
        created_at=tenant.created_at.isoformat() if tenant.created_at else "",
    )
