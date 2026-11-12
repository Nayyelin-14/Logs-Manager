import asyncio
import os
import pathlib
import subprocess
import sys

BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
IN_CONTAINER = os.path.exists("/.dockerenv")


_DB_HOST = "db" if IN_CONTAINER else "localhost"
_REDIS_HOST = "redis" if IN_CONTAINER else "localhost"


_DB_PORT = int(os.environ.get("TEST_DB_PORT", "5432" if IN_CONTAINER else "55432"))
_REDIS_PORT = int(os.environ.get("TEST_REDIS_PORT", "6379" if IN_CONTAINER else "56379"))


_ADMIN_EMAIL = "admin@demo.local"
_ADMIN_PASSWORD = os.environ.get("SEED_ADMIN_PASSWORD") or "TestPassword123!"
_VIEWER_A_EMAIL = "viewerA@demo.local"
_VIEWER_A_PASSWORD = os.environ.get("SEED_VIEWER_A_PASSWORD") or "TestViewerPassword1!"
_VIEWER_B_EMAIL = "viewerB@demo.local"
_VIEWER_B_PASSWORD = os.environ.get("SEED_VIEWER_B_PASSWORD") or "TestViewerBP@ssw0rd!"


os.environ.setdefault("SEED_ADMIN_PASSWORD", _ADMIN_PASSWORD)
os.environ.setdefault("SEED_VIEWER_A_PASSWORD", _VIEWER_A_PASSWORD)
os.environ.setdefault("SEED_VIEWER_B_PASSWORD", _VIEWER_B_PASSWORD)


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
os.environ["ALERT_WEBHOOK_URL"] = "http://127.0.0.1:9/webhook"
os.environ["WEBHOOK_RETRY_DELAYS"] = "0,0,0"
os.environ["RESEND_RETRY_DELAYS"] = "0,0"


ADMIN_EMAIL = _ADMIN_EMAIL
ADMIN_PASSWORD = _ADMIN_PASSWORD
VIEWER_A_EMAIL = _VIEWER_A_EMAIL
VIEWER_A_PASSWORD = _VIEWER_A_PASSWORD
VIEWER_B_EMAIL = _VIEWER_B_EMAIL
VIEWER_B_PASSWORD = _VIEWER_B_PASSWORD


DEMOA_API_KEY = "demoa-api-key-0123456789abcdef0123456789abcdef"
DEMOB_API_KEY = "demob-api-key-0123456789abcdef0123456789abcdef"

import pytest


@pytest.fixture(autouse=True)
def _stub_alert_delivery(monkeypatch):
    async def fake_send_webhook(*args, **kwargs):
        return [
            {
                "attempt": 1,
                "timestamp": "stubbed",
                "status": "sent",
                "http_code": 200,
                "error": None,
            }
        ]

    async def fake_send_email(*args, **kwargs):
        return {"status": "sent", "error": None}

    monkeypatch.setattr("app.services.alerting.alerter.send_webhook", fake_send_webhook)
    monkeypatch.setattr("app.services.alerting.alerter.send_email_notification", fake_send_email)


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
    env["REDIS_URL"] = f"redis://{_REDIS_HOST}:{_REDIS_PORT}"
    env["SYSLOG_ENABLED"] = "false"
    env["DATABASE_POOL"] = "null"
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
                await conn.execute(f"GRANT ALL ON SCHEMA public TO {_POSTGRES_USER}")
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
    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient
    from slowapi.errors import RateLimitExceeded
    from app.main import app
    from app.main import _rate_limit_exceeded_handler
    from app.core.limiting import limiter
    from app.api.routes.health import require_feature

    test_app = FastAPI()
    test_app.include_router(app.router)
    test_app.state.limiter = limiter
    test_app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    @test_app.get("/features/test-flagged")
    async def test_flagged_route(_=Depends(require_feature("test_flag"))):
        return {"status": "ok", "feature": "test_flag"}

    with TestClient(test_app) as test_client:
        yield test_client


def login(client, email: str, password: str):
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, f"login failed: {response.status_code} {response.text}"
    # After login, the server sets the XSRF-TOKEN cookie. Attach it as a header
    # on the client so subsequent state-changing requests pass CSRF validation.
    token = response.cookies.get("XSRF-TOKEN")
    if token:
        client.headers["X-XSRF-TOKEN"] = token
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
    from sqlalchemy import update
    import hashlib

    async def _setup():
        key_hash = hashlib.sha256(DEMOA_API_KEY.encode()).hexdigest()
        async with async_session_maker() as session:
            await session.execute(
                update(Tenant).where(Tenant.name == "demoa").values(api_key_hash=key_hash, is_active=True)
            )
            await session.commit()

    asyncio.run(_setup())
    return DEMOA_API_KEY


@pytest.fixture()
def api_key_demob(test_database):
    from app.core.database import async_session_maker
    from app.models.tenant import Tenant
    from sqlalchemy import update
    import hashlib

    async def _setup():
        key_hash = hashlib.sha256(DEMOB_API_KEY.encode()).hexdigest()
        async with async_session_maker() as session:
            await session.execute(
                update(Tenant).where(Tenant.name == "demob").values(api_key_hash=key_hash, is_active=True)
            )
            await session.commit()

    asyncio.run(_setup())
    return DEMOB_API_KEY


@pytest.fixture()
def api_key(api_key_demoa):
    return api_key_demoa


@pytest.fixture()
def feature_test_flag_enabled():
    os.environ["FEATURE_TEST_FLAG_ENABLED"] = "true"
    try:
        yield
    finally:
        os.environ.pop("FEATURE_TEST_FLAG_ENABLED", None)


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    from app.api.routes.auth import login_limiter
    from app.core.limiting import limiter
    import asyncio
    import redis.asyncio as _redis_async

    # Clear Redis lockout keys for test isolation between tests
    async def _clear_all():
        try:
            client = _redis_async.from_url(
                os.environ.get("REDIS_URL", "redis://localhost:56379"),
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            keys = await client.keys("lms:auth:login:*")
            if keys:
                await client.delete(*keys)
            await client.aclose()
        except Exception:
            pass

    try:
        asyncio.run(_clear_all())
    except Exception:
        pass
    for rate_limiter in (login_limiter, limiter):
        try:
            rate_limiter.reset()
        except Exception:
            pass


@pytest.fixture(scope="session", autouse=True)
def db_baseline(test_database):
    """Snapshot the seeded rows immediately after the session database is built.

    The snapshot is the source of truth for what "isolation" means: anything not
    present here was created by a test module and must be removed at that
    module's teardown.  Using a snapshot (instead of hard-coded names) keeps the
    cleanup correct even when seed data changes.
    """
    import asyncpg

    async def _snapshot() -> dict:
        conn = await asyncpg.connect(**_connection_kwargs(database=db_name))
        try:
            return {
                "rule_ids": [r["id"] for r in await conn.fetch("SELECT id FROM alert_rules")],
                "alert_ids": [r["id"] for r in await conn.fetch("SELECT id FROM alerts")],
                "tenant_names": [r["name"] for r in await conn.fetch("SELECT name FROM tenants")],
                "user_emails": [r["email"] for r in await conn.fetch('SELECT email FROM "User"')],
                "ingested_at": await conn.fetchval("SELECT max(ingested_at) FROM events"),
            }
        finally:
            await conn.close()

    return asyncio.run(_snapshot())


@pytest.fixture(scope="module", autouse=True)
def isolate_db(db_baseline):
    """Remove rows created by a test module once that module finishes.

    Isolation is at module scope so module-level seed fixtures (dashboard and
    tenant-isolation suites) stay alive for every test in their own module,
    while alert rules, alerts, events, users and tenants created by one module
    can never leak into the next one.  Cleanup is driven by ``db_baseline``, so
    results do not depend on test execution order.
    """
    yield
    import asyncpg

    async def _cleanup() -> None:
        conn = await asyncpg.connect(**_connection_kwargs(database=db_name))
        try:
            async with conn.transaction():
                # email_notifications references alerts, so delete it first.
                await conn.execute(
                    'DELETE FROM email_notifications '
                    'WHERE "alertId" IS NULL OR "alertId" <> ALL($1::varchar[])',
                    db_baseline["alert_ids"],
                )
                await conn.execute(
                    "DELETE FROM alerts WHERE id <> ALL($1::varchar[])",
                    db_baseline["alert_ids"],
                )
                await conn.execute(
                    "DELETE FROM alert_rules WHERE id <> ALL($1::varchar[])",
                    db_baseline["rule_ids"],
                )
                if db_baseline["ingested_at"] is not None:
                    await conn.execute(
                        "DELETE FROM events WHERE ingested_at > $1",
                        db_baseline["ingested_at"],
                    )
                await conn.execute(
                    'DELETE FROM "User" WHERE email <> ALL($1::varchar[])',
                    db_baseline["user_emails"],
                )
                await conn.execute(
                    "DELETE FROM tenants WHERE name <> ALL($1::varchar[])",
                    db_baseline["tenant_names"],
                )
        finally:
            await conn.close()

    asyncio.run(_cleanup())