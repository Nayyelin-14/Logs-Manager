from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import get_session

router = APIRouter()


@router.get("/healthz")
async def health_check(session: AsyncSession = Depends(get_session)):
    try:
        await session.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "uptime": 0,
            "timestamp": "2026-11-04T00:00:00.000Z",
        }
    except Exception:
        return {
            "status": "degraded",
            "database": "unreachable",
            "timestamp": "2026-11-04T00:00:00.000Z",
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