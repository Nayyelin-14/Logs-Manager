import asyncio
import sys
import ssl
import urllib.parse
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context

sys.path.append(".")

from app.models.base import Base
import app.models  # noqa: F401  ensure all model tables register on Base.metadata
from app.core.config import get_settings

config = context.config
settings = get_settings()

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _build_engine_args(database_url: str) -> dict:
    """Build engine arguments with proper SSL configuration for Neon/asyncpg."""
    parsed = urllib.parse.urlparse(database_url)
    query_params = urllib.parse.parse_qs(parsed.query)
    
    connect_args = {}
    
    # Handle SSL for asyncpg (Neon requires SSL)
    # For local connections (localhost/127.0.0.1), skip SSL
    host = parsed.hostname or ''
    if host not in ('localhost', '127.0.0.1'):
        sslmode = query_params.get("sslmode", ["require"])[0]
        if sslmode in ("require", "verify-ca", "verify-full"):
            ssl_context = ssl.create_default_context()
            if sslmode == "verify-full":
                ssl_context.check_hostname = True
                ssl_context.verify_mode = ssl.CERT_REQUIRED
            elif sslmode == "verify-ca":
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_REQUIRED
            else:
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_REQUIRED
            connect_args = {"ssl": ssl_context}
    
    clean_query = {k: v for k, v in query_params.items() if k not in ("sslmode", "channel_binding")}
    clean_query_str = urllib.parse.urlencode(clean_query, doseq=True)
    clean_url = urllib.parse.urlunparse((
        parsed.scheme, parsed.netloc, parsed.path, parsed.params, clean_query_str, parsed.fragment
    ))
    
    return {
        "url": clean_url,
        "connect_args": connect_args,
    }


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    engine_args = _build_engine_args(settings.DATABASE_URL)
    context.configure(
        url=engine_args["url"],
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine_args = _build_engine_args(settings.DATABASE_URL)
    connectable = create_async_engine(
        engine_args["url"],
        echo=False,
        pool_pre_ping=True,
        poolclass=pool.NullPool,
        connect_args=engine_args["connect_args"],
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
