from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, asc, or_, and_
from sqlalchemy.orm import selectinload
from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone
from app.core.config import get_settings
from app.core.database import get_session
from app.core.dependencies import get_current_user, get_effective_tenant, verify_api_key, require_admin
from app.core.exceptions import ValidationError, is_transient_db_error
from app.core.rule_validation import (
    VALID_RULE_TYPES,
    VALID_SEVERITIES,
    validate_cooldown_range,
    validate_filter_dict,
    validate_threshold_range,
    validate_window_minutes_range,
)
from app.core.security import TokenPayload
from app.core.tenancy import is_platform_admin, normalize_tenant, resolve_read_tenant, tenant_key
from app.models.events import Event
from app.models.enums import Role, Status
from app.models.alert import Alert, AlertRule, EmailNotification, EmailType, EmailStatus
from app.models.user import User
from app.models.tenant import Tenant
from app.services.ingest_service import IngestionService
from app.services.notifier import (
    is_valid_email,
    send_email_notification,
    send_webhook,
)
from app.integrations.queue import enqueue_alert_email
from app.integrations.syslog import parse_syslog_message
from app.core.limiting import limiter
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from typing import Any
import json
import logging
import secrets
import hashlib
import uuid

logger = logging.getLogger(__name__)

router = APIRouter()

public_router = APIRouter(include_in_schema=False)
settings = get_settings()


def resolve_tenant(api_user: TokenPayload, requested: Optional[str]) -> str:
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


_MEANINGFUL_FIELDS = {
    "event_type", "eventname", "event", "type", "user", "username", "user_name",
    "userid", "user_id", "ip", "src_ip", "srcip", "sourceip", "source_ip",
    "dst_ip", "dstip", "destinationip", "destination_ip", "host", "hostname",
    "process", "action", "severity", "source", "vendor", "product",
    "rule_name", "rule", "policy", "url", "http_method", "method",
    "status_code", "status", "event_id", "eventid", "logon_type", "logontype",
    "cloud", "sha256", "reason", "description", "msg", "message",
}


def _normalized_field_key(key: Any) -> str:
    return str(key or "").lower().replace("_", "").replace("-", "")


_MEANINGFUL_FIELDS_NORMALIZED = {_normalized_field_key(field) for field in _MEANINGFUL_FIELDS}
_IGNORED_FIELDS_NORMALIZED = {
    _normalized_field_key(field)
    for field in ("source", "tenant", "@timestamp", "timestamp", "tags", "raw")
}


def _is_meaningless_event(event_data: dict) -> bool:
    """True when an event carries no fields that can produce a log entry.

    Keys are compared without case, underscores, or hyphens so the UI's
    camelCase payload and the machine API's snake_case payload behave the same.
    """
    for key, value in event_data.items():
        normalized = _normalized_field_key(key)
        if normalized in _IGNORED_FIELDS_NORMALIZED:
            continue
        if normalized in _MEANINGFUL_FIELDS_NORMALIZED and value not in (None, "", [], {}):
            return False
    return True


def _validate_timestamp(value: Any, field_name: str = "@timestamp") -> None:
    if value is None or value == "":
        return
    if isinstance(value, (int, float)):
        return
    try:
        datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid {field_name}: '{value}'. Must be RFC3339 ISO-8601 (e.g. 2025-08-20T07:20:00Z).",
        )


def _parse_date_filter(value: str, field_name: str) -> datetime:
    """Parse a UI date filter as a midnight-UTC timestamp.

    The date picker sends ``YYYY-MM-DD``; ISO datetimes are also accepted.
    """
    raw = str(value).strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid {field_name} '{value}'. Use YYYY-MM-DD.",
        )
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )


def as_validation_http_error(exc: ValidationError) -> HTTPException:
    return HTTPException(status_code=400, detail=exc.message)


def is_platform_admin(current_user: TokenPayload) -> bool:
    """An ADMIN without a tenant is a platform administrator.

    Admins created inside a tenant are tenant-bound and must not manage other
    tenants. VIEWERs are always bound to their own tenant.
    """
    return current_user.role == "ADMIN" and not tenant_key(current_user.tenant)


def owns_tenant(current_user: TokenPayload, tenant: Optional[str]) -> bool:
    if is_platform_admin(current_user):
        return True
    return tenant_key(current_user.tenant) == tenant_key(tenant)


def effective_read_tenant(
    current_user: TokenPayload, requested: Optional[str]
) -> Optional[str]:
    """Resolve the tenant filter for read endpoints.

    Platform admins may ask for a specific tenant or all tenants. Everyone
    else, including tenant-bound admins and viewers without a tenant, is
    restricted to their own tenant; a missing tenant is a 403, never "all".
    """
    return resolve_read_tenant(current_user, requested)


def require_platform_admin(current_user: TokenPayload) -> None:
    if not is_platform_admin(current_user):
        raise HTTPException(
            status_code=403,
            detail="Tenant management requires a platform administrator",
        )


async def _require_active_tenant(session: AsyncSession, tenant_name: str) -> Tenant:
    """Return the tenant row, rejecting unknown or inactive tenants."""

    result = await session.execute(select(Tenant).where(Tenant.name == tenant_name))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(
            status_code=404,
            detail=f"Tenant '{tenant_name}' not found",
        )
    if not tenant.is_active:
        raise HTTPException(
            status_code=422,
            detail=f"Tenant '{tenant_name}' is not active",
        )
    return tenant


async def resolve_ui_ingest_tenant(
    current_user: TokenPayload,
    requested: Optional[str],
    session: AsyncSession,
) -> str:
    """Resolve the tenant for a session-authenticated UI ingest.

    Tenant-bound administrators can only write to their own tenant; a requested
    tenant that differs is rejected instead of silently rewritten. Platform
    administrators (ADMIN with no tenant) must name an existing, active tenant.
    Empty, reserved ("all", "*") and malformed values are rejected.
    """
    requested_tenant: Optional[str] = None
    if requested is not None and str(requested).strip():
        requested_tenant = normalize_tenant(requested)

    own_tenant = tenant_key(current_user.tenant)

    if own_tenant:
        if requested_tenant and requested_tenant != own_tenant:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Cannot ingest into tenant '{requested}'. "
                    f"Your account is scoped to '{own_tenant}'."
                ),
            )
        target_tenant = normalize_tenant(own_tenant)
    else:
        if not requested_tenant:
            raise HTTPException(
                status_code=422,
                detail="tenant is required for an administrator without a tenant scope.",
            )
        target_tenant = requested_tenant

    await _require_active_tenant(session, target_tenant)
    return target_tenant


def _validated_role(value: str) -> str:
    normalized = str(value or "").strip().upper()
    if normalized not in {role.value for role in Role}:
        raise HTTPException(
            status_code=422,
            detail="role must be ADMIN or VIEWER",
        )
    return normalized


def _validated_status(value: str) -> str:
    normalized = str(value or "").strip().upper()
    if normalized not in {member.value for member in Status}:
        raise HTTPException(
            status_code=422,
            detail="status must be ACTIVE, INACTIVE, or FREEZE",
        )
    return normalized






class IngestEventRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    source: Optional[str] = None
    tenant: Optional[str] = None

class IngestBatchRequest(BaseModel):
    events: List[dict]
    source: Optional[str] = None
    tenant: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def accept_bare_array(cls, value: Any) -> Any:
        """Accept both ``{"events": [...]}`` and a bare JSON array.

        The documented batch contract is the wrapped object, but several
        senders (and the sample script) post a bare array. Supporting both
        removes a confusing 422 without changing machine authentication.
        """
        if isinstance(value, list):
            return {"events": value}
        return value


class UIIngestRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

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
@public_router.post("/ingest", response_model=IngestResponse)
@limiter.limit(lambda: get_settings().INGEST_RATE_LIMIT)
async def ingest_single_event(
    request: Request,
    session: AsyncSession = Depends(get_session),
    api_user: TokenPayload = Depends(verify_api_key),
):

    body = await _read_limited_body(request, settings.INGEST_MAX_BODY_BYTES)
    if not body:
        raise HTTPException(
            status_code=400,
            detail="Empty request body. Send a JSON object with at least one event field.",
        )
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail="Invalid JSON or non-UTF8 encoding in request body.",
        )
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=400,
            detail="Request body must be a JSON object.",
        )

    tenant = resolve_tenant(api_user, payload.get("tenant"))
    event_data = {k: v for k, v in payload.items() if k not in ("source", "tenant")}
    source = payload.get("source")


    if _is_meaningless_event(event_data):
        raise HTTPException(
            status_code=422,
            detail="Event has no meaningful fields. Provide at least one of: "
                   "event_type, user, ip, src_ip, host, action, severity, source, etc.",
        )


    ts_value = payload.get("@timestamp") or payload.get("timestamp")
    _validate_timestamp(ts_value, "@timestamp")

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
@public_router.post("/ingest/batch", response_model=IngestResponse)
@limiter.limit(lambda: get_settings().INGEST_RATE_LIMIT)
async def ingest_batch_events(
    request: Request,
    session: AsyncSession = Depends(get_session),
    api_user: TokenPayload = Depends(verify_api_key),
):
    body = await _read_limited_body(request, settings.INGEST_MAX_BODY_BYTES)
    if not body:
        raise HTTPException(status_code=400, detail="Empty request body.")
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail="Invalid JSON or non-UTF8 encoding in request body.",
        )
    # Accept both {"events": [...]} and a bare JSON array.
    if isinstance(payload, list):
        payload = {"events": payload}
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=400,
            detail="Request body must be a JSON object.",
        )

    events = payload.get("events")
    source = payload.get("source")
    tenant = payload.get("tenant")

    if not isinstance(events, list):
        raise HTTPException(
            status_code=400, detail="Batch 'events' must be a list of event objects."
        )
    if len(events) > settings.INGEST_BATCH_MAX_EVENTS:
        raise HTTPException(
            status_code=413,
            detail=f"Batch exceeds the limit of {settings.INGEST_BATCH_MAX_EVENTS} events.",
        )
    if not events:
        raise HTTPException(status_code=400, detail="Batch must contain at least one event.")

    for idx, event in enumerate(events):
        if not isinstance(event, dict):
            raise HTTPException(
                status_code=400,
                detail=f"Batch event at index {idx} must be a JSON object.",
            )
        # Validate individual raw payload size.
        raw = json.dumps(event, default=str).encode("utf-8")
        if len(raw) > settings.INGEST_MAX_RAW_EVENT_BYTES:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"Batch event at index {idx} exceeds the "
                    f"{settings.INGEST_MAX_RAW_EVENT_BYTES} byte raw payload limit."
                ),
            )
        ts_value = event.get("@timestamp") or event.get("timestamp")
        _validate_timestamp(ts_value, f"events[{idx}].@timestamp")

    tenant = resolve_tenant(api_user, tenant)
    service = IngestionService(session)
    try:
        result = await service.ingest_batch(
            events,
            source,
            {"tenant": tenant, "username": api_user.username, "email": api_user.email},
        )
    except ValidationError as e:
        raise as_validation_http_error(e)

    return IngestResponse(
        success=result["ingested"] > 0,
        ingested=result["ingested"],
        rejected=result["failed"],
        parsed=len(events),
        alerts=result.get("alerts", []),
        errors=[r for r in result["results"] if not r.get("success")],
    )

@router.post("/ingest/file", response_model=IngestResponse)
@public_router.post("/ingest/file", response_model=IngestResponse)
@limiter.limit(lambda: get_settings().INGEST_RATE_LIMIT)
async def ingest_file(
    request: Request,
    file: UploadFile = File(...),
    source: Optional[str] = Form(None),
    tenant: Optional[str] = Form(None),
    session: AsyncSession = Depends(get_session),
    api_user: TokenPayload = Depends(verify_api_key),
):
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


@router.post("/ingest/ui", response_model=IngestResponse)
@limiter.limit(lambda: get_settings().INGEST_UI_RATE_LIMIT)
async def ingest_ui_event(
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_user: TokenPayload = Depends(require_admin),
):
    """Ingest one event from the signed-in admin UI.

    This is deliberately separate from ``/ingest``: machine senders keep using
    an API key, while the browser uses its normal session. The tenant always
    comes from the authenticated account (or an explicit value that a platform
    admin is allowed to choose), never from an untrusted client default.
    """
    body = await _read_limited_body(request, settings.INGEST_MAX_BODY_BYTES)
    if not body:
        raise HTTPException(
            status_code=400,
            detail="Empty request body. Send a JSON object with at least one event field.",
        )
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail="Invalid JSON or non-UTF8 encoding in request body.",
        )
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=400,
            detail="Request body must be a JSON object.",
        )

    tenant = await resolve_ui_ingest_tenant(
        current_user, payload.get("tenant"), session
    )

    event_data = {k: v for k, v in payload.items() if k not in ("source", "tenant")}
    source = event_data.pop("source", None)

    if _is_meaningless_event(event_data):
        raise HTTPException(
            status_code=422,
            detail="Event has no meaningful fields. Provide at least one of: "
                   "event_type, user, ip, src_ip, host, action, severity, source, etc.",
        )

    _validate_timestamp(
        event_data.get("@timestamp") or event_data.get("timestamp"),
        "@timestamp",
    )

    service = IngestionService(session)
    try:
        result = await service.ingest(
            event_data,
            source,
            {
                "tenant": tenant,
                "username": current_user.username,
                "email": current_user.email,
            },
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






class AlertStatusUpdate(BaseModel):
    status: str


class TestNotificationRequest(BaseModel):
    channel: str
    recipient: Optional[str] = None
    webhook_url: Optional[str] = None


class SyslogIngestResponse(BaseModel):
    accepted: int
    rejected: int
    errors: List[dict] = []


async def _read_limited_body(request: Request, max_bytes: int) -> bytes:
    """Read the request body, rejecting anything over ``max_bytes``.

    Reads the ASGI request stream in chunks and rejects the request with 413
    as soon as the running total exceeds ``max_bytes``. Bodies larger than the
    limit are never fully buffered. Works for chunked requests and requests
    without a trustworthy Content-Length header. Chunks are accumulated only
    up to the limit, so memory usage is bounded by ``max_bytes``.
    """
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > max_bytes:
                raise HTTPException(
                    status_code=413,
                    detail=f"Request body exceeds the {max_bytes} byte limit.",
                )
        except ValueError:
            pass

    chunks: List[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"Request body exceeds the {max_bytes} byte limit.",
            )
        chunks.append(chunk)
    return b"".join(chunks)


@router.post(
    "/ingest/syslog",
    response_model=SyslogIngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
@limiter.limit(lambda: get_settings().INGEST_RATE_LIMIT)
async def ingest_syslog_http(
    request: Request,
    session: AsyncSession = Depends(get_session),
    api_user: TokenPayload = Depends(verify_api_key),
):
    """Ingest newline-delimited syslog lines over HTTPS.

    This is the SaaS counterpart to the UDP/TCP listener. It reuses the same
    ``parse_syslog_message`` parser and ``IngestionService`` /
    ``NormalizationService`` path; only the transport tag and tenant context
    differ.
    """
    current_settings = get_settings()
    body = await _read_limited_body(
        request, current_settings.INGEST_HTTP_SYSLOG_MAX_BYTES
    )
    if not body.strip():
        raise HTTPException(status_code=400, detail="Empty syslog request body.")

    content_type = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    text = body.decode("utf-8", errors="replace")

    requested_tenant: Optional[str] = request.query_params.get("tenant")
    lines: List[Any]
    if content_type == "application/json" or text.lstrip().startswith("{"):
        try:
            payload = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            raise HTTPException(status_code=400, detail="Invalid JSON syslog body.")
        if not isinstance(payload, dict) or not isinstance(payload.get("lines"), list):
            raise HTTPException(
                status_code=400,
                detail='JSON syslog body must be {"lines": ["<syslog line>", ...]}.',
            )
        requested_tenant = payload.get("tenant") or requested_tenant
        lines = payload["lines"]
    else:
        lines = text.splitlines()

    tenant = resolve_tenant(api_user, requested_tenant)

    max_lines = current_settings.INGEST_HTTP_SYSLOG_MAX_LINES
    if len(lines) > max_lines:
        raise HTTPException(
            status_code=413,
            detail=f"Syslog batch exceeds the {max_lines} line limit.",
        )

    remote_address = request.client.host if request.client else None
    remote_port = request.client.port if request.client else None
    context = {
        "tenant": tenant,
        "username": api_user.username,
        "email": api_user.email,
    }

    events: List[tuple[int, Dict[str, Any]]] = []
    pre_rejected: List[dict] = []
    for index, line in enumerate(lines):
        if not isinstance(line, str):
            pre_rejected.append({"index": index, "success": False, "error": "line must be a string"})
            continue
        if not line.strip():
            continue

        parsed = None
        try:
            parsed = parse_syslog_message(line)
        except Exception as exc:  # noqa: BLE001 - isolate a broken line
            logger.warning("syslog line %d could not be parsed: %s", index, exc)
        if not parsed:
            pre_rejected.append({"index": index, "success": False, "error": "unable to parse syslog line"})
            continue

        event = dict(parsed)
        tags = list(event.get("tags") or [])
        if "transport=http-syslog" not in tags:
            tags.append("transport=http-syslog")
        event["tags"] = tags
        event["remoteAddress"] = remote_address
        event["remotePort"] = remote_port
        events.append((index, event))

    service = IngestionService(session)
    try:
        results = await service.ingest_batch_atomic(
            events,
            current_settings.SYSLOG_SOURCE,
            context,
            pre_rejected=pre_rejected,
        )
    except Exception as exc:  # noqa: BLE001 - map infra failure to a retryable 5xx
        await session.rollback()
        transient = is_transient_db_error(exc)
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE if transient else status.HTTP_500_INTERNAL_SERVER_ERROR
        logger.error(
            "syslog HTTPS ingest failed for tenant %s (transient=%s): %s: %s",
            tenant,
            transient,
            type(exc).__name__,
            exc,
        )
        # Nothing was persisted: the batch transaction was rolled back. Keep the
        # existing response shape so forwarders can parse it while still
        # treating the request as a retryable failure.
        return JSONResponse(
            status_code=status_code,
            content={
                "accepted": 0,
                "rejected": len(events) + len(pre_rejected),
                "errors": [
                    {
                        "line": None,
                        "error": (
                            "temporary storage failure; retry this request"
                            if transient
                            else "ingestion failed"
                        ),
                    }
                ],
            },
            headers={"Retry-After": "5"} if transient else None,
        )

    errors = [
        {"line": entry.get("index"), "error": entry.get("error")}
        for entry in results.get("results", [])
        if not entry.get("success", False)
    ]
    return SyslogIngestResponse(
        accepted=results.get("ingested", 0),
        rejected=results.get("failed", 0),
        errors=errors,
    )


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
    requested_tenant = (tenant or "").strip()
    effective_tenant = effective_read_tenant(current_user, requested_tenant)

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
            or_(
                Alert.title.ilike(f"%{search}%"),
                Alert.description.ilike(f"%{search}%"),
                func.array_to_string(Alert.tags, ',').ilike(f"%{search}%")
            )
        )

    query = query.order_by(desc(Alert.triggered_at), desc(Alert.id)).limit(limit + 1)
    if cursor:
        cursor_alert = await session.get(Alert, cursor)
        if cursor_alert is None:
            return {"alerts": [], "hasNextPage": False, "newCursor": None}
        query = query.where(
            or_(
                Alert.triggered_at < cursor_alert.triggered_at,
                and_(
                    Alert.triggered_at == cursor_alert.triggered_at,
                    Alert.id < cursor,
                ),
            )
        )

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
            "count": a.count,
            "group_key": a.group_key,
            "triggeredAt": a.triggered_at.isoformat() if a.triggered_at else None,
            "eventIds": a.event_ids,
            "tags": a.tags,
            "notifications": a.notifications or [],
            "rule": {"name": a.rule.name, "description": a.rule.description} if a.rule else None,
            "dedupeKey": a.dedupe_key,
        } for a in alerts],
        "hasNextPage": has_next,
        "newCursor": next_cursor,
    }

@router.post("/alerts/test-notification", response_model=dict)
async def send_test_notification(
    payload: "TestNotificationRequest",
    current_user: TokenPayload = Depends(require_admin),
):
    """Send a one-off email or webhook using the production delivery path.

    Admin-only. Returns actionable JSON errors for disabled providers, missing
    credentials, invalid recipients, and provider rejections. Secrets are never
    returned.
    """
    channel = (payload.channel or "").strip().lower()
    settings = get_settings()

    def fail(code: str, message: str, status_code: int = 400):
        raise HTTPException(
            status_code=status_code,
            detail={"error": code, "message": message},
        )

    if channel == "email":
        recipient = (payload.recipient or settings.ALERT_EMAIL_TO or "").strip()
        if not settings.EMAIL_ENABLED:
            fail(
                "email_disabled",
                "Email delivery is disabled. Set EMAIL_ENABLED=true after configuring a provider.",
            )
        provider = (settings.EMAIL_PROVIDER or "").strip().lower()
        if provider == "resend":
            if not settings.RESEND_API_KEY:
                fail(
                    "missing_resend_api_key",
                    "RESEND_API_KEY is not configured on the server.",
                )
            if not is_valid_email(settings.ALERT_EMAIL_FROM):
                fail(
                    "missing_sender",
                    "ALERT_EMAIL_FROM is missing or is not a valid address.",
                )
        if not is_valid_email(recipient):
            fail(
                "invalid_recipient",
                "Provide a valid recipient email address in the request or ALERT_EMAIL_TO.",
            )

        try:
            result = await send_email_notification(
                recipient=recipient,
                subject="Logs Manager test notification",
                html_body="<p>This is a test notification from Logs Manager. "
                "Email delivery is configured correctly.</p>",
                text_body="This is a test notification from Logs Manager. "
                "Email delivery is configured correctly.",
            )
        except Exception as exc:  # noqa: BLE001 - report instead of crashing
            fail("provider_error", f"{type(exc).__name__}: {exc}", 502)

        if result.get("status") == "sent":
            return {
                "ok": True,
                "channel": "email",
                "status": "sent",
                "provider": provider or "smtp",
                "attempts": len(result.get("attempts") or []),
                "message_id": result.get("message_id"),
            }

        error = str(result.get("error") or "provider_error")
        if error in ("smtp_disabled_on_render", "smtp_disabled"):
            fail(
                error,
                "SMTP delivery is unavailable here. Configure EMAIL_PROVIDER=resend "
                "and a verified sender.",
            )
        if error == "invalid_recipient":
            fail("invalid_recipient", "The recipient address was rejected as invalid.")
        if error == "invalid_sender":
            fail("missing_sender", "ALERT_EMAIL_FROM is invalid.")
        if error == "missing_resend_api_key":
            fail("missing_resend_api_key", "RESEND_API_KEY is not configured on the server.")
        fail(
            "provider_rejected",
            f"The email provider rejected the test message: {error}",
            502,
        )

    if channel == "webhook":
        from urllib.parse import urlparse

        url = (payload.webhook_url or settings.ALERT_WEBHOOK_URL or "").strip()
        if not url:
            fail(
                "missing_webhook_url",
                "Provide webhook_url in the request or configure ALERT_WEBHOOK_URL.",
            )
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            fail("invalid_webhook_url", "webhook_url must be an absolute http(s) URL.")

        try:
            attempts = await send_webhook(
                webhook_url=url,
                payload={
                    "test": True,
                    "channel": "webhook",
                    "message": "Logs Manager test notification",
                    "notified_at": datetime.now(timezone.utc).isoformat(),
                },
                retries=1,
            )
        except Exception as exc:  # noqa: BLE001 - report instead of crashing
            fail("webhook_error", f"{type(exc).__name__}: {exc}", 502)

        last = attempts[-1] if attempts else {}
        if last.get("status") == "sent":
            return {
                "ok": True,
                "channel": "webhook",
                "status": "sent",
                "attempts": len(attempts),
                "http_code": last.get("http_code"),
            }
        fail(
            "webhook_delivery_failed",
            f"Webhook delivery failed: {last.get('error') or 'no response'}",
            502,
        )

    fail("invalid_channel", "channel must be 'email' or 'webhook'.")

@router.patch("/alerts/{alert_id}", response_model=dict)
async def update_alert_status(
    alert_id: str,
    update: AlertStatusUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: TokenPayload = Depends(require_admin),
):
    if update.status not in ["open", "resolved"]:
        raise HTTPException(status_code=400, detail="Invalid status")

    result = await session.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if not is_platform_admin(current_user) and tenant_key(alert.tenant) != tenant_key(current_user.tenant):
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.status = update.status
    await session.commit()

    return {"message": "Alert status updated", "alert": {"id": alert.id, "status": alert.status}}






VALID_CONDITION_TYPES = {
    "event_type",
    "severity_min",
    "field_value",
    "threshold_count",
    "repeated_failures",
}

_GROUP_BY_ALIASES = {
    "srcip": "src_ip",
    "src_ip": "src_ip",
    "user": "user_name",
    "username": "user_name",
    "user_name": "user_name",
    "host": "host",
    "hostname": "host",
}

_FIELD_ALIASES = {
    "action": "action",
    "eventtype": "event_type",
    "event_type": "event_type",
    "severity": "severity",
    "srcip": "src_ip",
    "src_ip": "src_ip",
    "dstip": "dst_ip",
    "dst_ip": "dst_ip",
    "user": "user_name",
    "username": "user_name",
    "user_name": "user_name",
    "host": "host",
    "hostname": "host",
    "process": "process",
    "status": "status",
}


def _coerce_int(value: Any, field_name: str, *, minimum: int = 1, maximum: Optional[int] = None) -> Optional[int]:
    """Coerce a form string/number into an int, rejecting bad values as 422."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise HTTPException(status_code=422, detail=f"{field_name} must be an integer.")
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail=f"{field_name} must be an integer.")
    if number < minimum:
        raise HTTPException(status_code=422, detail=f"{field_name} must be at least {minimum}.")
    if maximum is not None and number > maximum:
        raise HTTPException(status_code=422, detail=f"{field_name} must be at most {maximum}.")
    return number


def _canonical_group_by(value: Any) -> Optional[str]:
    if value is None or str(value).strip() == "":
        return None
    key = str(value).strip().lower()
    canonical = _GROUP_BY_ALIASES.get(key) or _GROUP_BY_ALIASES.get(key.replace("_", ""))
    if canonical is None:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid groupBy field: {value}. Use src_ip, user_name, or host.",
        )
    return canonical


def _canonical_rule_field(value: Any) -> Optional[str]:
    if value is None or str(value).strip() == "":
        return None
    key = str(value).strip().lower()
    return _FIELD_ALIASES.get(key) or _FIELD_ALIASES.get(key.replace("_", "")) or key


def _normalize_rule_conditions(conditions: Any) -> tuple[dict, str, Optional[int], Optional[int]]:
    """Validate one UI condition and return it plus derived rule settings.

    The browser sends ``threshold``/``windowSeconds`` as strings and uses
    ``groupBy`` values such as ``srcIp``. Older senders may also send a single
    condition object or a ``threshold_count`` condition. All of those normalize
    to the stored contract: camelCase condition fields plus canonical
    ``group_by`` (``src_ip``/``user_name``/``host``).
    """
    if isinstance(conditions, dict):
        conditions = [conditions]
    if not isinstance(conditions, list) or len(conditions) != 1:
        raise HTTPException(status_code=422, detail="Exactly one condition required")

    raw = conditions[0]
    if not isinstance(raw, dict):
        raise HTTPException(status_code=422, detail="Condition must be a JSON object")

    cond_type = str(raw.get("type") or "").strip()
    if cond_type not in VALID_CONDITION_TYPES:
        raise HTTPException(status_code=422, detail=f"Unknown condition type: {cond_type}")

    # Reject blank/null/whitespace condition values for condition types that
    # use one. ``repeated_failures``/``threshold_count`` derive their filter
    # from action/outcome and legitimately omit ``value``.
    raw_value = raw.get("value")
    if isinstance(raw_value, bool):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Condition value must not be a boolean.",
        )
    if cond_type in ("event_type", "severity_min", "field_value") and (
        raw_value is None or str(raw_value).strip() == ""
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Condition value must not be empty or whitespace",
        )

    threshold = _coerce_int(raw.get("threshold"), "threshold", minimum=1)
    window_seconds = _coerce_int(
        raw.get("windowSeconds", raw.get("window_seconds")),
        "windowSeconds",
        minimum=1,
        maximum=86400,
    )
    group_by = _canonical_group_by(raw.get("groupBy", raw.get("group_by")))
    field = _canonical_rule_field(raw.get("field"))
    value = raw.get("value")
    value = None if value is None or str(value).strip() == "" else str(value)

    condition: Dict[str, Any] = {"type": cond_type}
    if field:
        condition["field"] = field
    if value is not None:
        condition["value"] = value
    if threshold is not None:
        condition["threshold"] = threshold
    if window_seconds is not None:
        condition["windowSeconds"] = window_seconds
    if group_by is not None:
        condition["groupBy"] = group_by

    return condition, (group_by or "src_ip"), threshold, window_seconds


def _derive_rule_settings(
    condition: Dict[str, Any],
    *,
    group_by: str,
    threshold: Optional[int],
    window_seconds: Optional[int],
    filter_json: Optional[Dict[str, Any]] = None,
    rule_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the persisted top-level rule fields the evaluator reads."""
    cond_type = condition["type"]
    value = condition.get("value")
    derived_filter: Dict[str, Any] = dict(filter_json or {})

    if cond_type == "event_type" and value:
        derived_filter["event_type"] = value
    elif cond_type == "severity_min" and value:
        derived_filter["severity_gte"] = _coerce_int(value, "value", minimum=0, maximum=10)
    elif cond_type == "field_value" and value:
        field = condition.get("field")
        if field:
            derived_filter[field] = value
    elif cond_type in ("repeated_failures", "threshold_count"):
        if value:
            derived_filter["event_type"] = value
        else:
            derived_filter.setdefault("outcome", "failure")
            derived_filter.setdefault("action", "login")

    derived_type = rule_type or (
        "repeated_failures"
        if cond_type in ("repeated_failures", "threshold_count")
        else "threshold"
    )
    if derived_type not in ("threshold", "repeated_failures"):
        raise HTTPException(
            status_code=422,
            detail="rule_type must be 'threshold' or 'repeated_failures'.",
        )

    normalized_threshold = threshold if threshold is not None else 5
    window_minutes = max(1, int((window_seconds or 300) / 60))
    return {
        "rule_type": derived_type,
        "filter": derived_filter,
        "group_by": group_by,
        "threshold": normalized_threshold,
        "window_minutes": window_minutes,
    }


def _rule_payload(rule: AlertRule) -> Dict[str, Any]:
    return {
        "id": rule.id,
        "name": rule.name,
        "description": rule.description,
        "tenant": rule.tenant,
        "enabled": rule.enabled,
        "severity": rule.severity,
        "conditions": rule.conditions,
        "rule_type": rule.rule_type,
        "filter": rule.filter or {},
        "group_by": rule.group_by,
        "threshold": rule.threshold,
        "window_minutes": rule.window_minutes,
        "cooldown_minutes": rule.cooldown_minutes,
        "notify": rule.notify or {},
        "createdAt": rule.created_at.isoformat() if rule.created_at else None,
        "updatedAt": rule.updated_at.isoformat() if rule.updated_at else None,
    }


class AlertRuleCreate(BaseModel):
    name: str
    tenant: str
    description: Optional[str] = None
    conditions: Any
    enabled: bool = True
    severity: str = "medium"
    rule_type: Optional[str] = None
    filter: Optional[Dict[str, Any]] = None
    group_by: Optional[str] = None
    threshold: Optional[Any] = None
    window_minutes: Optional[Any] = None
    cooldown_minutes: Optional[Any] = None
    notify: Optional[Dict[str, Any]] = None


class AlertRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tenant: Optional[str] = None
    conditions: Optional[Any] = None
    enabled: Optional[bool] = None
    severity: Optional[str] = None
    rule_type: Optional[str] = None
    filter: Optional[Dict[str, Any]] = None
    group_by: Optional[str] = None
    threshold: Optional[Any] = None
    window_minutes: Optional[Any] = None
    cooldown_minutes: Optional[Any] = None
    notify: Optional[Dict[str, Any]] = None

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
    requested_tenant = (tenant or "").strip()
    effective_tenant = effective_read_tenant(current_user, requested_tenant)

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
            return {"rules": [], "hasNextPage": False, "newCursor": None}
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
    }


@router.put("/update-rule/{rule_id}", response_model=dict)
async def update_alert_rule(
    rule_id: str,
    rule: AlertRuleUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: TokenPayload = Depends(require_admin),
):
    result = await session.execute(
        select(AlertRule).where(AlertRule.id == rule_id)
    )
    existing = result.scalar_one_or_none()
    if not existing or not owns_tenant(current_user, existing.tenant):
        raise HTTPException(status_code=404, detail="Rule not found")

    # Reject tenant changes (H-11).
    update_tenant = getattr(rule, "tenant", None)
    if update_tenant is not None and update_tenant.strip() != existing.tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot change rule tenant",
        )

    # ---- H-2/H-6/H-11: Explicit validation layer ----
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
        # Check for duplicate name within tenant scope (H-11).
        result = await session.execute(
            select(AlertRule).where(
                AlertRule.name == stripped_name,
                AlertRule.tenant == existing.tenant,
                AlertRule.id != rule_id,
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Rule with name '{stripped_name}' already exists in tenant '{existing.tenant}'",
            )
        existing.name = stripped_name

    if rule.description is not None:
        existing.description = rule.description

    # Validate severity if provided (H-11).
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

    # Validate rule type if provided (H-6).
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

    # Validate numeric ranges if provided (H-2).
    if rule.cooldown_minutes not in (None, ""):
        existing.cooldown_minutes = validate_cooldown_range(
            _coerce_int(rule.cooldown_minutes, "cooldown_minutes", minimum=0)
        )
    if rule.threshold not in (None, ""):
        existing.threshold = validate_threshold_range(
            _coerce_int(rule.threshold, "threshold", minimum=1)
        )
    if rule.window_minutes not in (None, ""):
        existing.window_minutes = validate_window_minutes_range(
            _coerce_int(rule.window_minutes, "window_minutes", minimum=1)
        )

    # Validate filter dict if provided (H-2).
    if rule.filter is not None:
        rule.filter = validate_filter_dict(rule.filter)

    if rule.enabled is not None:
        existing.enabled = rule.enabled
    if rule.notify is not None:
        existing.notify = rule.notify

    explicit_group_by = _canonical_group_by(rule.group_by) if rule.group_by else None
    explicit_threshold = (
        _coerce_int(rule.threshold, "threshold", minimum=1)
        if rule.threshold not in (None, "")
        else None
    )

    if rule.conditions is not None:
        # Validate conditions are present and not blank (H-2).
        if not rule.conditions or len(rule.conditions) != 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Exactly one condition is required",
            )
        condition, group_by, threshold, window_seconds = _normalize_rule_conditions(
            rule.conditions
        )
        settings = _derive_rule_settings(
            condition,
            group_by=explicit_group_by or group_by,
            threshold=explicit_threshold or threshold,
            window_seconds=window_seconds,
            filter_json=rule.filter,
            rule_type=rule.rule_type,
        )
        # Validate the built filter dict (H-2).
        settings["filter"] = validate_filter_dict(settings["filter"])
        if rule.window_minutes not in (None, ""):
            settings["window_minutes"] = _coerce_int(
                rule.window_minutes, "window_minutes", minimum=1
            )
        existing.conditions = [condition]
        existing.rule_type = settings["rule_type"]
        existing.filter = settings["filter"]
        existing.group_by = settings["group_by"]
        existing.threshold = settings["threshold"]
        existing.window_minutes = settings["window_minutes"]
    else:
        # Metadata-only edits keep the existing condition but allow
        # explicit top-level overrides.
        if rule.filter is not None:
            existing.filter = rule.filter
        if rule.rule_type is not None:
            existing.rule_type = rule.rule_type
        if explicit_group_by is not None:
            existing.group_by = explicit_group_by
        if explicit_threshold is not None:
            existing.threshold = explicit_threshold
        if rule.window_minutes not in (None, ""):
            existing.window_minutes = _coerce_int(
                rule.window_minutes, "window_minutes", minimum=1
            )

    await session.commit()
    await session.refresh(existing)

    return {"message": "Alert rule updated", "rule": _rule_payload(existing)}

@router.patch("/rules/{rule_id}/enabled", response_model=dict)
async def toggle_rule_enabled(
    rule_id: str,
    enabled: bool,
    session: AsyncSession = Depends(get_session),
    current_user: TokenPayload = Depends(require_admin),
):
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
    result = await session.execute(
        select(AlertRule).where(AlertRule.id == rule_id)
    )
    rule = result.scalar_one_or_none()
    if not rule or not owns_tenant(current_user, rule.tenant):
        raise HTTPException(status_code=404, detail="Rule not found")


    alert_count = await session.execute(
        select(func.count()).select_from(Alert).where(Alert.rule_id == rule_id)
    )
    if alert_count.scalar() > 0:
        raise HTTPException(status_code=409, detail="Cannot delete rule with existing alerts")

    await session.delete(rule)
    await session.commit()

    return {"message": "Alert rule deleted"}


@router.post("/rules/{rule_id}/test", response_model=dict)
async def test_alert_rule(
    rule_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: TokenPayload = Depends(require_admin),
):
    result = await session.execute(
        select(AlertRule).where(AlertRule.id == rule_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    if not owns_tenant(current_user, rule.tenant):
        raise HTTPException(status_code=403, detail="Cannot test rule for different tenant")

    from app.services.alerting.evaluator import evaluate_rule
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    try:
        triggered = await evaluate_rule(session, rule, now)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Rule evaluation failed: {exc}")

    return {
        "rule_id": rule.id,
        "rule_name": rule.name,
        "tenant": rule.tenant,
        "evaluated_at": now.isoformat(),
        "would_trigger": len(triggered) > 0,
        "matches": triggered,
    }






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
    role: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    date: Optional[str] = None,
    limit: int = 25,
    cursor: Optional[int] = None,
    session: AsyncSession = Depends(get_session),
    current_user: TokenPayload = Depends(require_admin),
):
    requested_tenant = (tenant or "").strip()
    effective_tenant = effective_read_tenant(current_user, requested_tenant)

    query = select(User)
    if effective_tenant:
        query = query.where(User.tenant == effective_tenant)

    if role and role.strip():
        role_value = role.strip().upper()
        if role_value not in ("ADMIN", "VIEWER"):
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported role '{role}'. Use ADMIN or VIEWER.",
            )
        query = query.where(User.role == role_value)

    if status_filter and status_filter.strip():
        status_value = status_filter.strip().upper()
        if status_value not in ("ACTIVE", "INACTIVE", "FREEZE"):
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Unsupported status '{status_filter}'. "
                    "Use ACTIVE, INACTIVE, or FREEZE."
                ),
            )
        query = query.where(User.status == status_value)

    if date and date.strip():
        start = _parse_date_filter(date, "date")
        query = query.where(User.create_at >= start)
        query = query.where(User.create_at < start + timedelta(days=1))

    if search:
        search_term = f"%{search}%"
        query = query.where(
            (User.username.ilike(f"%{search}%")) |
            (User.email.ilike(f"%{search}%"))
        )

    query = query.order_by(desc(User.id)).limit(limit + 1)
    if cursor:
        # Rows are ordered newest-first, so the next page contains smaller ids.
        query = query.where(User.id < cursor)

    result = await session.execute(query)
    users = result.scalars().all()

    has_next = len(users) > limit
    if has_next:
        users = users[:limit]

    next_cursor = users[-1].id if has_next else None

    users_payload = [{
        "id": u.id,
        "username": u.username,
        "email": u.email,
        "role": u.role,
        "tenant": u.tenant,
        "status": u.status,
        "createAt": u.create_at.isoformat() if u.create_at else None,
        "updatedAt": u.updated_at.isoformat() if u.updated_at else None,
    } for u in users]

    return {
        "usersList": users_payload,


        "users": users_payload,
        "newCursor": next_cursor,
    }

async def _read_user_request_payload(request: Request) -> Dict[str, Any]:
    """Read a user payload from JSON (documented) or form data (legacy clients)."""

    content_type = (
        (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    )
    if content_type == "application/json":
        try:
            payload = await request.json()
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            raise HTTPException(status_code=400, detail="Invalid JSON body.")
        if not isinstance(payload, dict):
            raise HTTPException(
                status_code=400, detail="Request body must be a JSON object."
            )
        return payload

    try:
        form = await request.form()
    except Exception as exc:  # pragma: no cover - malformed multipart bodies
        raise HTTPException(status_code=400, detail="Invalid form body.") from exc
    return {key: value for key, value in form.items()}


@router.post("/create-user", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_user: TokenPayload = Depends(require_admin),
):
    payload = await _read_user_request_payload(request)

    username = str(payload.get("username") or "").strip()
    email = str(payload.get("email") or "").strip()
    raw_tenant = payload.get("tenant")
    raw_password = payload.get("password")

    required = {
        "username": username,
        "email": email,
        "tenant": raw_tenant,
        "password": raw_password,
    }
    missing = [
        name
        for name, value in required.items()
        if value is None or str(value).strip() == ""
    ]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Missing required fields: {', '.join(missing)}",
        )

    target_tenant = normalize_tenant(str(raw_tenant))
    if not is_platform_admin(current_user) and target_tenant != tenant_key(current_user.tenant):
        raise HTTPException(status_code=403, detail="Cannot create user for different tenant")

    await _require_active_tenant(session, target_tenant)

    role_value = _validated_role(payload.get("role") or "VIEWER")
    status_value = _validated_status(payload.get("status") or "ACTIVE")

    from app.core.security import hash_password

    existing = await session.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    hashed = hash_password(str(raw_password))
    user = User(
        username=username,
        email=email,
        tenant=target_tenant,
        role=role_value,
        status=status_value,
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
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_user: TokenPayload = Depends(require_admin),
):
    payload = await _read_user_request_payload(request)

    raw_id = payload.get("id")
    if raw_id is None or str(raw_id).strip() == "":
        raise HTTPException(status_code=422, detail="id is required")
    try:
        user_id = int(str(raw_id))
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="id must be an integer")

    username = payload.get("username")
    email = payload.get("email")
    tenant = payload.get("tenant")
    role = payload.get("role")
    status = payload.get("status")

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not owns_tenant(current_user, user.tenant):
        raise HTTPException(status_code=404, detail="User not found")

    is_self = user.id == current_user.user_id
    current_tenant = tenant_key(user.tenant)
    target_tenant: Optional[str] = None

    if tenant is not None:
        requested_tenant = tenant_key(str(tenant))
        if is_self and requested_tenant != current_tenant:
            raise HTTPException(status_code=403, detail="Cannot change your own tenant")
        if not is_platform_admin(current_user) and requested_tenant != current_tenant:
            raise HTTPException(
                status_code=403,
                detail="Tenant-bound administrators cannot change a user's tenant",
            )
        if requested_tenant != current_tenant:
            target_tenant = normalize_tenant(str(tenant))
            await _require_active_tenant(session, target_tenant)
        elif current_tenant:
            # Keep the canonical value when the caller re-sends the same tenant.
            target_tenant = normalize_tenant(str(tenant))

    role_value = _validated_role(str(role)) if role is not None else None
    status_value = _validated_status(str(status)) if status is not None else None

    if is_self:
        if role_value is not None and role_value != "ADMIN":
            raise HTTPException(status_code=403, detail="Cannot change your own role from ADMIN")
        if status_value is not None and status_value != "ACTIVE":
            raise HTTPException(status_code=403, detail="Cannot deactivate yourself")

    if role_value is not None and user.role == "ADMIN" and role_value != "ADMIN":
        admin_count = await session.execute(select(func.count()).select_from(User).where(User.role == "ADMIN", User.status == "ACTIVE"))
        if admin_count.scalar() <= 1:
            raise HTTPException(status_code=403, detail="Cannot demote the last active admin")
    if status_value is not None and user.role == "ADMIN" and user.status == "ACTIVE" and status_value != "ACTIVE":
        admin_count = await session.execute(select(func.count()).select_from(User).where(User.role == "ADMIN", User.status == "ACTIVE"))
        if admin_count.scalar() <= 1:
            raise HTTPException(status_code=403, detail="Cannot deactivate the last active admin")

    if username is not None:
        user.username = str(username).strip()
    if email is not None:
        user.email = str(email).strip()
    if target_tenant is not None:
        user.tenant = target_tenant
    if role_value is not None:
        user.role = role_value
    if status_value is not None:
        user.status = status_value

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
    user_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: TokenPayload = Depends(require_admin),
):
    query = select(User)
    if user_id.isdigit():
        query = query.where(User.id == int(user_id))
    else:
        query = query.where(User.email == user_id)
    result = await session.execute(query)
    user = result.scalar_one_or_none()
    if not user or not owns_tenant(current_user, user.tenant):
        raise HTTPException(status_code=404, detail="User not found")


    if user.id == current_user.user_id:
        raise HTTPException(status_code=403, detail="Cannot delete yourself")


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
    requested = (tenant or "").strip()
    effective_tenant = effective_read_tenant(current_user, requested)

    def tenant_filter(model):
        return [model.tenant == effective_tenant] if effective_tenant else []

    total_events = await session.execute(
        select(func.count()).select_from(Event).where(*tenant_filter(Event))
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
            select(Event.tenant, func.count()).group_by(Event.tenant)
        )

        result["data"]["tenants"] = [{"tenant": row[0]} for row in by_tenant if row[0]]
    return result






class TenantCreateRequest(BaseModel):
    name: str
    is_active: bool = True


class TenantCreateResponse(BaseModel):
    id: str
    name: str
    api_key: str
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
    require_platform_admin(current_user)
    from app.models.enums import Role


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


    existing = await session.execute(select(Tenant).where(Tenant.name == name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Tenant '{name}' already exists")


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
        api_key=api_key,
        is_active=tenant.is_active,
        created_at=tenant.created_at.isoformat() if tenant.created_at else "",
    )


@router.get("/tenants", response_model=List[TenantResponse])
async def list_tenants(
    session: AsyncSession = Depends(get_session),
    current_user: TokenPayload = Depends(require_admin),
):
    require_platform_admin(current_user)
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
    require_platform_admin(current_user)
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
    require_platform_admin(current_user)
    result = await session.execute(select(Tenant).where(Tenant.name == name))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant '{name}' not found")


    new_api_key = secrets.token_urlsafe(32)
    new_key_hash = hashlib.sha256(new_api_key.encode()).hexdigest()

    tenant.api_key_hash = new_key_hash
    await session.commit()
    await session.refresh(tenant)

    return TenantCreateResponse(
        id=tenant.id,
        name=tenant.name,
        api_key=new_api_key,
        is_active=tenant.is_active,
        created_at=tenant.created_at.isoformat() if tenant.created_at else "",
    )
