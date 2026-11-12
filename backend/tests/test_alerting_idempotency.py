import asyncio
import os
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.database import async_session_maker
from app.models.alert import Alert
from app.models.tenant import Tenant
from app.models.user import User

pytestmark = pytest.mark.asyncio


def _run_seed():
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script = os.path.join(backend_dir, "scripts", "seed_demo_data.py")

    env = dict(os.environ)
    db_host = "db" if os.path.exists("/.dockerenv") else "localhost"
    db_port = "5432" if os.path.exists("/.dockerenv") else "55432"
    env["DATABASE_URL"] = f"postgresql+asyncpg://logs:postgres_pass@{db_host}:{db_port}/logs_manager_test?sslmode=disable"
    env["SEED_ADMIN_PASSWORD"] = "TestPassword123!"
    env["SEED_VIEWER_A_PASSWORD"] = "TestViewerPassword1!"
    env["SEED_VIEWER_B_PASSWORD"] = "TestViewerBP@ssw0rd!"
    env["SAAS_MODE"] = "false"

    return subprocess.run(
        [sys.executable, script],
        cwd=backend_dir,
        env=env,
        capture_output=True,
        text=True,
    )


async def _counts(session):
    tenants = (await session.execute(select(Tenant))).scalars().all()
    users = (await session.execute(select(User))).scalars().all()
    alerts = (await session.execute(select(Alert))).scalars().all()
    return tenants, users, alerts


async def test_seed_demo_data_is_idempotent():
    """Running the demo seed twice must not duplicate tenants, users, or alerts."""
    for run in (1, 2):
        result = _run_seed()
        output = f"{result.stdout}\n{result.stderr}"
        assert result.returncode == 0, f"Seed run {run} failed:\n{output}"
        assert "Seed error" not in output, f"Seed run {run} had an error:\n{output}"
        assert "Seed complete!" in output, f"Seed run {run} did not complete:\n{output}"

    async with async_session_maker() as session:
        tenants, users, alerts = await _counts(session)
        assert len(tenants) == 2, f"Expected exactly 2 tenants, got {len(tenants)}"
        assert len(users) == 3, f"Expected exactly 3 users, got {len(users)}"
        dedupe_keys = [a.dedupe_key for a in alerts if a.dedupe_key]
        assert len(dedupe_keys) == len(set(dedupe_keys)), "Duplicate dedupe_keys found"
