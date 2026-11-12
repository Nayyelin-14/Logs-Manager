from fastapi import APIRouter, Depends
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Dict, Any

from app.core.database import get_session
from app.core.dependencies import require_admin
from app.core.security import TokenPayload
from app.models.user import User

router = APIRouter()


@router.get("/users/{query}", response_model=dict)
async def get_users_infinite(
    query: str = " ",
    filters: Optional[Dict[str, Any]] = None,
    limit: int = 25,
    cursor: Optional[int] = None,
    session: AsyncSession = Depends(get_session),
    current_user: "TokenPayload" = Depends(require_admin),
):
    tenant = current_user.tenant

    query_stmt = select(User).where(User.tenant == tenant)

    if filters:
        if filters.get("role"):
            query_stmt = query_stmt.where(User.role == filters["role"])
        if filters.get("status"):
            query_stmt = query_stmt.where(User.status == filters["status"])
        if filters.get("date"):

            pass
        if filters.get("search"):
            search_term = f"%{filters['search']}%"
            query_stmt = query_stmt.where(
                (User.username.ilike(f"%{filters['search']}%")) |
                (User.email.ilike(f"%{filters['search']}%"))
            )

    query_stmt = query_stmt.order_by(desc(User.id)).limit(limit + 1)
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
