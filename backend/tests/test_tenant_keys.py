import hashlib
import io
import json
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.main import app
from app.core.database import async_session_maker
from app.models.tenant import Tenant



DEMOA_API_KEY = "demoA-test-key-0123456789abcdef"
DEMOB_API_KEY = "demoB-test-key-0123456789abcdef"


from conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    VIEWER_A_EMAIL,
    VIEWER_A_PASSWORD,
    VIEWER_B_EMAIL,
    VIEWER_B_PASSWORD,
)
def login(client: TestClient, email: str, password: str) -> TestClient:
    client.post("/api/auth/login", json={"email": email, "password": password})
    return client


def aws_sample(tenant: str = "demob") -> dict:
    return {
        "tenant": tenant,
        "source": "AWS",
        "event_type": "CreateUser",
        "event_subtype": "CreateUser",
        "severity": 6,
        "action": "CREATE",
        "user": "admin",
        "cloud": {
            "service": "iam",
            "account_id": "123456789012",
            "region": "ap-southeast-1",
        },
        "@timestamp": "2026-11-05T10:00:00Z",
        "raw": {
            "eventName": "CreateUser",
            "requestParameters": {"userName": "temp-user"},
        },
        "tags": ["demo", "seed"],
    }


@pytest.fixture(scope="session", autouse=True)
def seed_tenants():
    import asyncio

    async def _seed():
        async with async_session_maker() as session:
            from sqlalchemy import select

            for name, key in [("demoa", DEMOA_API_KEY), ("demob", DEMOB_API_KEY)]:
                key_hash = hashlib.sha256(key.encode()).hexdigest()
                tenant_id = hashlib.sha256(name.encode()).hexdigest()[:25]


                result = await session.execute(select(Tenant).where(Tenant.name == name))
                existing = result.scalar_one_or_none()
                if existing:
                    existing.api_key_hash = key_hash
                    existing.is_active = True
                else:
                    tenant = Tenant(
                        id=tenant_id,
                        name=name,
                        api_key_hash=key_hash,
                        is_active=True,
                    )
                    session.add(tenant)

            await session.commit()

    asyncio.run(_seed())







def test_demoa_key_cross_tenant_403():
    client = TestClient(app)
    resp = client.post(
        "/api/ingest",
        json=aws_sample("demob"),
        headers={"X-API-Key": DEMOA_API_KEY},
    )
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"


def test_demob_key_ingest_202():
    client = TestClient(app)
    resp = client.post(
        "/api/ingest",
        json=aws_sample("demob"),
        headers={"X-API-Key": DEMOB_API_KEY},
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"


def test_demob_key_visible_to_viewerb_not_viewera():
    client = TestClient(app)

    client.post(
        "/api/ingest",
        json=aws_sample("demob"),
        headers={"X-API-Key": DEMOB_API_KEY},
    )


    vb = login(TestClient(app), VIEWER_B_EMAIL, VIEWER_B_PASSWORD)
    resp = vb.get("/api/get-logs?tenant=demob")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    logs = data.get("logs", [])
    assert any(l.get("tenant") == "demob" for l in logs), "viewerB should see demob logs"


    va = login(TestClient(app), VIEWER_A_EMAIL, VIEWER_A_PASSWORD)
    resp = va.get("/api/get-logs?tenant=demob")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    logs = data.get("logs", [])
    assert not any(l.get("tenant") == "demob" for l in logs), "viewerA should NOT see demob logs"


    admin = login(TestClient(app), ADMIN_EMAIL, ADMIN_PASSWORD)
    resp = admin.get("/api/get-logs?tenant=demob")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    logs = data.get("logs", [])
    assert any(l.get("tenant") == "demob" for l in logs), "admin should see demob logs"


def test_demob_key_batch_202():
    client = TestClient(app)
    resp = client.post(
        "/api/ingest/batch",
        json={"events": [aws_sample("demob")], "source": "AWS", "tenant": "demob"},
        headers={"X-API-Key": DEMOB_API_KEY},
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"


def test_demob_key_file_202():
    client = TestClient(app)
    files = {"file": ("cloudtrail.json", io.BytesIO(json.dumps(aws_sample("demob")).encode()), "application/json")}
    resp = client.post(
        "/api/ingest/file",
        files=files,
        headers={"X-API-Key": DEMOB_API_KEY},
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"


def test_no_tenant_field_lands_in_key_tenant():
    client = TestClient(app)
    sample = aws_sample("demob")
    del sample["tenant"]
    resp = client.post(
        "/api/ingest",
        json=sample,
        headers={"X-API-Key": DEMOA_API_KEY},
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"


def test_unknown_key_401():
    client = TestClient(app)
    resp = client.post(
        "/api/ingest",
        json=aws_sample("demoa"),
        headers={"X-API-Key": "unknown-key-that-does-not-exist"},
    )
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"


def test_missing_key_401():
    client = TestClient(app)
    resp = client.post("/api/ingest", json=aws_sample("demoa"))
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"







def test_create_tenant_admin_201():
    client = TestClient(app)
    admin = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    import uuid
    tenant_name = f"tenantC-{uuid.uuid4().hex[:8]}"
    resp = admin.post(
        "/api/tenants",
        json={"name": tenant_name, "is_active": True},
    )
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "api_key" in data, f"Response must contain api_key: {data}"

    body_text = json.dumps(data)
    assert body_text.count(data["api_key"]) == 1, "API key should appear exactly once"


def test_create_tenant_viewer_403():
    client = TestClient(app)
    viewer = login(client, VIEWER_B_EMAIL, VIEWER_B_PASSWORD)
    resp = viewer.post(
        "/api/tenants",
        json={"name": "tenantC", "is_active": True},
    )
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"


def test_create_tenant_unauth_401():
    client = TestClient(app)
    resp = client.post("/api/tenants", json={"name": "tenantC", "is_active": True})
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"


def test_get_tenants_no_key_exposed():
    client = TestClient(app)
    admin = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    resp = admin.get("/api/tenants")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    body_text = resp.text
    assert "api_key" not in body_text, "Response must not contain api_key"
    assert "api_key_hash" not in body_text, "Response must not contain api_key_hash"
    assert DEMOA_API_KEY not in body_text, "Response must not contain the raw key"


def test_rotate_key():
    client = TestClient(app)
    admin = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)


    import asyncio
    import time
    from app.core.database import async_session_maker
    from app.models.tenant import Tenant
    import hashlib
    import secrets

    async def create_test_tenant():
        async with async_session_maker() as session:
            tenant_name = f"tenantd{int(time.time()*1000)%100000}"
            new_key = f"test-key-{tenant_name}"
            key_hash = hashlib.sha256(new_key.encode()).hexdigest()
            tenant_id = hashlib.sha256(tenant_name.encode()).hexdigest()[:25]
            tenant = Tenant(
                id=tenant_id,
                name=tenant_name,
                api_key_hash=key_hash,
                is_active=True,
            )
            session.add(tenant)
            await session.commit()
            return tenant_name, new_key

    tenant_name, new_key = asyncio.run(create_test_tenant())


    resp = admin.post(f"/api/tenants/{tenant_name}/rotate-key")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    rotated_key = resp.json()["api_key"]
    assert rotated_key != new_key, "Rotated key should differ from original"


    resp = client.post(
        "/api/ingest",
        json=aws_sample(tenant_name),
        headers={"X-API-Key": rotated_key},
    )
    assert resp.status_code == 200, f"Expected 200 with rotated key, got {resp.status_code}: {resp.text}"


    resp = client.post(
        "/api/ingest",
        json=aws_sample(tenant_name),
        headers={"X-API-Key": new_key},
    )
    assert resp.status_code == 401, f"Expected 401 with old key, got {resp.status_code}: {resp.text}"


def test_invalid_tenant_names_422():
    client = TestClient(app)
    admin = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    import uuid
    for bad_name in ["all", "a", "x;y", ""]:
        resp = admin.post("/api/tenants", json={"name": bad_name, "is_active": True})
        assert resp.status_code == 422, (
            f"Expected 422 for name={bad_name!r}, got {resp.status_code}: {resp.text}"
        )


def test_deactivate_tenant_blocks_viewer():
    client = TestClient(app)
    admin = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)


    resp = admin.patch("/api/tenants/demob", json={"is_active": False})
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["is_active"] is False, f"Tenant should be deactivated, got {data}"


    resp = admin.patch("/api/tenants/demob", json={"is_active": True})
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["is_active"] is True, f"Tenant should be active, got {data}"


def test_duplicate_tenant_409():
    client = TestClient(app)
    admin = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)

    resp = admin.post("/api/tenants", json={"name": "demoa", "is_active": True})
    assert resp.status_code == 409, f"Expected 409, got {resp.status_code}: {resp.text}"
