import argparse
import asyncio
import hashlib
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.core.database import async_session_maker
from app.models.tenant import Tenant


async def rotate(tenant_name: str, api_key: str | None) -> int:
    key = api_key if api_key else secrets.token_urlsafe(32)
    async with async_session_maker() as session:
        result = await session.execute(select(Tenant).where(Tenant.name == tenant_name))
        tenant = result.scalar_one_or_none()
        if tenant is None:
            print(f"Tenant not found: {tenant_name}", file=sys.stderr)
            return 1
        tenant.api_key_hash = hashlib.sha256(key.encode()).hexdigest()
        await session.commit()
    print(f"API key for tenant {tenant_name}: {key}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Rotate a tenant ingestion API key")
    parser.add_argument("tenant")
    parser.add_argument("api_key", nargs="?")
    args = parser.parse_args()
    if args.api_key and len(args.api_key) < 16:
        print("API key must be at least 16 characters", file=sys.stderr)
        return 2
    return asyncio.run(rotate(args.tenant, args.api_key))


if __name__ == "__main__":
    raise SystemExit(main())
