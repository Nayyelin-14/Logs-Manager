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
            demoa_key_created = False
            if configured_key:
                demoa_key = configured_key
                demoa_hash = hashlib.sha256(configured_key.encode()).hexdigest()
            else:
                demoa_key, demoa_hash = generate_api_key()
                demoa_key_created = True
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
                demoa_key_created = True
            elif configured_key:
                demoa_tenant.api_key_hash = demoa_hash
                demoa_tenant.is_active = True
            print(f"  demoa tenant ready (API key shown once only!)")


            demob_key, demob_hash = generate_api_key()
            demob_key_created = False
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
                demob_key_created = True
            print("  demob tenant ready")

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


            print("\n=== API KEYS ===")
            if demoa_key_created or configured_key:
                print(f"demoa: {demoa_key}")
            else:
                print("demoa: existing key unchanged")
            if demob_key_created:
                print(f"demob: {demob_key}")
            else:
                print("demob: existing key unchanged")



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



            # IngestionService stores the supplied raw payload under the
            # normalized event's ``raw`` key, so the seed marker is nested.
            # Each scenario is seeded independently: re-running the seed stays
            # idempotent, and scenarios added later still populate an existing
            # demo database.
            existing_result = await session.execute(
                text(
                    "SELECT DISTINCT raw->'raw'->>'scenario' FROM events "
                    "WHERE raw->'raw'->>'_seed' = 'true'"
                )
            )
            seeded_scenarios = {
                row[0] for row in existing_result.fetchall() if row[0]
            }

            now = datetime.now(timezone.utc)
            ingest = IngestionService(session)

            def iso(seconds_ago: int = 0) -> str:
                return (
                    now - timedelta(seconds=seconds_ago)
                ).isoformat().replace("+00:00", "Z")

            def seed_raw(scenario: str, **extra) -> dict:
                return {"_seed": True, "scenario": scenario, **extra}

            if "brute_force" not in seeded_scenarios:
                for i in range(6):
                    await ingest.ingest(
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
                            "@timestamp": iso(60 * i),
                            "raw": seed_raw("brute_force", index=i),
                            "tags": ["demo", "seed"],
                        },
                        source="AD",
                        context={"tenant": "demoa"},
                    )
                    print(f"Seeded failed login {i + 1}/6 src_ip=203.0.113.77")
            else:
                print("Brute-force seed events already exist, skipping")

            if "firewall" not in seeded_scenarios:
                await ingest.ingest(
                    {
                        "tenant": "demoa",
                        "source": "firewall",
                        "event_type": "firewall_deny",
                        "action": "DENY",
                        "src_ip": "10.0.0.5",
                        "src_port": 54321,
                        "dst_ip": "8.8.8.8",
                        "dst_port": 53,
                        "protocol": "UDP",
                        "host": "fw01",
                        "rule_name": "block-dns",
                        "description": "DNS query blocked",
                        "severity": 6,
                        "vendor": "Fortinet",
                        "product": "FortiGate",
                        "@timestamp": iso(25),
                        "raw": seed_raw("firewall", sample="syslog_firewall.log"),
                        "tags": ["demo", "seed"],
                    },
                    source="FIREWALL",
                    context={"tenant": "demoa"},
                )
                print("Seeded firewall event")
            else:
                print("Firewall seed event already exists, skipping")

            if "network" not in seeded_scenarios:
                await ingest.ingest(
                    {
                        "tenant": "demoa",
                        "source": "network",
                        "event_type": "traffic_allowed",
                        "action": "ALLOW",
                        "src_ip": "192.168.1.10",
                        "src_port": 51515,
                        "dst_ip": "1.1.1.1",
                        "dst_port": 443,
                        "protocol": "TCP",
                        "host": "router01",
                        "interface": "Gi0/1",
                        "description": "outbound https",
                        "severity": 3,
                        "vendor": "Cisco",
                        "product": "IOS",
                        "@timestamp": iso(20),
                        "raw": seed_raw("network", sample="syslog_network.log"),
                        "tags": ["demo", "seed"],
                    },
                    source="NETWORK",
                    context={"tenant": "demoa"},
                )
                print("Seeded network event")
            else:
                print("Network seed event already exists, skipping")

            if "api" not in seeded_scenarios:
                await ingest.ingest(
                    {
                        "tenant": "demoa",
                        "source": "api",
                        "event_type": "app_login_failed",
                        "event_subtype": "wrong_password",
                        "user": "svc-api",
                        "src_ip": "203.0.113.40",
                        "action": "LOGIN",
                        "outcome": "failure",
                        "description": "API login failed",
                        "severity": 5,
                        "@timestamp": iso(15),
                        "raw": seed_raw("api", request_id="demo-request-1"),
                        "tags": ["demo", "seed"],
                    },
                    source="API",
                    context={"tenant": "demoa"},
                )
                print("Seeded API event")
            else:
                print("API seed event already exists, skipping")

            if "crowdstrike" not in seeded_scenarios:
                await ingest.ingest(
                    {
                        "tenant": "demoa",
                        "source": "crowdstrike",
                        "event_type": "malware_detected",
                        "user": "alice",
                        "host": "WIN-ENG-01",
                        "process": "invoice.exe",
                        "src_ip": "10.0.0.42",
                        "action": "alert",
                        "description": "Malicious executable blocked by Falcon",
                        "severity": 8,
                        "vendor": "crowdstrike",
                        "product": "falcon",
                        "@timestamp": iso(10),
                        "raw": seed_raw(
                            "crowdstrike",
                            DetectName="MalwareDetected",
                            FileName="invoice.exe",
                        ),
                        "tags": ["demo", "seed"],
                    },
                    source="CROWDSTRIKE",
                    context={"tenant": "demoa"},
                )
                print("Seeded CrowdStrike event")
            else:
                print("CrowdStrike seed event already exists, skipping")

            if "m365" not in seeded_scenarios:
                await ingest.ingest(
                    {
                        "tenant": "demoa",
                        "source": "m365",
                        "event_type": "UserLoggedIn",
                        "user": "alice@example.com",
                        "src_ip": "203.0.113.20",
                        "action": "LOGIN",
                        "outcome": "success",
                        "status": "Success",
                        "description": "UserLoggedIn",
                        "severity": 2,
                        "vendor": "microsoft",
                        "product": "AzureActiveDirectory",
                        "@timestamp": iso(8),
                        "raw": seed_raw(
                            "m365",
                            Operation="UserLoggedIn",
                            Workload="AzureActiveDirectory",
                        ),
                        "tags": ["demo", "seed"],
                    },
                    source="M365",
                    context={"tenant": "demoa"},
                )
                print("Seeded M365 event")
            else:
                print("M365 seed event already exists, skipping")

            if "aws_createuser_demoa" not in seeded_scenarios:
                await ingest.ingest(
                    {
                        "tenant": "demoa",
                        "source": "aws",
                        "event_type": "CreateUser",
                        "user": "alice",
                        "src_ip": "203.0.113.10",
                        "cloud": {
                            "service": "iam.amazonaws.com",
                            "account_id": "123456789012",
                            "region": "us-east-1",
                        },
                        "action": "CREATE",
                        "severity": 3,
                        "@timestamp": iso(5),
                        "raw": seed_raw(
                            "aws_createuser_demoa",
                            eventName="CreateUser",
                            requestParameters={"userName": "bob"},
                        ),
                        "tags": ["demo", "seed"],
                    },
                    source="AWS",
                    context={"tenant": "demoa"},
                )
                print("Seeded AWS event (demoa)")
            else:
                print("AWS demoa seed event already exists, skipping")

            if "aws_createuser_demob" not in seeded_scenarios:
                await ingest.ingest(
                    {
                        "tenant": "demob",
                        "source": "aws",
                        "event_type": "CreateUser",
                        "user": "admin",
                        "cloud": {"service": "iam", "account_id": "123456789012", "region": "ap-southeast-1"},
                        "action": "CREATE",
                        "severity": 6,
                        "@timestamp": iso(0),
                        "raw": seed_raw(
                            "aws_createuser_demob",
                            eventName="CreateUser",
                            requestParameters={"userName": "temp-user"},
                        ),
                        "tags": ["demo", "seed"],
                    },
                    source="AWS",
                    context={"tenant": "demob"},
                )
                print("Seeded AWS event (demob)")
            else:
                print("AWS demob seed event already exists, skipping")

            print("\nSeed complete!")

        except Exception as e:
            await session.rollback()
            print(f"Seed error: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            raise


async def main():
    await seed_demo_data()


if __name__ == "__main__":
    asyncio.run(main())
