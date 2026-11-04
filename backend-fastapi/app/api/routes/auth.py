from fastapi import APIRouter, Depends, Response, HTTPException, status
from pydantic import BaseModel, AfterValidator
from typing import Annotated, Optional
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
    generate_otp,
    generate_token,
)
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.otp import Otp
from app.integrations.queue import enqueue_otp_email
import bcrypt
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


class RegisterRequest(BaseModel):
    username: str
    email: SafeEmail
    tenant: str


class OtpVerifyRequest(BaseModel):
    username: str
    email: SafeEmail
    tenant: str
    otp: str
    token: str


class ConfirmPasswordRequest(BaseModel):
    email: SafeEmail
    username: str
    tenant: str
    password: str
    confirmPassword: str
    token: str


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

    if not verify_password(request.password, user.password):
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


@router.post("/register")
async def register(
    request: RegisterRequest,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(User).where(User.email == request.email))
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=409, detail="This email number is already in use")

    otp = generate_otp()
    salt = bcrypt.gensalt(10)
    hashed_otp = bcrypt.hashpw(str(otp).encode(), salt).decode()
    remember_token = generate_token()

    otp_record = Otp(
        email=request.email,
        opt_code=hashed_otp,
        remember_token=remember_token,
        count=1,
        error=0,
    )
    session.add(otp_record)
    await session.commit()

    if settings.OTP_EMAIL_ENABLED:
        await enqueue_otp_email(request.email, otp, otp_record.id)

    return {
        "message": f"We are sending otp to {request.email}",
        "userData": {
            "id": otp_record.id,
            "email": otp_record.email,
            "optCode": otp_record.opt_code,
            "rememberToken": otp_record.remember_token,
            "count": otp_record.count,
            "error": otp_record.error,
        },
        "tenant": request.tenant,
        "username": request.username,
        "token": remember_token,
    }


@router.post("/verify-Otp")
async def verify_otp(
    request: OtpVerifyRequest,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Otp).where(Otp.email == request.email))
    otp_record = result.scalar_one_or_none()

    if not otp_record:
        raise HTTPException(status_code=400, detail="Something went wrong with one time password")

    if otp_record.remember_token != request.token:
        otp_record.error = 5
        await session.commit()
        raise HTTPException(status_code=400, detail="Unauhorized OTP detected")

    # Check OTP expiry (2 minutes)
    if otp_record.updated_at:
        expiry = datetime.datetime.now(datetime.timezone.utc) - otp_record.updated_at
        if expiry.total_seconds() > 120:
            raise HTTPException(status_code=403, detail="One time password is expired")

    if not verify_password(request.otp, otp_record.opt_code):
        otp_record.error += 1
        await session.commit()
        raise HTTPException(status_code=403, detail="One time password is incorrect")

    verify_token = generate_token()
    otp_record.verify_token = verify_token
    otp_record.count = 1
    otp_record.error = 0
    await session.commit()

    return {
        "isSuccess": True,
        "message": "OTP is successfully verified",
        "token": verify_token,
    }


@router.post("/confirm-password")
async def confirm_password(
    request: ConfirmPasswordRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Otp).where(Otp.email == request.email))
    otp_record = result.scalar_one_or_none()

    if not otp_record:
        raise HTTPException(status_code=400, detail="Something went wrong with one time password")

    if otp_record.error > 5:
        raise HTTPException(status_code=400, detail="Invalid credentials")

    if otp_record.verify_token != request.token:
        otp_record.error = 5
        await session.commit()
        raise HTTPException(status_code=400, detail="Invalid Token")

    if otp_record.updated_at:
        expiry = datetime.datetime.now(datetime.timezone.utc) - otp_record.updated_at
        if expiry.total_seconds() > 600:  # 10 minutes
            raise HTTPException(status_code=403, detail="Your request is expired. Try again later")

    if request.password != request.confirmPassword:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    hashed = hash_password(request.password)

    user = User(
        email=request.email,
        username=request.username,
        tenant=request.tenant,
        password=hashed,
        role="USER",
        status="ACTIVE",
    )
    session.add(user)
    await session.commit()

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
        "message": "Successfully created a new account",
        "userId": user.id,
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