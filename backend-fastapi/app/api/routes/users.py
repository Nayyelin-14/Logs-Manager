"""
User Management API Routes

User CRUD operations (Admin only).
"""

from fastapi import APIRouter, Depends, HTTPException, status, Form
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr

from app.core.database import get_session
from app.core.dependencies import get_current_user, require_admin
from app.core.security import hash_password, TokenPayload
from app.models.user import User
from app.models.events import Event

router = APIRouter()


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    tenant: str
    status: str
    createAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None


@router.get("/get-users", response_model=dict)
async def list_users(
    search: Optional[str] = None,
    limit: int = 25,
    cursor: Optional[int] = None,
    session: AsyncSession = Depends(get_session),
    current_user: "TokenPayload" = Depends(require_admin),
):
    """List all users (Admin only)."""
    tenant = current_user.tenant
    
    query = select(User).where(User.tenant == tenant)
    if search:
        search_term = f"%{search}%"
        query = query.where(
            (User.username.ilike(f"%{search}%")) |
            (User.email.ilike(f"%{search}%"))
        )
    
    query = query.order_by(desc(User.create_at)).limit(limit + 1)
    if cursor:
        query = query.where(User.id > cursor)
    
    result = await session.execute(query)
    users = result.scalars().all()
    
    has_next = len(users) > limit
    if has_next:
        users = users[:limit]
    
    next_cursor = users[-1].id if has_next else None
    
    return {
        "usersList": [{
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "role": u.role,
            "tenant": u.tenant,
            "status": u.status,
            "createAt": u.create_at.isoformat() if u.create_at else None,
            "updatedAt": u.updated_at.isoformat() if u.updated_at else None,
        } for u in users],
        "newCursor": next_cursor,
    }


@router.get("/users/{query}", response_model=dict)
async def get_users_infinite(
    query: str = " ",
    filters: Optional[Dict[str, Any]] = None,
    limit: int = 25,
    cursor: Optional[int] = None,
    session: AsyncSession = Depends(get_session),
    current_user: "TokenPayload" = Depends(require_admin),
):
    """Infinite scroll users with filters (Admin only)."""
    tenant = current_user.tenant
    
    query_stmt = select(User).where(User.tenant == tenant)
    
    if filters:
        if filters.get("role"):
            query_stmt = query_stmt.where(User.role == filters["role"])
        if filters.get("status"):
            query_stmt = query_stmt.where(User.status == filters["status"])
        if filters.get("date"):
            # Parse date filter
            pass
        if filters.get("search"):
            search_term = f"%{filters['search']}%"
            query_stmt = query_stmt.where(
                (User.username.ilike(f"%{filters['search']}%")) |
                (User.email.ilike(f"%{filters['search']}%"))
            )
    
    query_stmt = query_stmt.order_by(desc(User.create_at)).limit(limit + 1)
    if cursor:
        query_stmt = query_stmt.where(User.id > cursor)
    
    result = await session.execute(query_stmt)
    users = result.scalars().all()
    
    has_next = len(users) > limit
    if has_next:
        users.pop()
    
    next_cursor = users[-1].id if has_next else None
    
    return {
        "usersList": [{
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "role": u.role,
            "tenant": u.tenant,
            "status": u.status,
            "createAt": u.create_at.isoformat() if u.create_at else None,
            "updatedAt": u.updated_at.isoformat() if u.updated_at else None,
        } for u in users],
        "newCursor": next_cursor,
        "prevCursor": cursor,
    }


@router.post("/create-user", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    username: str = Form(...),
    email: str = Form(...),
    tenant: str = Form(...),
    role: str = Form("VIEWER"),
    status: str = Form("ACTIVE"),
    password: str = Form(...),
    session: AsyncSession = Depends(get_session),
    current_user: "TokenPayload" = Depends(require_admin),
):
    """Create a new user (Admin only)."""
    if tenant != current_user.tenant:
        raise HTTPException(status_code=403, detail="Cannot create user for different tenant")
    
    from app.core.security import hash_password
    
    existing = await session.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")
    
    hashed = hash_password(password)
    user = User(
        username=username,
        email=email,
        tenant=tenant,
        role=role,
        status=status,
        password=hashed,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        tenant=user.tenant,
        status=user.status,
        createAt=user.create_at,
        updatedAt=user.updated_at,
    )


@router.put("/update-user", response_model=UserResponse)
async def update_user(
    id: int = Form(...),
    username: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    tenant: Optional[str] = Form(None),
    role: Optional[str] = Form(None),
    status: Optional[str] = Form(None),
    session: AsyncSession = Depends(get_session),
    current_user: "TokenPayload" = Depends(require_admin),
):
    """Update a user (Admin only)."""
    result = await session.execute(
        select(User).where(User.id == id, User.tenant == current_user.tenant)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if username is not None:
        user.username = username
    if email is not None:
        user.email = email
    if tenant is not None:
        user.tenant = tenant
    if role is not None:
        user.role = role
    if status is not None:
        user.status = status
    
    await session.commit()
    await session.refresh(user)
    
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        tenant=user.tenant,
        status=user.status,
        createAt=user.create_at,
        updatedAt=user.updated_at,
    )


@router.delete("/delete-user/{user_id}", response_model=dict)
async def delete_user(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: "TokenPayload" = Depends(require_admin),
):
    """Delete a user (Admin only)."""
    result = await session.execute(
        select(User).where(User.id == user_id, User.tenant == current_user.tenant)
    )
    user = result.scalar_one_or_none()
    if not user:
        return {"success": False, "message": "User not found"}
    
    # Capture user data before deletion for response
    user_data = {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "tenant": user.tenant,
        "status": user.status,
    }
    
    await session.delete(user)
    await session.commit()
    
    return {"success": True, "message": "User deleted successfully", "user": user_data}


@router.get("/get-all-data", response_model=dict)
async def get_all_data(
    tenant: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    current_user: "TokenPayload" = Depends(require_admin),
):
    """Get aggregated data counts for dashboard cards."""
    tenant = tenant if tenant and tenant != "all" else current_user.tenant
    
    total_events = await session.execute(
        select(func.count()).select_from(Event).where(Event.tenant == tenant)
    )
    total_alerts = await session.execute(
        select(func.count()).select_from(Alert).where(Alert.tenant == tenant)
    )
    total_rules = await session.execute(
        select(func.count()).select_from(AlertRule).where(AlertRule.tenant == tenant)
    )
    total_users = await session.execute(
        select(func.count()).select_from(User).where(User.tenant == tenant)
    )
    
    return {
        "data": {
            "allLogs": total_events.scalar() or 0,
            "allUsers": total_users.scalar() or 0,
            "allAlerts": total_alerts.scalar() or 0,
            "allRules": total_rules.scalar() or 0,
        }
    }