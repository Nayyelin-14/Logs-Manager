import jwt
import bcrypt
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from app.core.config import get_settings


settings = get_settings()


class TokenPayload:
    def __init__(
        self,
        user_id: int,
        username: Optional[str],
        email: str,
        tenant: str,
        role: str,
    ):
        self.user_id = user_id
        self.username = username
        self.email = email
        self.tenant = tenant
        self.role = role

    def to_dict(self) -> dict:
        return {
            "userId": self.user_id,
            "username": self.username,
            "email": self.email,
            "tenant": self.tenant,
            "role": self.role,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TokenPayload":
        return cls(
            user_id=data.get("userId") or data.get("user_id"),
            username=data.get("username"),
            email=data.get("email"),
            tenant=data.get("tenant"),
            role=data.get("role"),
        )


def create_access_token(payload: TokenPayload) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token_payload = payload.to_dict()
    token_payload.update({
        "exp": int(expire.timestamp()),
    })
    return jwt.encode(token_payload, settings.ACCESS_TOKEN_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(payload: TokenPayload) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    token_payload = payload.to_dict()
    token_payload.update({
        "exp": int(expire.timestamp()),
    })
    return jwt.encode(token_payload, settings.REFRESH_TOKEN_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str, secret: str) -> dict:
    return jwt.decode(token, secret, algorithms=[settings.JWT_ALGORITHM])


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(12)).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def generate_otp() -> int:
    return (int.from_bytes(secrets.token_bytes(3), "big") % 900000) + 100000


def generate_token() -> str:
    return secrets.token_hex(32)