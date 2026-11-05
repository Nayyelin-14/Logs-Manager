"""Pytest configuration.

Forces every test run onto a dedicated test database (never Neon/production)
and prepares schema + demo seed before the first test executes.

Run inside the backend container:
    docker compose -f backend-fastapi/docker-compose.yml exec -T backend pytest -v
or on the host with the project venv:
    backend-fastapi/.venv/bin/python -m pytest -v
"""

import asyncio
import hashlib
import os
import pathlib
import secrets
import subprocess
import sys

BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
IN_CONTAINER = os.path.exists("/.dockerenv")
_HOST = "postgres" if IN_CONTAINER else "localhost"

DEFAULT_TEST_DB = (
    f"postgresql+asyncpg://logs:postgres_pass@{_HOST}:5432/logs_manager_test?sslmode=disable"
)
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_DB)

# Guard: refuse to run tests against production/Neon databases
db_name = TEST_DATABASE_URL.rsplit("/", 1)[-1].split("?")[0]
if "neon" in TEST_DATABASE_URL.lower():
    raise RuntimeError(
        f"Refusing to run tests against a Neon database ({TEST_DATABASE_URL}). "
        "Use TEST_DATABASE_URL pointing at a disposable test database."
    )
if "test" not in db_name.lower():
    raise RuntimeError(
        f"Refusing to run tests against a production database ({db_name}). "
        "TEST_DATABASE_URL must point at a disposable test database containing 'test' in the name."
    )

# Bind settings/engine to the test database BEFORE any app import.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
# Local .env points at a shared Upstash Redis; tests use the local Docker Redis.
os.environ["REDIS_URL"] = f"redis://{_HOST}:6379"
os.environ["SYSLOG_ENABLED"] = "false"
# NullPool: connections are never reused across the pytest/TestClient event loops.
os.environ["DATABASE_POOL"] = "null"

import pytest  # noqa: E402


def _connection_kwargs(database: str) -> dict:
    from urllib.parse import unquote, urlparse

    url = urlparse(TEST_DATABASE_URL.replace("+asyncpg", ""))
    return {
        "host": url.hostname or _HOST,
        "port": url.port or 5432,
        "user": unquote(url.username or "logs"),
        "password": unquote(url.password or "postgres_pass"),
        "database": database,
        "ssl": False,
    }


def _ensure_database_exists() -> None:
    """Create the test database if it does not exist yet."""
    import asyncpg

    target = TEST_DATABASE_URL.replace("+asyncpg", "").split("?")[0].rsplit("/", 1)[-1]

    async def _ensure() -> None:
        try:
            conn = await asyncpg.connect(**_connection_kwargs(target))
        except asyncpg.InvalidCatalogNameError:
            admin = await asyncpg.connect(**_connection_kwargs("postgres"))
            try:
                await admin.execute(f'CREATE DATABASE "{target}"')
            finally:
                await admin.close()
            conn = await asyncpg.connect(**_connection_kwargs(target))
        await conn.close()

    asyncio_run = asyncio.run
    asyncio_run(_ensure())


def _run(args: list, *, check: bool = True) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["DATABASE_URL"] = TEST_DATABASE_URL
    return subprocess.run(
        args,
        cwd=str(BACKEND_DIR),
        env=env,
        check=check,
        capture_output=True,
        text=True,
    )


@pytest.fixture(scope="session", autouse=True)
def test_database():
    """Create schema (alembic) and seed demo data once per test session."""
    _ensure_database_exists()

    result = _run([sys.executable, "-m", "alembic", "upgrade", "head"])
    if result.returncode != 0:
        raise RuntimeError(
            f"alembic upgrade head failed:\n{result.stdout}\n{result.stderr}"
        )

    result = _run([sys.executable, "scripts/seed_demo_data.py"])
    output = f"{result.stdout}\n{result.stderr}"
    if result.returncode != 0 or "Seed error" in output:
        raise RuntimeError(f"seed_demo_data failed:\n{output}")

    yield


@pytest.fixture()
def client():
    """FastAPI test client (no lifespan: listeners/scheduler stay off)."""
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


def login(client, email: str, password: str):
    """Log in and return the response (session cookies stay on the client)."""
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, f"login failed: {response.status_code} {response.text}"
    return response


@pytest.fixture()
def admin_client(client):
    login(client, "admin@demo.local", "Admin123!")
    return client


@pytest.fixture()
def viewer_a_client(client):
    login(client, "viewerA@demo.local", "ViewerA123!")
    return client


@pytest.fixture()
def viewer_b_client(client):
    login(client, "viewerB@demo.local", "ViewerB123!")
    return client


@pytest.fixture()
def api_key_demoa(test_database):
    """Generate a fresh API key for demoa tenant, store its hash, return raw key."""
    from app.core.database import async_session_maker, engine
    from app.models.tenant import Tenant
    from sqlalchemy import update, select
    import asyncio
    import hashlib
    import secrets

    async def _setup():
        raw_key = secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        print(f"[FIXTURE api_key_demoa] Generated key: {raw_key}")
        print(f"[FIXTURE api_key_demoa] Generated hash: {key_hash}")
        print(f"[FIXTURE api_key_demoa] Engine URL: {engine.url}")
        async with async_session_maker() as session:
            await session.execute(
                update(Tenant).where(Tenant.name == "demoa").values(api_key_hash=key_hash)
            )
            await session.commit()
            print(f"[FIXTURE api_key_demoa] Hash stored in database")
            # Verify immediately
            result = await session.execute(select(Tenant).where(Tenant.name == "demoa"))
            tenant = result.scalar_one_or_none()
            if tenant:
                print(f"[FIXTURE api_key_demoa] Verified DB hash: {tenant.api_key_hash}")
                print(f"[FIXTURE api_key_demoa] Match: {tenant.api_key_hash == key_hash}")
        return raw_key

    return asyncio.run(_setup())


@pytest.fixture()
def api_key_demoa(test_database):
    """Generate a fresh API key for demoa tenant, store its hash, return raw key."""
    from app.core.database import async_session_maker
    from app.models.tenant import Tenant
    from sqlalchemy import update, select
    import asyncio
    import hashlib
    import secrets

    async def _setup():
        raw_key = secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        async with async_session_maker() as session:
            await session.execute(
                update(Tenant).where(Tenant.name == "demoa").values(api_key_hash=key_hash, is_active=True)
            )
            await session.commit()
        return raw_key

    return asyncio.run(_setup())


@pytest.fixture()
def api_key_demob(test_database):
    """Generate a fresh API key for demob tenant, store its hash, return raw key."""
    from app.core.database import async_session_maker
    from app.models.tenant import Tenant
    from sqlalchemy import update, select
    import asyncio
    import hashlib
    import secrets

    async def _setup():
        raw_key = secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        async with async_session_maker() as session:
            await session.execute(
                update(Tenant).where(Tenant.name == "demob").values(api_key_hash=key_hash, is_active=True)
            )
            await session.commit()
        return raw_key

    return asyncio.run(_setup())


@pytest.fixture()
def api_key(api_key_demoa):
    """Alias for api_key_demoa for backward compatibility with existing tests."""
    return api_key_demoa
