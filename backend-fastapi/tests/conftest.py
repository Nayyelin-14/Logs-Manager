"""Pytest configuration.

Forces every test run onto a dedicated test database (never Neon/production)
and prepares schema + demo seed before the first test executes.

Run inside the backend container:
    COMPOSE_PROJECT_NAME=logs_verify docker compose -f docker-compose.yml exec -T backend pytest -v

Or on the host with configurable ports:
    TEST_DB_PORT=55432 TEST_REDIS_PORT=56379 backend-fastapi/.venv/bin/python -m pytest -v
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

# Service hosts: db and redis (not postgres)
_DB_HOST = "db" if IN_CONTAINER else "localhost"
_REDIS_HOST = "redis" if IN_CONTAINER else "localhost"

# Ports: internal 5432/6379 in container, configurable on host
_DB_PORT = int(os.environ.get("TEST_DB_PORT", "5432" if IN_CONTAINER else "55432"))
_REDIS_PORT = int(os.environ.get("TEST_REDIS_PORT", "6379" if IN_CONTAINER else "56379"))

# Password constants with env defaults
_ADMIN_EMAIL = "admin@demo.local"
_ADMIN_PASSWORD = os.environ.get("SEED_ADMIN_PASSWORD") or "TestPassword123!"
_VIEWER_A_EMAIL = "viewerA@demo.local"
_VIEWER_A_PASSWORD = os.environ.get("SEED_VIEWER_A_PASSWORD") or "TestViewerPassword1!"
_VIEWER_B_EMAIL = "viewerB@demo.local"
_VIEWER_B_PASSWORD = os.environ.get("SEED_VIEWER_B_PASSWORD") or "TestViewerBP@ssw0rd!"

# Set env vars early for seed script
os.environ.setdefault("SEED_ADMIN_PASSWORD", _ADMIN_PASSWORD)
os.environ.setdefault("SEED_VIEWER_A_PASSWORD", _VIEWER_A_PASSWORD)
os.environ.setdefault("SEED_VIEWER_B_PASSWORD", _VIEWER_B_PASSWORD)

# DB credentials
_POSTGRES_USER = os.environ.get("POSTGRES_USER", "logs")
_POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "postgres_pass")
_POSTGRES_DB = os.environ.get("POSTGRES_DB", "logs_manager")

DEFAULT_TEST_DB = (
    f"postgresql+asyncpg://{_POSTGRES_USER}:{_POSTGRES_PASSWORD}@{_DB_HOST}:{_DB_PORT}/logs_manager_test?sslmode=disable"
)
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_DB)

if "neon" in TEST_DATABASE_URL.lower():
    raise RuntimeError(
        f"Refusing to run tests against a Neon database ({TEST_DATABASE_URL}). "
        "Use TEST_DATABASE_URL pointing at a disposable test database."
    )
db_name = TEST_DATABASE_URL.rsplit("/", 1)[-1].split("?")[0]
if "test" not in db_name.lower():
    raise RuntimeError(
        f"Refusing to run tests against a production database ({db_name}). "
        "TEST_DATABASE_URL must point at a disposable test database containing 'test' in the name."
    )

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["REDIS_URL"] = f"redis://{_REDIS_HOST}:{_REDIS_PORT}"
os.environ["SYSLOG_ENABLED"] = "false"
os.environ["DATABASE_POOL"] = "null"

# Public exports for test files
ADMIN_EMAIL = _ADMIN_EMAIL
ADMIN_PASSWORD = _ADMIN_PASSWORD
VIEWER_A_EMAIL = _VIEWER_A_EMAIL
VIEWER_A_PASSWORD = _VIEWER_A_PASSWORD
VIEWER_B_EMAIL = _VIEWER_B_EMAIL
VIEWER_B_PASSWORD = _VIEWER_B_PASSWORD

import pytest  # noqa: E402


def _connection_kwargs(database: str) -> dict:
    from urllib.parse import unquote, urlparse

    url = urlparse(TEST_DATABASE_URL.replace("+asyncpg", ""))
    return {
        "host": url.hostname or _DB_HOST,
        "port": url.port or 5432,
        "user": unquote(url.username or _POSTGRES_USER),
        "password": unquote(url.password or _POSTGRES_PASSWORD),
        "database": database,
        "ssl": False,
    }


def _ensure_database_exists() -> None:
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

    asyncio.run(_ensure())


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
    _ensure_database_exists()

    if "test" in db_name.lower():
        import asyncpg

        async def _reset():
            conn = await asyncpg.connect(**_connection_kwargs(database=db_name))
            try:
                await conn.execute("DROP SCHEMA public CASCADE")
                await conn.execute("CREATE SCHEMA public")
                await conn.execute("GRANT ALL ON SCHEMA public TO logs")
            finally:
                await conn.close()
        asyncio.run(_reset())

    result = _run([sys.executable, "-m", "alembic", "upgrade", "heads"], check=False)
    if result.returncode != 0:
        raise RuntimeError(f"alembic upgrade failed:\n{result.stdout}\n{result.stderr}")

    result = _run([sys.executable, "scripts/seed_demo_data.py"], check=False)
    output = f"{result.stdout}\n{result.stderr}"
    if result.returncode != 0 or "Seed error" in output:
        raise RuntimeError(f"seed_demo_data failed:\n{output}")

    yield


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


def login(client, email: str, password: str):
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, f"login failed: {response.status_code} {response.text}"
    return response


@pytest.fixture()
def admin_client(client):
    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    return client


@pytest.fixture()
def viewer_a_client(client):
    login(client, VIEWER_A_EMAIL, VIEWER_A_PASSWORD)
    return client


@pytest.fixture()
def viewer_b_client(client):
    login(client, VIEWER_B_EMAIL, VIEWER_B_PASSWORD)
    return client


@pytest.fixture()
def api_key_demoa(test_database):
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
    return api_key_demoa