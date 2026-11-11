from fastapi import Depends, Request, Response, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import hashlib
import hmac
import secrets
import jwt
from jwt import PyJWTError, ExpiredSignatureError
from app.core.security import (
    decode_token,
    TokenPayload,
    create_access_token,
    create_refresh_token,
)
from app.core.config import get_settings, Settings
from app.core.database import get_session
from app.core.exceptions import is_transient_db_error
from app.models.user import User
from app.models.tenant import Tenant

settings = get_settings()


async def get_current_user(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> TokenPayload:
    access_token = request.cookies.get("accessToken")
    refresh_token = request.cookies.get("refreshToken")

    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthenticated user. Try Again!!!",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if access_token:
        try:
            payload = decode_token(access_token, settings.ACCESS_TOKEN_SECRET)
            result = await session.execute(select(User).where(User.id == payload["userId"]))
            user = result.scalar_one_or_none()
            if not user or user.status != "ACTIVE":
                raise HTTPException(status_code=401, detail="Account not active")

            # Never trust stale role/tenant claims from the token. Rebuild the
            # authorization context from the current database row so demoted,
            # deactivated or tenant-moved users lose old privileges immediately.
            return TokenPayload(
                user_id=user.id,
                username=user.username,
                email=user.email,
                tenant=user.tenant,
                role=user.role.value if hasattr(user.role, "value") else user.role,
            )
        except ExpiredSignatureError:
            pass
        except PyJWTError:
            pass

    try:
        payload = decode_token(refresh_token, settings.REFRESH_TOKEN_SECRET)
        result = await session.execute(select(User).where(User.id == payload["userId"]))
        user = result.scalar_one_or_none()
        if not user or user.status != "ACTIVE":
            raise HTTPException(status_code=401, detail="Account not active")

        new_payload = TokenPayload(
            user_id=user.id,
            username=user.username,
            email=user.email,
            tenant=user.tenant,
            role=user.role.value if hasattr(user.role, "value") else user.role,
        )
        new_access = create_access_token(new_payload)
        new_refresh = create_refresh_token(new_payload)

        opts = settings.cookie_options()
        response.set_cookie("accessToken", new_access, max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60, **opts)
        response.set_cookie("refreshToken", new_refresh, max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60, **opts)
        # Keep the double-submit CSRF cookie alive for the whole session. Without
        # this, the token would expire after the short access-token lifetime
        # while the session itself is still valid, breaking every write.
        csrf_token = request.cookies.get(settings.CSRF_COOKIE_NAME) or secrets.token_urlsafe(32)
        response.set_cookie(
            settings.CSRF_COOKIE_NAME,
            csrf_token,
            max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
            **settings.csrf_cookie_options(),
        )
        return new_payload

    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token refresh failed")
    except PyJWTError:
        raise HTTPException(status_code=401, detail="Token refresh failed")


async def require_admin(current_user: TokenPayload = Depends(get_current_user)) -> TokenPayload:
    if current_user.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    return current_user


async def require_viewer(current_user: TokenPayload = Depends(get_current_user)) -> TokenPayload:
    if current_user.role not in ("VIEWER", "ADMIN"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return current_user


async def get_current_user_any(current_user: TokenPayload = Depends(get_current_user)) -> TokenPayload:
    return current_user


async def get_effective_tenant(current_user: TokenPayload = Depends(get_current_user)) -> str:
    return current_user.tenant


async def verify_api_key(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> TokenPayload:
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")


    key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    try:
        result = await session.execute(
            select(Tenant).where(Tenant.api_key_hash == key_hash, Tenant.is_active == True)
        )
        tenant_row = result.scalar_one_or_none()
    except Exception as exc:
        # A database/infrastructure outage while validating the key is not an
        # authentication failure. Report it as retryable so clients (Vector,
        # rsyslog, scripts) retry instead of treating the key as invalid.
        if is_transient_db_error(exc):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database temporarily unavailable",
                headers={"Retry-After": "5"},
            ) from exc
        raise

    if not tenant_row:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return TokenPayload(
        user_id=0,
        username=f"ingest-{tenant_row.name}",
        email=f"ingest-{tenant_row.name}@local",
        tenant=tenant_row.name,
        role="VIEWER",
    )
