from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, asc, or_
from sqlalchemy.orm import selectinload
from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone
from app.core.config import get_settings
from app.core.database import get_session
from app.core.dependencies import get_current_user, get_effective_tenant, verify_api_key, require_admin
from app.core.exceptions import ValidationError
from app.core.security import TokenPayload
from app.models.events import Event
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
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Any
import json
import secrets
import hashlib
import uuid

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


def _is_meaningless_event(event_data: dict) -> bool:
    data_keys = {k.lower() for k in event_data.keys()}

    data_keys -= {"source", "tenant", "@timestamp", "timestamp", "tags", "raw"}
    return not bool(data_keys & _MEANINGFUL_FIELDS)


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


def as_validation_http_error(exc: ValidationError) -> HTTPException:
    return HTTPException(status_code=400, detail=exc.message)


def owns_tenant(current_user: TokenPayload, tenant: Optional[str]) -> bool:
    if current_user.role == "ADMIN":
        return True
    return (current_user.tenant or "") == (tenant or "")






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
@public_router.post("/ingest", response_model=IngestResponse)
async def ingest_single_event(
    request: Request,
    session: AsyncSession = Depends(get_session),
    api_user: TokenPayload = Depends(verify_api_key),
):

    body = await request.body()
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
async def ingest_batch_events(
    request: IngestBatchRequest,
    session: AsyncSession = Depends(get_session),
    api_user: TokenPayload = Depends(verify_api_key),
):
    tenant = resolve_tenant(api_user, request.tenant)
    if len(request.events) > settings.INGEST_BATCH_MAX_EVENTS:
        raise HTTPException(
            status_code=413,
            detail=f"Batch exceeds the limit of {settings.INGEST_BATCH_MAX_EVENTS} events.",
        )
    if not request.events:
        raise HTTPException(status_code=400, detail="Batch must contain at least one event.")


    for idx, event in enumerate(request.events):
        if not isinstance(event, dict):
            raise HTTPException(
                status_code=400,
                detail=f"Batch event at index {idx} must be a JSON object.",
            )
        ts_value = event.get("@timestamp") or event.get("timestamp")
        _validate_timestamp(ts_value, f"events[{idx}].@timestamp")

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
@public_router.post("/ingest/file", response_model=IngestResponse)
async def ingest_file(
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
    """Read the request body, rejecting anything over ``max_bytes``."""
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > max_bytes:
                raise HTTPException(
                    status_code=413,
                    detail=f"Syslog body exceeds the {max_bytes} byte limit.",
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
                detail=f"Syslog body exceeds the {max_bytes} byte limit.",
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

    accepted = 0
    rejected = 0
    errors: List[dict] = []
    service = IngestionService(session)

    for index, line in enumerate(lines):
        if not isinstance(line, str):
            rejected += 1
            errors.append({"line": index, "error": "line must be a string"})
            continue
        if not line.strip():
            continue

        parsed = parse_syslog_message(line)
        if not parsed:
            rejected += 1
            errors.append({"line": index, "error": "unable to parse syslog line"})
            continue

        event = dict(parsed)
        tags = list(event.get("tags") or [])
        if "transport=http-syslog" not in tags:
            tags.append("transport=http-syslog")
        event["tags"] = tags
        event["remoteAddress"] = remote_address
        event["remotePort"] = remote_port

        source = event.get("source") or current_settings.SYSLOG_SOURCE
        try:
            await service.ingest(event, source, context)
            accepted += 1
        except ValidationError as exc:
            await session.rollback()
            rejected += 1
            errors.append({"line": index, "error": exc.message})
        except Exception as exc:  # noqa: BLE001 - one bad line must not abort the batch
            await session.rollback()
            rejected += 1
            errors.append({"line": index, "error": f"{type(exc).__name__}: {exc}"})

    return SyslogIngestResponse(accepted=accepted, rejected=rejected, errors=errors)


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

    alert.status = update.status
    await session.commit()

    return {"message": "Alert status updated", "alert": {"id": alert.id, "status": alert.status}}






class AlertRuleCreate(BaseModel):
    name: str
    tenant: str
    description: Optional[str] = None
    conditions: List[dict]
    enabled: bool = True
    severity: str = "medium"

    @field_validator("conditions")
    @classmethod
    def validate_conditions(cls, v: List[dict]) -> List[dict]:
        if not v or len(v) != 1:
            raise ValueError("Exactly one condition required")

        condition = v[0]
        cond_type = condition.get("type")
        valid_types = ["event_type", "severity_min", "field_value", "threshold_count", "repeated_failures"]
        if cond_type not in valid_types:
            raise ValueError(f"Unknown condition type: {cond_type}")


        threshold = condition.get("threshold")
        if threshold is not None and threshold < 1:
            raise ValueError("threshold must be at least 1")


        window = condition.get("windowSeconds")
        if window is not None:
            if window < 1:
                raise ValueError("windowSeconds must be at least 1")
            if window > 86400:
                raise ValueError("windowSeconds must be at most 86400")


        group_by = condition.get("groupBy")
        if group_by is not None and group_by not in ("src_ip", "user", "host"):
            raise ValueError(f"Invalid groupBy field: {group_by}")

        return v


class AlertRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    conditions: Optional[List[dict]] = None
    enabled: Optional[bool] = None
    severity: Optional[str] = None

    @field_validator("conditions", mode="before")
    @classmethod
    def validate_conditions(cls, v: Optional[List[dict]]) -> Optional[List[dict]]:
        if v is not None:
            if not v or len(v) != 1:
                raise ValueError("Exactly one condition required")

            condition = v[0]
            cond_type = condition.get("type")
            valid_types = ["event_type", "severity_min", "field_value", "threshold_count", "repeated_failures"]
            if cond_type not in valid_types:
                raise ValueError(f"Unknown condition type: {cond_type}")

            threshold = condition.get("threshold")
            if threshold is not None and threshold < 1:
                raise ValueError("threshold must be at least 1")

            window = condition.get("windowSeconds")
            if window is not None:
                if window < 1:
                    raise ValueError("windowSeconds must be at least 1")
                if window > 86400:
                    raise ValueError("windowSeconds must be at most 86400")

            group_by = condition.get("groupBy")
            if group_by is not None and group_by not in ("src_ip", "user", "host"):
                raise ValueError(f"Invalid groupBy field: {group_by}")

        return v

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
    if not owns_tenant(current_user, rule.tenant):
        raise HTTPException(status_code=403, detail="Cannot create rule for different tenant")

    new_rule = AlertRule(
        id=uuid.uuid4().hex[:25],
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
    result = await session.execute(
        select(AlertRule).where(AlertRule.id == rule_id)
    )
    existing = result.scalar_one_or_none()
    if not existing or not owns_tenant(current_user, existing.tenant):
        raise HTTPException(status_code=404, detail="Rule not found")


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
    limit: int = 25,
    cursor: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    current_user: TokenPayload = Depends(require_admin),
):
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

    query = query.order_by(desc(User.id)).limit(limit + 1)
    if cursor:
        query = query.where(User.id > cursor)

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
    result = await session.execute(select(User).where(User.id == id))
    user = result.scalar_one_or_none()
    if not user or not owns_tenant(current_user, user.tenant):
        raise HTTPException(status_code=404, detail="User not found")


    if user.id == current_user.user_id:
        if role is not None and role != "ADMIN":
            raise HTTPException(status_code=403, detail="Cannot change your own role from ADMIN")
        if status is not None and status != "ACTIVE":
            raise HTTPException(status_code=403, detail="Cannot deactivate yourself")


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
    if current_user.role != "ADMIN":
        requested = current_user.tenant or ""
    effective_tenant = None if requested in ("", "all") else requested

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
