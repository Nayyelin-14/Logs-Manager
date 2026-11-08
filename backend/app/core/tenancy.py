import re
from fastapi import HTTPException, status
_TENANT_NAME_RE = re.compile(r"^[a-z0-9_-]{2,50}$")

def normalize_tenant(value: str) -> str:

    if value is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="tenant is required",
        )
    normalized = value.strip().lower()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="tenant must not be empty",
        )
    if normalized == "all":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="tenant name 'all' is reserved",
        )
    if not _TENANT_NAME_RE.match(normalized):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"tenant name '{normalized}' is invalid. "
                f"Must be 2-50 chars: lowercase letters, digits, underscore, hyphen."
            ),
        )
    return normalized
def effective_tenant(user, requested=None):
    if user.role == "ADMIN":
        if requested is None or requested == "" or requested == "all":
            return None
        return normalize_tenant(requested)
    if not user.tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Viewer has no tenant assigned",
        )
    return user.tenant
