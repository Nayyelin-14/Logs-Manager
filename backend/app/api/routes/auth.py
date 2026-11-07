from fastapi import APIRouter, Depends, Response, HTTPException, status, Request
from fastapi.responses import JSONResponse
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi import Limiter
from pydantic import BaseModel, AfterValidator
from typing import Annotated
import re
import time
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.config import get_settings
from app.core.database import get_session
from app.core.security import (
    TokenPayload,
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
)
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.enums import Role
import datetime

settings = get_settings()
router = APIRouter()

# Dedicated limiter for the login route (avoids circular import with app.main).
# Uses Redis storage so rate limits are shared across workers/containers.
# Rate limit exceptions are handled by the global handler registered in main.py.
login_limiter = Limiter(key_func=get_remote_address, storage_uri=settings.REDIS_URL)

# Per-username failed attempt tracking (in-memory, resets on restart).
# Key: email -> {"count": int, "first_failed_at": float}
_FAILED_LOGIN_TRACKER: dict[str, dict] = {}

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_email(value: str) -> str:
    value = value.strip()
    if not _EMAIL_PATTERN.match(value):
        raise ValueError("value is not a valid email address")
    return value


SafeEmail = Annotated[str, AfterValidator(_validate_email)]


class LoginRequest(BaseModel):
    email: SafeEmail
    password: str


def _is_locked_out(email: str) -> tuple[bool, int]:
    """Check if an email is locked out due to repeated failures.

    Returns (locked, retry_after_seconds).
    """
    entry = _FAILED_LOGIN_TRACKER.get(email)
    if not entry:
        return False, 0
    elapsed = time.time() - entry["first_failed_at"]
    if entry["count"] >= settings.LOGIN_LOCKOUT_ATTEMPTS and elapsed < settings.LOGIN_LOCKOUT_MINUTES * 60:
        return True, int(settings.LOGIN_LOCKOUT_MINUTES * 60 - elapsed)
    # Lockout expired: reset tracker
    if elapsed >= settings.LOGIN_LOCKOUT_MINUTES * 60:
        _FAILED_LOGIN_TRACKER.pop(email, None)
    return False, 0


def _record_failed_login(email: str):
    """Record a failed login attempt for an email."""
    now = time.time()
    entry = _FAILED_LOGIN_TRACKER.get(email)
    if not entry:
        _FAILED_LOGIN_TRACKER[email] = {"count": 1, "first_failed_at": now}
    else:
        entry["count"] += 1


def _clear_failed_logins(email: str):
    """Clear failed login tracker for an email on successful login."""
    _FAILED_LOGIN_TRACKER.pop(email, None)


class AuthCheckResponse(BaseModel):
    message: str
    user: dict


def set_auth_cookies(response: Response, access_token: str, refresh_token: str):
    opts = settings.cookie_options()
    response.set_cookie(
        "accessToken",
        access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        **opts,
    )
    response.set_cookie(
        "refreshToken",
        refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        **opts,
    )


def clear_auth_cookies(response: Response):
    opts = settings.cookie_options()
    response.delete_cookie("accessToken", **opts)
    response.delete_cookie("refreshToken", **opts)


@router.post("/login")
@login_limiter.limit("5/minute")
async def login(
    request: Request,
    login_request: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    email = login_request.email

    # Per-username lockout check (before DB lookup to avoid user enumeration)
    locked, retry_after = _is_locked_out(email)
    if locked:
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many login attempts. Try again later."},
            headers={"Retry-After": str(retry_after)},
        )

    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        _record_failed_login(email)
        locked, retry_after = _is_locked_out(email)
        if locked:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many login attempts. Try again later."},
                headers={"Retry-After": str(retry_after)},
            )
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if user.status != "ACTIVE":
        raise HTTPException(status_code=403, detail="This account is not active.")

    if user.password and not verify_password(login_request.password, user.password):
        _record_failed_login(email)
        locked, retry_after = _is_locked_out(email)
        if locked:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many login attempts. Try again later."},
                headers={"Retry-After": str(retry_after)},
            )
        raise HTTPException(status_code=401, detail="Invalid credentials")

    _clear_failed_logins(email)

    payload = TokenPayload(
        user_id=user.id,
        username=user.username,
        email=user.email,
        tenant=user.tenant,
        role=user.role,
    )

    access_token = create_access_token(payload)
    refresh_token = create_refresh_token(payload)

    set_auth_cookies(response, access_token, refresh_token)

    return {
        "message": f"Welcome back!!! {user.username}",
        "userData": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "tenant": user.tenant,
            "status": user.status,
            "createAt": user.create_at.isoformat() if user.create_at else None,
            "updatedAt": user.updated_at.isoformat() if user.updated_at else None,
        },
    }


@router.post("/logout")
async def logout(
    response: Response,
    current_user: TokenPayload = Depends(get_current_user),
):
    clear_auth_cookies(response)
    return {"message": "Loggedout successfully"}


@router.get("/auth-check")
async def auth_check(
    current_user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(User).where(User.id == current_user.user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="Unauthenticated User")

    return {
        "message": "Authenticated user",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "tenant": user.tenant,
            "status": user.status,
        },
    }