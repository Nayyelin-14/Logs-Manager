from fastapi import APIRouter, Depends, Response, HTTPException, status, Request
from fastapi.responses import JSONResponse
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi import Limiter
from pydantic import BaseModel, AfterValidator
from typing import Annotated, Optional
import re
import secrets
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
from app.core.dependencies import get_current_user, require_admin
from app.core.tenancy import resolve_read_tenant
from app.core.auth_lockout import auth_lockout, RedisUnavailableError, LOCKOUT_TTL_SECONDS
from app.models.user import User
from app.models.tenant import Tenant
from app.models.enums import Role

settings = get_settings()
router = APIRouter()




login_limiter = Limiter(key_func=get_remote_address, storage_uri=settings.REDIS_URL)



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
    response.delete_cookie(settings.CSRF_COOKIE_NAME, **settings.csrf_cookie_options())


@router.post("/login")
@login_limiter.limit("5/minute")
async def login(
    request: Request,
    login_request: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    email = login_request.email


    try:
        locked, retry_after = await auth_lockout.is_locked_out(email)
    except RedisUnavailableError:
        return JSONResponse(
            status_code=503,
            content={"detail": "Authentication service temporarily unavailable."},
        )

    if locked:
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many login attempts. Try again later."},
            headers={"Retry-After": str(retry_after)},
        )

    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        try:
            _, lockout_activated = await auth_lockout.record_failed_login(email)
        except RedisUnavailableError:
            return JSONResponse(
                status_code=503,
                content={"detail": "Authentication service temporarily unavailable."},
            )
        if lockout_activated:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many login attempts. Try again later."},
                headers={"Retry-After": str(LOCKOUT_TTL_SECONDS)},
            )
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if user.status != "ACTIVE":
        raise HTTPException(status_code=403, detail="This account is not active.")

    if user.tenant:
        tenant_result = await session.execute(select(Tenant).where(Tenant.name == user.tenant))
        tenant = tenant_result.scalar_one_or_none()
        if tenant and not tenant.is_active:
            raise HTTPException(status_code=403, detail="Tenant is not active.")

    if user.password and not verify_password(login_request.password, user.password):
        try:
            _, lockout_activated = await auth_lockout.record_failed_login(email)
        except RedisUnavailableError:
            return JSONResponse(
                status_code=503,
                content={"detail": "Authentication service temporarily unavailable."},
            )
        if lockout_activated:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many login attempts. Try again later."},
                headers={"Retry-After": str(LOCKOUT_TTL_SECONDS)},
            )
        raise HTTPException(status_code=401, detail="Invalid credentials")

    try:
        await auth_lockout.clear_failed_logins(email)
    except RedisUnavailableError:
        return JSONResponse(
            status_code=503,
            content={"detail": "Authentication service temporarily unavailable."},
        )

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

    # Set a non-HttpOnly CSRF token cookie so the browser's JavaScript can
    # read it and send it back as the X-XSRF-TOKEN header on state-changing
    # requests. SameSite/Secure attributes mirror the auth cookies.
    csrf_token = secrets.token_urlsafe(32)
    response.set_cookie(
        settings.CSRF_COOKIE_NAME,
        csrf_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        **settings.csrf_cookie_options(),
    )

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


@router.get("/users", response_model=dict)
async def list_users_for_admin(
    session: AsyncSession = Depends(get_session),
    current_user: TokenPayload = Depends(require_admin),
    tenant: Optional[str] = None,
):
    effective_tenant = resolve_read_tenant(current_user, tenant)

    query = select(User).order_by(User.id.desc())
    if effective_tenant:
        query = query.where(User.tenant == effective_tenant)

    result = await session.execute(query)
    users = result.scalars().all()
    users_payload = [{
        "id": u.id,
        "username": u.username,
        "email": u.email,
        "role": u.role,
        "tenant": u.tenant,
        "status": u.status,
        "createAt": u.create_at.isoformat() if u.create_at else None,
        "updatedAt": u.updated_at.isoformat() if u.updated_at else None,
    } for u in users]
    return {"usersList": users_payload, "users": users_payload}
