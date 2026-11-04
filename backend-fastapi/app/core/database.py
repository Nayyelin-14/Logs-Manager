from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import get_settings
import ssl

settings = get_settings()

from app.models.base import Base  # noqa: F401, re-export


def _build_engine_args() -> dict:
    """Build engine arguments with proper SSL configuration for Neon/asyncpg."""
    # Parse DATABASE_URL to extract components for proper SSL config
    import urllib.parse
    parsed = urllib.parse.urlparse(settings.DATABASE_URL)
    
    # Extract query parameters
    query_params = urllib.parse.parse_qs(parsed.query)
    
    connect_args = {}
    
    # Handle SSL for asyncpg (Neon requires SSL)
    sslmode = query_params.get("sslmode", ["require"])[0]
    if sslmode in ("require", "verify-ca", "verify-full"):
        ssl_context = ssl.create_default_context()
        if sslmode == "verify-full":
            ssl_context.check_hostname = True
            ssl_context.verify_mode = ssl.CERT_REQUIRED
        elif sslmode == "verify-ca":
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_REQUIRED
        else:  # require - verify certificates but don't check hostname for pooled connections
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_REQUIRED
        connect_args["ssl"] = ssl_context
    
    # Remove sslmode and channel_binding from URL since we handle SSL via connect_args
    # asyncpg doesn't accept these as connection arguments
    clean_query = {k: v for k, v in query_params.items() if k not in ("sslmode", "channel_binding")}
    clean_query_str = urllib.parse.urlencode(clean_query, doseq=True)
    clean_url = urllib.parse.urlunparse((
        parsed.scheme, parsed.netloc, parsed.path, parsed.params, clean_query_str, parsed.fragment
    ))
    
    return {
        "url": clean_url,
        "connect_args": connect_args,
    }


engine_args = _build_engine_args()

if settings.DATABASE_POOL.strip().lower() in ("null", "none", "off"):
    # NullPool: every checkout gets a fresh connection on the current event
    # loop. Used by the test suite to avoid cross-event-loop connection reuse.
    from sqlalchemy.pool import NullPool

    engine = create_async_engine(
        engine_args["url"],
        echo=False,
        poolclass=NullPool,
        connect_args=engine_args["connect_args"],
    )
else:
    engine = create_async_engine(
        engine_args["url"],
        echo=settings.APP_ENV == "development",
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        connect_args=engine_args["connect_args"],
    )

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncSession:
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Verify Alembic-managed schema exists; Alembic is the single source of truth.

    This function MUST NOT call Base.metadata.create_all().
    The versions in migrations/versions/ are the only way the schema is created.
    If the schema has not been applied, startup fails fast with a clear error
    so the operator runs `docker compose exec backend alembic upgrade head`.
    """
    from sqlalchemy import text

    required = ["User", "Otp", "alert_rules", "alerts", "email_notifications", "security_logs"]
    async with engine.connect() as conn:
        res = await conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
        )
        tables = {row[0] for row in res.fetchall()}
        missing = [t for t in required if t not in tables]
        if missing:
            hint = (
                "Schema not applied: missing tables " + ", ".join(missing) + ". "
                "Run: docker compose -f backend-fastapi/docker-compose.yml exec -T backend alembic upgrade head"
            )
            raise RuntimeError(hint)
    # also verify alembic_version exists if tables exist (fresh DB without stamp will fail next start)
    async with engine.connect() as conn:
        res = await conn.execute(
            text("SELECT version_num FROM alembic_version")
        )
        version = res.scalar_one_or_none()
        if not version:
            raise RuntimeError(
                "alembic_version table is empty - schema may exist but Alembic version is not recorded. "
                "Run: docker compose -f backend-fastapi/docker-compose.yml exec -T backend alembic upgrade head"
            )


async def close_db():
    await engine.dispose()