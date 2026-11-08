import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.core.database import async_session_maker
from app.core.security import hash_password
from app.models.user import User


async def update_password(username: str, password: str) -> int:
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        if user is None:
            print(f"User not found: {username}", file=sys.stderr)
            return 1
        user.password = hash_password(password)
        await session.commit()
        print(f"Password updated for {username}")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Set the password for an existing user")
    parser.add_argument("username")
    parser.add_argument("password")
    args = parser.parse_args()
    if len(args.password) < 8:
        print("Password must be at least 8 characters", file=sys.stderr)
        return 2
    return asyncio.run(update_password(args.username, args.password))


if __name__ == "__main__":
    raise SystemExit(main())
