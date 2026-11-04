"""
FastAPI Application Entry Point

Main application factory with all routes, middleware, and lifecycle management.
"""

import asyncio
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.core.config import get_settings
from app.core.database import init_db, close_db
from app.api.routes import health, auth, ingest, search, dashboard, alerts, rules, users
import structlog

settings = get_settings()

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("starting_up", env=settings.APP_ENV)

    await init_db()

    # Background tasks: syslog listeners + 7-day retention scheduler
    udp_transport = None
    tcp_server = None
    retention_scheduler = None
    if settings.SYSLOG_ENABLED:
        from app.core.database import async_session_maker
        from app.integrations.syslog import (
            start_udp_syslog_listener,
            start_tcp_syslog_listener,
        )

        if settings.SYSLOG_UDP_PORT:
            udp_transport = await start_udp_syslog_listener(async_session_maker)
        if settings.SYSLOG_TCP_PORT:
            tcp_server = await start_tcp_syslog_listener(async_session_maker)

    from app.services.retention import start_retention_scheduler

    retention_scheduler = start_retention_scheduler()

    yield

    logger.info("shutting_down")
    from app.services.retention import stop_retention_scheduler

    await stop_retention_scheduler(retention_scheduler)
    if tcp_server is not None:
        tcp_server.close()
        await tcp_server.wait_closed()
    if udp_transport is not None:
        udp_transport.close()
    await close_db()


app = FastAPI(
    title="Log Manager API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.APP_ENV != "production" else None,
    redoc_url="/redoc" if settings.APP_ENV != "production" else None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key", "Cookie"],
    expose_headers=["Set-Cookie"],
)

# Security headers
if settings.APP_ENV == "production":
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# Rate limiting
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path.startswith("/api"):
        # Check rate limit
        pass
    return await call_next(request)


# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(ingest.router, prefix="/api", tags=["Ingest"])
app.include_router(search.router, prefix="/api", tags=["Search"])
app.include_router(dashboard.router, prefix="/api", tags=["Dashboard"])
app.include_router(alerts.router, prefix="/api", tags=["Alerts"])
app.include_router(rules.router, prefix="/api", tags=["Rules"])
app.include_router(users.router, prefix="/api", tags=["Users"])


@app.get("/")
async def root():
    return {"service": "Log Manager API", "version": "0.1.0"}
