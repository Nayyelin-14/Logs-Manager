"""
Exact-path aliases for assignment compliance.

The assignment requires POST /ingest (exact path). The main API router uses
prefix="/api" so routes are /api/ingest etc. This router exposes the same
handlers at the exact paths /ingest, /ingest/batch, /ingest/file without any
prefix. Included in main.py with no prefix.
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from app.core.database import get_session
from app.core.dependencies import verify_api_key, get_current_user
from app.services.ingest_service import IngestionService
from app.core.exceptions import ValidationError
from pydantic import BaseModel, ConfigDict
from app.api.routes.ingest import (
    IngestEventRequest,
    IngestBatchRequest,
    IngestResponse,
    resolve_tenant,
    as_validation_http_error,
    owns_tenant,
)

alias_router = APIRouter()


@alias_router.post("/ingest", response_model=IngestResponse)
async def ingest_single_event_exact(
    request: IngestEventRequest,
    session: AsyncSession = Depends(get_session),
    api_user=Depends(verify_api_key),
):
    """Exact-path alias: POST /ingest (single event)."""
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


@alias_router.post("/ingest/batch", response_model=IngestResponse)
async def ingest_batch_events_exact(
    request: IngestBatchRequest,
    session: AsyncSession = Depends(get_session),
    api_user=Depends(verify_api_key),
):
    """Exact-path alias: POST /ingest/batch."""
    tenant = resolve_tenant(api_user, request.tenant)
    if len(request.events) > 1000:
        raise HTTPException(status_code=413, detail="Batch exceeds the limit of 1000 events.")
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


@alias_router.post("/ingest/file", response_model=IngestResponse)
async def ingest_file_exact(
    file: UploadFile = File(...),
    source: Optional[str] = Form(None),
    tenant: Optional[str] = Form(None),
    session: AsyncSession = Depends(get_session),
    api_user=Depends(verify_api_key),
):
    """Exact-path alias: POST /ingest/file (multipart upload)."""
    effective_tenant = resolve_tenant(api_user, tenant)
    content = await file.read(10_485_760 + 1)
    if len(content) > 10_485_760:
        raise HTTPException(status_code=413, detail="File exceeds the 10485760 byte upload limit.")
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
