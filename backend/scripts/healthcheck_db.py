import asyncio
import sys

from sqlalchemy import text

from app.core.database import EFFECTIVE_DB_TARGET, engine


async def main() -> int:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        print(f"db ok: {EFFECTIVE_DB_TARGET}")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"db check failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
