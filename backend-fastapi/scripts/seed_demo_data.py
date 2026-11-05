"""
Seed script for demo data: tenants, users, and logs.
Runs against the backend-fastapi PostgreSQL/Redis.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import asyncio
import hashlib
import secrets
from sqlalchemy import select, func, cast, text
from sqlalchemy.exc import IntegrityError
from passlib.context import CryptContext
from app.core.database import get_session, async_session_maker
from app.models.user import User
from app.models.tenant import Tenant
from app.models.alert import AlertRule, Alert
from app.models.security_event import SecurityEvent
from app.core.security import hash_password
from app.services.ingest_service import IngestionService
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sqlalchemy.dialects.postgresql import JSONB

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def generate_api_key():
    key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    return key, key_hash


async def seed_demo_data():
    async for session in get_session():
        try:
            # 1. Create tenants table records
            print("Creating tenants...")
            
            # Create demoa tenant
            demoa_key, demoa_hash = generate_api_key()
            demoa_result = await session.execute(
                select(Tenant).where(Tenant.name == "demoa")
            )
            demoa_tenant = demoa_result.scalar_one_or_none()
            if not demoa_tenant:
                demoa_tenant = Tenant(
                    id=hashlib.sha256(b"demoa").hexdigest()[:25],
                    name="demoa",
                    api_key_hash=demoa_hash,
                    is_active=True,
                )
                session.add(demoa_tenant)
                await session.flush()
            print(f"  demoa tenant created (API key shown once only!)")

            # Create demob tenant
            demob_key, demob_hash = generate_api_key()
            demob_result = await session.execute(
                select(Tenant).where(Tenant.name == "demob")
            )
            demob_tenant = demob_result.scalar_one_or_none()
            if not demob_tenant:
                demob_tenant = Tenant(
                    id=hashlib.sha256(b"demob").hexdigest()[:25],
                    name="demob",
                    api_key_hash=demob_hash,
                    is_active=True,
                )
                session.add(demob_tenant)
                await session.flush()
            print(f"  demob tenant created (API key shown once only!)")

            await session.commit()

            # 2. Create users: admin (Admin, all tenants), viewerA (Viewer, demoa), viewerB (Viewer, demob)
            admin_password = hash_password("Admin123!")
            viewer_a_password = hash_password("ViewerA123!")
            viewer_b_password = hash_password("ViewerB123!")

            # Check if admin already exists
            admin_result = await session.execute(select(User).where(User.username == "admin"))
            admin = admin_result.scalar_one_or_none()
            if not admin:
                admin = User(
                    username="admin",
                    email="admin@demo.local",
                    password=admin_password,
                    role="ADMIN",
                    tenant=None,  # Admin has access to all tenants
                    status="ACTIVE",
                )
                session.add(admin)
                print("Created admin user")

            # Check if viewerA already exists
            viewer_a_result = await session.execute(select(User).where(User.username == "viewerA"))
            viewer_a = viewer_a_result.scalar_one_or_none()
            if not viewer_a:
                viewer_a = User(
                    username="viewerA",
                    email="viewerA@demo.local",
                    password=viewer_a_password,
                    role="VIEWER",
                    tenant="demoa",
                    status="ACTIVE",
                )
                session.add(viewer_a)
                print("Created viewerA user")

            # Check if viewerB already exists
            viewer_b_result = await session.execute(select(User).where(User.username == "viewerB"))
            viewer_b = viewer_b_result.scalar_one_or_none()
            if not viewer_b:
                viewer_b = User(
                    username="viewerB",
                    email="viewerB@demo.local",
                    password=viewer_b_password,
                    role="VIEWER",
                    tenant="demob",
                    status="ACTIVE",
                )
                session.add(viewer_b)
                print("Created viewerB user")

            await session.commit()
            print("Database commit complete.")

            # Store API keys in a way to be displayed (not persisted as plain text)
            print("\n=== API KEYS (save these!) ===")
            print(f"demoa: {demoa_key}")
            print(f"demob: {demob_key}")

            # 3. Create alert rule: Brute force - 5 failed logins from same src_ip within 5 min
            rule_result = await session.execute(
                select(AlertRule).where(AlertRule.name == "Brute force: repeated failed logins")
            )
            rule = rule_result.scalar_one_or_none()
            if not rule:
                rule = AlertRule(
                    id=uuid4().hex[:25],
                    name="Brute force: repeated failed logins",
                    description="Triggers when 5+ failed logins from the same src_ip within 5 minutes",
                    tenant="demoa",
                    enabled=True,
                    severity="high",
                    conditions=[
                        {
                            "type": "repeated_failures",
                            "groupBy": "src_ip",
                            "threshold": 5,
                            "windowSeconds": 300,
                        }
                    ],
                )
                session.add(rule)
                print("Created brute-force alert rule for demoa")
                await session.commit()
            else:
                print("Brute-force alert rule already exists")
            
            # Create rule for demob tenant too
            rule_b_result = await session.execute(
                select(AlertRule).where(AlertRule.name == "Brute force: repeated failed logins (demob)")
            )
            rule_b = rule_b_result.scalar_one_or_none()
            if not rule_b:
                rule_b = AlertRule(
                    id=uuid4().hex[:25],
                    name="Brute force: repeated failed logins (demob)",
                    description="Triggers when 5+ failed logins from the same src_ip within 5 minutes",
                    tenant="demob",
                    enabled=True,
                    severity="high",
                    conditions=[
                        {
                            "type": "repeated_failures",
                            "groupBy": "src_ip",
                            "threshold": 5,
                            "windowSeconds": 300,
                        }
                    ],
                )
                session.add(rule_b)
                print("Created brute-force alert rule for demob")
                await session.commit()

            # 4. Idempotent marker check: if seeded events already exist, skip ingestion.
            existing_result = await session.execute(
                text("SELECT id FROM security_logs WHERE raw->>'_seed' = 'true' LIMIT 1")
            )
            already_seeded = existing_result.scalars().first() is not None
            if already_seeded:
                print("Seed events already exist, skipping ingestion")
                print("\nSeed complete!")
                return

            # 5. Ingest demo events through the real pipeline (normalization + alert evaluation).
            # Fixed-window brute-force scenario: 6 failures, same src_ip, within 5 minutes.
            now = datetime.now(timezone.utc)
            ingest = IngestionService(session)
            for i in range(6):
                result = await ingest.ingest(
                    {
                        "tenant": "demoa",
                        "source": "AD",
                        "event_id": 4625,
                        "event_type": "LogonFailed",
                        "user": "demo\\eve",
                        "host": "DC01",
                        "src_ip": "203.0.113.77",
                        "src_port": str(49152 + i),
                        "action": "LOGIN",
                        "status": "Failure",
                        "severity": 7,
                        "login_type": 3,
                        "@timestamp": (now - timedelta(seconds=60 * i)).isoformat().replace("+00:00", "Z"),
                        "raw": {"_seed": True, "scenario": "brute_force", "index": i},
                        "tags": ["demo", "seed"],
                    },
                    source="AD",
                    context={"tenant": "demoa"},
                )
                print(f"Seeded failed login {i + 1}/6 src_ip=203.0.113.77")
            # Firewall sample (distinct traffic, no alert by itself)
            await ingest.ingest(
                {
                    "tenant": "demoa",
                    "source": "firewall",
                    "event_type": "traffic_blocked",
                    "action": "DENY",
                    "src_ip": "10.0.1.10",
                    "src_port": 5353,
                    "dst_ip": "8.8.8.8",
                    "dst_port": 53,
                    "protocol": "udp",
                    "host": "fw01",
                    "rule_name": "Block-DNS",
                    "severity": 4,
                    "vendor": "demo",
                    "product": "ngfw",
                    "@timestamp": (now - timedelta(seconds=30)).isoformat().replace("+00:00", "Z"),
                    "raw": {"_seed": True, "scenario": "firewall"},
                    "tags": ["demo", "seed"],
                },
                source="FIREWALL",
                context={"tenant": "demoa"},
            )
            # demob sample (isolates tenant data)
            await ingest.ingest(
                {
                    "tenant": "demob",
                    "source": "aws",
                    "event_type": "CreateUser",
                    "user": "admin",
                    "cloud": {"service": "iam", "account_id": "123456789012", "region": "ap-southeast-1"},
                    "action": "CREATE",
                    "severity": 6,
                    "@timestamp": now.isoformat().replace("+00:00", "Z"),
                    "raw": {"_seed": True, "scenario": "aws", "eventName": "CreateUser", "requestParameters": {"userName": "temp-user"}},
                    "tags": ["demo", "seed"],
                },
                source="AWS",
                context={"tenant": "demob"},
            )
            print("\nSeed complete!")

        except Exception as e:
            await session.rollback()
            print(f"Seed error: {e}")
            import traceback
            traceback.print_exc()


async def main():
    await seed_demo_data()


if __name__ == "__main__":
    asyncio.run(main())