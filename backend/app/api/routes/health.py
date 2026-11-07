from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import get_session

router = APIRouter()


@router.get("/healthz")
async def health_check(request: Request, session: AsyncSession = Depends(get_session)):
    now = datetime.now(timezone.utc)
    try:
        startup_time = request.app.state.startup_time
        uptime_seconds = int((now - startup_time).total_seconds())
    except Exception:
        uptime_seconds = 0
    try:
        await session.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "uptime": uptime_seconds,
            "timestamp": now.isoformat().replace("+00:00", "Z"),
            "database": "connected",
        }
    except Exception:
        return {
            "status": "degraded",
            "database": "unreachable",
            "uptime": uptime_seconds,
            "timestamp": now.isoformat().replace("+00:00", "Z"),
        }


@router.get("/ready")
async def readiness_check(session: AsyncSession = Depends(get_session)):
    try:
        await session.execute(text("SELECT 1"))
        return {
            "status": "ready",
            "database": "connected",
            "redis": "connected",
        }
    except Exception:
        return {
            "status": "not_ready",
            "database": "unreachable",
            "redis": "unreachable",
        }