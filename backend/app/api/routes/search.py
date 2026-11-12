from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func, desc, asc, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Set
from pydantic import BaseModel, Field, ConfigDict
import base64
import binascii
import json

from app.core.database import get_session
from app.core.dependencies import get_current_user, get_effective_tenant
from app.core.security import TokenPayload
from app.core.tenancy import is_platform_admin, resolve_read_tenant, tenant_key
from app.models.events import Event
from app.models.enums import Source

router = APIRouter()

VALID_SOURCES: Set[str] = {source.value for source in Source}
VALID_SEVERITIES = {"low", "medium", "high", "critical"}
SORTABLE_FIELDS = {
    "ts",
    "severity",
    "event_type",
    "source",
    "user_name",
    "src_ip",
    "dst_ip",
    "ingested_at",
}

# Opaque cursors are base64url(JSON). The version and the sort metadata let us
# reject a cursor that is reused with a different sort instead of silently
# returning the wrong page.
CURSOR_VERSION = 1


def _encode_cursor(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str) -> dict:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        raw = base64.b64decode(padded.encode("ascii"), altchars=b"-_", validate=True)
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError, binascii.Error, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="Invalid cursor")
    if not isinstance(payload, dict) or payload.get("v") != CURSOR_VERSION:
        raise HTTPException(status_code=400, detail="Invalid cursor")
    return payload


def _cursor_timestamp(value) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(status_code=400, detail="Invalid cursor")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid cursor")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _effective_tenant(current_user: "TokenPayload", requested: Optional[str]) -> Optional[str]:
    """Resolve a read filter, respecting tenant-bound administrators.

    ``None`` means all tenants and is only possible for platform admins. A
    non-platform account with no tenant receives 403 instead of an unscoped
    query.
    """
    return resolve_read_tenant(current_user, requested)


def _event_payload(log: Event) -> dict:
    return {
        "id": log.id,
        "timestamp": _iso_utc(log.ts),
        "eventType": log.event_type,
        "user": log.user_name,
        "srcIp": log.src_ip,
        "dstIp": log.dst_ip,
        "description": log.raw.get("description") if isinstance(log.raw, dict) else None,
        "severity": log.severity,
        "severityLevel": _severity_level(log.severity),
        "tenant": log.tenant,
        "action": log.action if isinstance(log.action, str) else (log.action.value if log.action else None),
        "source": log.source if isinstance(log.source, str) else (log.source.value if log.source else None),
        "host": log.host,
        "process": log.process,
        "protocol": log.protocol,
        "statusCode": log.status_code,
        "priority": log.raw.get("priority") if isinstance(log.raw, dict) else None,
        "sha256": log.raw.get("sha256") if isinstance(log.raw, dict) else None,
        "raw": log.raw,
        "createdAt": _iso_utc(log.ingested_at),
    }


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


def _parse_datetime(value: Optional[str], *, end_of_day: bool = False) -> Optional[datetime]:
    """Parse an ISO-8601 value or a plain ``YYYY-MM-DD`` date as UTC.

    Date-only values are interpreted as the whole UTC day: ``start`` maps to
    00:00:00Z and ``end`` (``end_of_day=True``) maps to the next day, so a
    range like ``from=2026-11-09&to=2026-11-09`` includes all of that day.
    """
    if value is None or not str(value).strip():
        return None
    raw = str(value).strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid date/time '{value}'. Use ISO-8601 (e.g. 2026-11-09 or 2026-11-09T00:00:00Z).",
        )
    date_only = len(raw) == 10 and raw[4] == "-" and raw[7] == "-"
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)
    if date_only and end_of_day:
        return parsed + timedelta(days=1)
    return parsed


class LogFilters(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

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
    from_time: Optional[str] = Field(None, alias="from")
    to_time: Optional[str] = Field(None, alias="to")
    search: Optional[str] = None
    q: Optional[str] = None
    limit: int = 50
    cursor: Optional[str] = None
    sort_by: str = "ts"
    sort_order: str = "desc"


class PaginatedLogsResponse(BaseModel):
    logs: List[dict]
    next_cursor: Optional[str] = None
    total: int


@router.get("/get-logs", response_model=dict)
@router.get("/events", response_model=dict)
async def search_logs(
    filters: LogFilters = Depends(),
    from_: Optional[str] = Query(
        None,
        alias="from",
        description="Inclusive start of the time window (ISO-8601).",
    ),
    session: AsyncSession = Depends(get_session),
    current_user: "TokenPayload" = Depends(get_current_user),
):
    requested_tenant = (filters.tenant or "").strip()
    tenant = _effective_tenant(current_user, requested_tenant)

    # Every filter is collected once so the page query and the COUNT query use
    # exactly the same WHERE clauses (including the server-side tenant scope).
    conditions = []
    if tenant:
        conditions.append(Event.tenant == tenant)

    if filters.source and str(filters.source).strip():
        source = str(filters.source).strip().lower()
        if source not in VALID_SOURCES:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Unsupported source '{filters.source}'. "
                    f"Valid sources: {', '.join(sorted(VALID_SOURCES))}."
                ),
            )
        conditions.append(Event.source == source)

    event_type = filters.event_type or filters.eventType
    if event_type and str(event_type).strip():
        conditions.append(func.lower(Event.event_type) == str(event_type).strip().lower())

    if filters.severity and str(filters.severity).strip():
        sev = str(filters.severity).strip().lower()
        ranges = {"low": (0, 3), "medium": (4, 6), "high": (7, 8), "critical": (9, 10)}
        if sev in ranges:
            low, high = ranges[sev]
            conditions.append(Event.severity.between(low, high))
        elif sev.isdigit():
            conditions.append(Event.severity >= int(sev))
        else:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Unsupported severity '{filters.severity}'. "
                    "Use low, medium, high, critical, or a number 0-10."
                ),
            )

    # A single calendar day remains the primary UI filter.
    day = _parse_datetime(filters.date)
    if day is not None:
        conditions.append(Event.ts >= day)
        conditions.append(Event.ts < day + timedelta(days=1))

    # Accept both the explicit start/end pair and the concise from/to aliases.
    start = (
        _parse_datetime(filters.start_time)
        or _parse_datetime(from_)
        or _parse_datetime(filters.from_time)
    )
    end = _parse_datetime(filters.end_time) or _parse_datetime(filters.to_time, end_of_day=True)
    if start is not None:
        conditions.append(Event.ts >= start)
    if end is not None:
        conditions.append(Event.ts <= end)

    if filters.action and str(filters.action).strip():
        conditions.append(Event.action == str(filters.action).strip().lower())
    if filters.user:
        conditions.append(Event.user_name.ilike(f"%{filters.user}%"))
    if filters.src_ip:
        conditions.append(Event.src_ip == filters.src_ip)
    if filters.dst_ip:
        conditions.append(Event.dst_ip == filters.dst_ip)

    search_value = filters.search or filters.q
    if search_value and str(search_value).strip():
        search_term = f"%{str(search_value).strip()}%"
        conditions.append(
            or_(
                Event.user_name.ilike(search_term),
                Event.src_ip.ilike(search_term),
                Event.dst_ip.ilike(search_term),
                Event.event_type.ilike(search_term),
                Event.host.ilike(search_term),
                Event.process.ilike(search_term),
                Event.rule_name.ilike(search_term),
            )
        )

    sort_by = filters.sort_by if filters.sort_by in SORTABLE_FIELDS else "ts"
    sort_column = getattr(Event, sort_by, Event.ts)
    sort_order = "asc" if (filters.sort_order or "").lower() == "asc" else "desc"

    # `total` is the real number of matching rows under the same filters, not
    # the current page length. The COUNT query reuses `conditions`, so the
    # tenant predicate is enforced server-side for viewers too.
    total = await session.scalar(
        select(func.count()).select_from(Event).where(*conditions)
    ) or 0

    query = select(Event).where(*conditions)

    cursor_payload = _decode_cursor(filters.cursor) if filters.cursor else None

    # Cursor design: the default `ts` sort uses keyset paging on the tuple
    # (ts, id) -- (ts, id) < (cursor_ts, cursor_id) for DESC and the inverse for
    # ASC. Both columns are part of the primary key and non-null, so there are
    # no NULL branches. Other allowlisted sort fields fall back to offset
    # paging encoded in the same opaque cursor, with id as a deterministic
    # tie-breaker (NULLs follow PostgreSQL's default ordering).
    if sort_by == "ts":
        if sort_order == "asc":
            query = query.order_by(asc(Event.ts), asc(Event.id))
        else:
            query = query.order_by(desc(Event.ts), desc(Event.id))

        if cursor_payload is not None:
            if (
                cursor_payload.get("mode") != "ts"
                or cursor_payload.get("sort") != "ts"
                or cursor_payload.get("order") != sort_order
            ):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid cursor: it does not match the requested sort",
                )
            cursor_ts = _cursor_timestamp(cursor_payload.get("ts"))
            cursor_id = cursor_payload.get("id")
            if not isinstance(cursor_id, str) or not cursor_id:
                raise HTTPException(status_code=400, detail="Invalid cursor")
            if sort_order == "asc":
                query = query.where(
                    or_(
                        Event.ts > cursor_ts,
                        and_(Event.ts == cursor_ts, Event.id > cursor_id),
                    )
                )
            else:
                query = query.where(
                    or_(
                        Event.ts < cursor_ts,
                        and_(Event.ts == cursor_ts, Event.id < cursor_id),
                    )
                )
    else:
        offset = 0
        if cursor_payload is not None:
            if (
                cursor_payload.get("mode") != "offset"
                or cursor_payload.get("sort") != sort_by
                or cursor_payload.get("order") != sort_order
            ):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid cursor: it does not match the requested sort",
                )
            offset = cursor_payload.get("offset")
            if not isinstance(offset, int) or offset < 0:
                raise HTTPException(status_code=400, detail="Invalid cursor")

        order_expr = asc(sort_column) if sort_order == "asc" else desc(sort_column)
        id_expr = asc(Event.id) if sort_order == "asc" else desc(Event.id)
        query = query.order_by(order_expr, id_expr).offset(offset)

    limit = max(1, min(int(filters.limit or 50), 500))
    query = query.limit(limit + 1)
    result = await session.execute(query)
    logs = result.scalars().all()

    has_next = len(logs) > limit
    if has_next:
        logs = logs[:limit]

    next_cursor = None
    if has_next and logs:
        last = logs[-1]
        if sort_by == "ts":
            next_cursor = _encode_cursor({
                "v": CURSOR_VERSION,
                "mode": "ts",
                "sort": "ts",
                "order": sort_order,
                "ts": last.ts.isoformat(),
                "id": last.id,
            })
        else:
            next_cursor = _encode_cursor({
                "v": CURSOR_VERSION,
                "mode": "offset",
                "sort": sort_by,
                "order": sort_order,
                "offset": offset + limit,
            })

    log_dicts = [_event_payload(log) for log in logs]

    return {
        "logs": log_dicts,
        "newCursor": next_cursor,
        "prevCursor": None,
        "total": total,
        # Additive aliases; existing clients keep using newCursor/prevCursor.
        "next_cursor": next_cursor,
        "has_more": has_next,
    }


@router.get("/events/{event_id}", response_model=dict)
async def get_event(
    event_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: "TokenPayload" = Depends(get_current_user),
):
    """Return one event, scoped to the caller's tenant.

    A tenant mismatch returns 404 rather than 403 so the endpoint does not
    reveal whether another tenant's event exists.
    """
    tenant = _effective_tenant(current_user, None)
    query = select(Event).where(Event.id == event_id)
    if tenant:
        query = query.where(Event.tenant == tenant)

    result = await session.execute(query)
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="Event not found")

    return _event_payload(log)


@router.delete("/delete-log/{log_id}", response_model=dict)
async def delete_log(
    log_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: "TokenPayload" = Depends(get_current_user),
):
    from app.core.dependencies import require_admin
    await require_admin(current_user)

    from app.models.events import Event as EventModel

    result = await session.execute(
        select(EventModel).where(EventModel.id == log_id)
    )
    log = result.scalar_one_or_none()
    if not log:
        return {"success": False, "message": "Log not found"}
    if not is_platform_admin(current_user) and tenant_key(log.tenant) != tenant_key(current_user.tenant):
        return {"success": False, "message": "Log not found"}

    log_data = {
        "id": str(log.id),
        "source": log.source if isinstance(log.source, str) else log.source.value,
        "tenant": log.tenant,
        "event_type": log.event_type,
        "severity": log.severity,
        "raw": log.raw,
    }

    await session.delete(log)
    await session.commit()

    return {"success": True, "message": "Log deleted", "deleted_log": log_data}
