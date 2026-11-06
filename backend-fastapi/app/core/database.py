from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from app.core.config import get_settings
from app.core.db_engine import create_engine, describe_database_target
import os

settings = get_settings()

# Password-free effective DB target (host/port/db/ssl), logged by services at startup.
EFFECTIVE_DB_TARGET = describe_database_target(settings.DATABASE_URL)

from app.models.base import Base  # noqa: F401, re-export


engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.APP_ENV == "development",
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

if settings.DATABASE_POOL.strip().lower() in ("null", "none", "off"):
    from sqlalchemy.pool import NullPool
    engine = create_engine(
        settings.DATABASE_URL,
        echo=False,
        poolclass=NullPool,
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
    """Initialize database: ensure Alembic migrations are applied."""
    from sqlalchemy import text
    import asyncio

    # Retry connection to PostgreSQL (it may take time to initialize)
    max_retries = 30
    for attempt in range(max_retries):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            break
        except Exception:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(1)

    required = ["User", "Otp", "alert_rules", "alerts", "email_notifications", "events", "security_logs"]
    async with engine.connect() as conn:
        res = await conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
        )
        tables = {row[0] for row in res.fetchall()}
        missing = [t for t in required if t not in tables]

    if missing:
        import subprocess
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            env={**os.environ, "DATABASE_URL": settings.DATABASE_URL},
        )
        if result.returncode != 0:
            raise RuntimeError(f"Alembic migration failed: {result.stderr}")

    async with engine.connect() as conn:
        res = await conn.execute(
            text("SELECT version_num FROM alembic_version")
        )
        version = res.scalar_one_or_none()
        if not version:
            raise RuntimeError(
                "alembic_version table is empty - schema may exist but Alembic version is not recorded."
            )


async def close_db():
    await engine.dispose()