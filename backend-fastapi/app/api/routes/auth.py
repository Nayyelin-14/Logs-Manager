from fastapi import APIRouter, Depends, Response, HTTPException, status
from pydantic import BaseModel, AfterValidator
from typing import Annotated
import re
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
        max_age=settings.REFRESH_TOKEN_DAYS * 24 * 60 * 60,
        **opts,
    )


def clear_auth_cookies(response: Response):
    opts = settings.cookie_options()
    response.delete_cookie("accessToken", **opts)
    response.delete_cookie("refreshToken", **opts)


@router.post("/login")
async def login(
    request: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if user.status != "ACTIVE":
        raise HTTPException(status_code=403, detail="This account is not active.")

    if user.password and not verify_password(request.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

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