import asyncio
import hmac
import logging
import structlog
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from urllib.parse import urlparse
from fastapi import FastAPI, Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from slowapi.errors import RateLimitExceeded

from app.core.config import get_settings
from app.core.limiting import limiter
from app.core.database import init_db, close_db, EFFECTIVE_DB_TARGET
from app.api.routes import (
    health,
    auth,
    ingest,
    search,
    dashboard,
    alerts,
    rules,
    users,
    aliases,
    stats,
)
from app.services.retention import start_retention_scheduler, stop_retention_scheduler
from app.worker import run as worker_run

settings = get_settings()


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
startup_logger = logging.getLogger("uvicorn.error")

@asynccontextmanager
async def lifespan(app: FastAPI):
    from datetime import datetime, timezone
    app.state.startup_time = datetime.now(timezone.utc)

    startup_logger.info(
        "starting_up env=%s db_target=%s worker_embedded=%s",
        settings.APP_ENV,
        EFFECTIVE_DB_TARGET,
        settings.WORKER_EMBEDDED,
    )

    email_provider = (settings.EMAIL_PROVIDER or "smtp").strip().lower()
    if not settings.EMAIL_ENABLED:
        email_state = "disabled"
    elif email_provider == "resend":
        email_state = (
            "valid"
            if settings.RESEND_API_KEY and settings.ALERT_EMAIL_FROM
            else "invalid_config"
        )
    elif email_provider == "smtp":
        email_state = (
            "valid"
            if settings.SMTP_HOST and settings.SMTP_USERNAME
            else "invalid_config"
        )
    else:
        email_state = "unknown_provider"
    startup_logger.info(
        "email provider=%s enabled=%s config=%s recipient_configured=%s webhook_configured=%s",
        email_provider,
        settings.EMAIL_ENABLED,
        email_state,
        bool(settings.ALERT_EMAIL_TO),
        bool(settings.ALERT_WEBHOOK_URL),
    )

    await init_db()


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

    # The embedded worker already runs retention at startup and hourly. Only
    # start the in-process scheduler when no worker process is embedded, so the
    # web process still handles retention on long-running deployments.
    if not settings.WORKER_EMBEDDED:
        from app.services.retention import start_retention_scheduler

        retention_scheduler = start_retention_scheduler()




    worker_task = None
    if settings.WORKER_EMBEDDED:
        worker_task = asyncio.create_task(worker_run())

    yield

    logger.info("shutting_down")
    if worker_task is not None:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass
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


async def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    retry_after = getattr(exc, "retry_after", None) or 60
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many login attempts. Try again later."},
        headers={"Retry-After": str(retry_after)},
    )


app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-API-Key",
        "X-XSRF-TOKEN",
        "Cookie",
    ],
    expose_headers=["Set-Cookie"],
)


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


def _origin_base(origin: str) -> str | None:
    """Return scheme://host:port for an origin string, or None if unparseable."""
    try:
        parsed = urlparse(origin)
        if not parsed.scheme or not parsed.hostname:
            return None
        base = f"{parsed.scheme}://{parsed.hostname}"
        if parsed.port:
            base += f":{parsed.port}"
        return base
    except Exception:
        return None


def _is_trusted_origin(origin: str) -> bool:
    base = _origin_base(origin)
    if base is None:
        return False
    for trusted in settings.CORS_ORIGINS:
        if _origin_base(trusted) == base:
            return True
    return False


@app.middleware("http")
async def csrf_protection(request: Request, call_next):
    """CSRF protection for cookie-authenticated state-changing requests.

    Uses a double-submit cookie strategy: a non-HttpOnly ``XSRF-TOKEN`` cookie
    is set on login; the browser's JavaScript reads it and sends it back as the
    ``X-XSRF-TOKEN`` header. The server verifies header matches cookie using
    constant-time comparison, so a cross-origin attacker cannot forge the header.

    Origin/Referer validation is an additional layer on top of the double-submit
    token check. The token check always runs for authenticated unsafe requests,
    regardless of whether Origin or Referer is present. Missing Origin never
    skips CSRF validation.

    Exemptions:
    - GET/HEAD/OPTIONS (safe methods)
    - Requests with ``X-API-Key`` AND no ``accessToken`` cookie
      (machine API-key auth only, not cookie sessions)
    - ``POST /api/auth/login`` (entry point that sets the CSRF cookie)
    """

    if request.method in ("GET", "HEAD", "OPTIONS"):
        return await call_next(request)

    has_api_key = bool(request.headers.get("X-API-Key"))
    has_access_token = bool(request.cookies.get("accessToken"))

    # Machine API-key authentication is not vulnerable to browser CSRF,
    # but only when no cookie session is also in use. If both are present,
    # the cookie session takes precedence and CSRF applies.
    if has_api_key and not has_access_token:
        return await call_next(request)

    # Login is the entry point; it sets the CSRF cookie.
    if request.url.path == "/api/auth/login":
        return await call_next(request)

    # CSRF only protects authenticated cookie sessions.
    if not has_access_token:
        return await call_next(request)

    # Double-submit cookie check — always required, regardless of Origin/Referer.
    csrf_cookie = request.cookies.get(settings.CSRF_COOKIE_NAME)
    csrf_header = request.headers.get(settings.CSRF_HEADER_NAME)
    if (
        not csrf_cookie
        or not csrf_header
        or not hmac.compare_digest(csrf_cookie, csrf_header)
    ):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "CSRF token missing or invalid"},
        )

    # Origin/Referer validation — additional layer, never a bypass.
    origin = request.headers.get("origin")
    referer = request.headers.get("referer")

    if origin:
        if not _is_trusted_origin(origin):
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Untrusted origin"},
            )
    elif referer:
        if not _is_trusted_origin(referer):
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Untrusted referer"},
            )

    return await call_next(request)




app.include_router(health.router, tags=["Health"])
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(ingest.router, prefix="/api", tags=["Ingest"])
app.include_router(ingest.public_router, tags=["Ingest"])
app.include_router(search.router, prefix="/api", tags=["Search"])
app.include_router(dashboard.router, prefix="/api", tags=["Dashboard"])
app.include_router(alerts.router, prefix="/api", tags=["Alerts"])
app.include_router(rules.router, prefix="/api", tags=["Rules"])
app.include_router(users.router, prefix="/api", tags=["Users"])
app.include_router(aliases.alias_router, tags=["Ingest Aliases"])
app.include_router(stats.router, prefix="/api", tags=["Stats"])


@app.get("/")
async def root():
    return {"service": "Log Manager API", "version": "0.1.0"}
