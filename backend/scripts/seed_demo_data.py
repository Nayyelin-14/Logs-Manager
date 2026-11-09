import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import asyncio
import hashlib
import os
import secrets
from sqlalchemy import select, func, cast, text
from sqlalchemy.exc import IntegrityError
from passlib.context import CryptContext
from app.core.database import get_session, async_session_maker
from app.models.user import User
from app.models.tenant import Tenant
from app.models.alert import AlertRule, Alert
from app.models.events import Event
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


SEED_PASSWORD_ENV_VARS = {
    "admin": "SEED_ADMIN_PASSWORD",
    "viewerA": "SEED_VIEWER_A_PASSWORD",
    "viewerB": "SEED_VIEWER_B_PASSWORD",
}


def resolve_seed_passwords() -> dict[str, str]:
    import os

    saas_mode = os.environ.get("SAAS_MODE", "false").strip().lower() in ("1", "true", "yes", "on")
    passwords: dict[str, str] = {}
    generated: dict[str, str] = {}
    for user, env_var in SEED_PASSWORD_ENV_VARS.items():
        value = os.environ.get(env_var)
        if value:
            passwords[user] = value
            continue
        if saas_mode:
            raise RuntimeError(
                f"{env_var} must be set when SAAS_MODE=true; refusing to seed with a default password."
            )
        passwords[user] = secrets.token_urlsafe(18)
        generated[user] = passwords[user]

    if generated:
        print("=== GENERATED SEED PASSWORDS (shown once; save them now) ===")
        for user, password in generated.items():
            print(f"{user}: {password}")
        print("=== END GENERATED SEED PASSWORDS ===", flush=True)
    return passwords


async def seed_demo_data():
    async for session in get_session():
        try:

            print("Creating tenants...")




            configured_key = os.environ.get("INGEST_API_KEY")
            if configured_key:
                demoa_key = configured_key
                demoa_hash = hashlib.sha256(configured_key.encode()).hexdigest()
            else:
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
            elif configured_key:
                demoa_tenant.api_key_hash = demoa_hash
                demoa_tenant.is_active = True
            print(f"  demoa tenant ready (API key shown once only!)")


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


            passwords = resolve_seed_passwords()

            admin_result = await session.execute(select(User).where(User.username == "admin"))
            admin = admin_result.scalar_one_or_none()
            if not admin:
                admin = User(
                    username="admin",
                    email="admin@demo.local",
                    password=hash_password(passwords["admin"]),
                    role="ADMIN",
                    tenant=None,
                    status="ACTIVE",
                )
                session.add(admin)
                print("Created admin user")

            viewer_a_result = await session.execute(select(User).where(User.username == "viewerA"))
            viewer_a = viewer_a_result.scalar_one_or_none()
            if not viewer_a:
                viewer_a = User(
                    username="viewerA",
                    email="viewerA@demo.local",
                    password=hash_password(passwords["viewerA"]),
                    role="VIEWER",
                    tenant="demoa",
                    status="ACTIVE",
                )
                session.add(viewer_a)
                print("Created viewerA user")

            viewer_b_result = await session.execute(select(User).where(User.username == "viewerB"))
            viewer_b = viewer_b_result.scalar_one_or_none()
            if not viewer_b:
                viewer_b = User(
                    username="viewerB",
                    email="viewerB@demo.local",
                    password=hash_password(passwords["viewerB"]),
                    role="VIEWER",
                    tenant="demob",
                    status="ACTIVE",
                )
                session.add(viewer_b)
                print("Created viewerB user")

            await session.commit()
            print("Database commit complete.")


            print("\n=== API KEYS (save these!) ===")
            print(f"demoa: {demoa_key}")
            print(f"demob: {demob_key}")



            rule_result = await session.execute(
                select(AlertRule).where(AlertRule.name == "Brute force: repeated failed logins")
            )
            rule = rule_result.scalar_one_or_none()
            if not rule:
                rule = AlertRule(
                    id=uuid4().hex[:25],
                    name="Brute force: repeated failed logins",
                    description="Triggers when 5+ failed logins from the same src_ip within 5 minutes (all tenants)",
                    tenant="*",
                    enabled=True,
                    severity="high",
                    filter={"outcome": "failure", "action": "login"},
                    group_by="src_ip",
                    threshold=5,
                    window_minutes=5,
                    cooldown_minutes=15,
                    notify={
                        **(
                            {"webhook_url": os.environ["ALERT_WEBHOOK_URL"]}
                            if os.environ.get("ALERT_WEBHOOK_URL")
                            else {}
                        ),
                        "cooldown_minutes": 15,
                    },
                    conditions=[
                        {
                            "type": "repeated_failures",
                            "groupBy": "src_ip",
                            "threshold": 5,
                            "windowSeconds": 300,
                            "cooldownSeconds": 900,
                        }
                    ],
                )
                session.add(rule)
                print("Created brute-force alert rule (all tenants)")
            else:
                print("Brute-force alert rule already exists")


            rule_malware_result = await session.execute(
                select(AlertRule).where(AlertRule.name == "CrowdStrike malware detected")
            )
            rule_malware = rule_malware_result.scalar_one_or_none()
            if not rule_malware:
                rule_malware = AlertRule(
                    id=uuid4().hex[:25],
                    name="CrowdStrike malware detected",
                    description="Triggers on CrowdStrike malware_detected with severity >= 8 (all tenants)",
                    tenant="*",
                    enabled=True,
                    severity="critical",
                    filter={"event_type": "malware_detected", "severity_gte": 8},
                    group_by="src_ip",
                    threshold=1,
                    window_minutes=5,
                    cooldown_minutes=15,
                    conditions=[
                        {
                            "type": "event_type",
                            "value": "malware_detected",
                            "groupBy": "src_ip",
                            "threshold": 1,
                            "windowSeconds": 300,
                            "filters": {"severity_gte": 8},
                        }
                    ],
                )
                session.add(rule_malware)
                print("Created CrowdStrike malware alert rule (all tenants)")
            else:
                print("CrowdStrike malware alert rule already exists")


            rule_iam_result = await session.execute(
                select(AlertRule).where(AlertRule.name == "AWS sensitive IAM change")
            )
            rule_iam = rule_iam_result.scalar_one_or_none()
            if not rule_iam:
                rule_iam = AlertRule(
                    id=uuid4().hex[:25],
                    name="AWS sensitive IAM change",
                    description="Triggers on AWS CreateUser or AttachUserPolicy events (all tenants)",
                    tenant="*",
                    enabled=True,
                    severity="high",
                    filter={"event_type": "CreateUser", "source": "aws"},
                    group_by="src_ip",
                    threshold=1,
                    window_minutes=5,
                    cooldown_minutes=15,
                    conditions=[
                        {
                            "type": "event_type",
                            "value": "CreateUser",
                            "groupBy": "src_ip",
                            "threshold": 1,
                            "windowSeconds": 300,
                            "filters": {"source": "aws"},
                        }
                    ],
                )
                session.add(rule_iam)
                print("Created AWS IAM change alert rule (all tenants)")
            else:
                print("AWS IAM change alert rule already exists")

            await session.commit()



            existing_result = await session.execute(
                text("SELECT id FROM events WHERE raw->>'_seed' = 'true' LIMIT 1")
            )
            already_seeded = existing_result.scalars().first() is not None
            if already_seeded:
                print("Seed events already exist, skipping ingestion")
                print("\nSeed complete!")
                return



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
