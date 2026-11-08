import os
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.config import get_settings
from app.core.database import get_session
import redis.asyncio as aioredis

router = APIRouter()


def _health_payload(request: Request) -> dict:
    now = datetime.now(timezone.utc)
    try:
        startup_time = request.app.state.startup_time
        uptime_seconds = int((now - startup_time).total_seconds())
    except Exception:
        uptime_seconds = 0
    return {
        "status": "ok",
        "uptime": uptime_seconds,
        "timestamp": now.isoformat().replace("+00:00", "Z"),
    }


def require_feature(flag_name: str):

    def dependency():
        env_key = f"FEATURE_{flag_name.upper()}_ENABLED"
        if os.getenv(env_key, "false").lower() not in ("true", "1", "yes"):
            raise HTTPException(status_code=404, detail="Feature not enabled")

    return dependency


@router.get("/features")
async def list_features():
    flags = {}
    for key, value in os.environ.items():
        if key.startswith("FEATURE_") and key.endswith("_ENABLED"):
            flag_name = key[len("FEATURE_"):-len("_ENABLED")].lower()
            flags[flag_name] = value.lower() in ("true", "1", "yes")
    return {"features": flags}


@router.get("/healthz")
async def health_check(request: Request, session: AsyncSession = Depends(get_session)):
    payload = _health_payload(request)
    try:
        await session.execute(text("SELECT 1"))
        payload["database"] = "connected"
    except Exception:
        payload["status"] = "degraded"
        payload["database"] = "unreachable"
    return payload


@router.get("/health")
async def health_liveness(request: Request, session: AsyncSession = Depends(get_session)):
    return await health_check(request, session)


@router.get("/version")
async def version_info():
    return {
        "app_version": os.getenv("APP_VERSION", "unknown"),
        "git_sha": os.getenv("GIT_SHA") or os.getenv("RENDER_GIT_COMMIT", "unknown"),
    }


@router.get("/ready")
async def readiness_check(session: AsyncSession = Depends(get_session)):
    settings = get_settings()
    db_ok = redis_ok = False
    try:
        await session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass
    client = None
    try:
        client = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=2, socket_timeout=2)
        await client.ping()
        redis_ok = True
    except Exception:
        pass
    finally:
        if client is not None:
            try:
                await (getattr(client, "aclose", None) or client.close)()
            except Exception:
                pass
    body = {
        "status": "ready" if (db_ok and redis_ok) else "not_ready",
        "database": "connected" if db_ok else "unreachable",
        "redis": "connected" if redis_ok else "unavailable",
    }
    return JSONResponse(status_code=200 if (db_ok and redis_ok) else 503, content=body)
