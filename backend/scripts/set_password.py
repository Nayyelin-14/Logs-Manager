import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import or_, select

from app.core.database import async_session_maker
from app.core.security import hash_password
from app.models.user import User


async def update_password(identifier: str, password: str) -> int:
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(
                or_(User.username == identifier, User.email == identifier)
            )
        )
        user = result.scalars().first()
        if user is None:
            print(f"User not found: {identifier}", file=sys.stderr)
            return 1
        user.password = hash_password(password)
        await session.commit()
        print(f"Password updated for {user.email}")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Set the password for an existing user by username or email"
    )
    parser.add_argument("identifier", help="username or email")
    parser.add_argument("password")
    args = parser.parse_args()
    if len(args.password) < 8:
        print("Password must be at least 8 characters", file=sys.stderr)
        return 2
    return asyncio.run(update_password(args.identifier, args.password))


if __name__ == "__main__":
    raise SystemExit(main())
