import re
from typing import Optional

from fastapi import HTTPException, status

_TENANT_NAME_RE = re.compile(r"^[a-z0-9_-]{2,50}$")


def normalize_tenant(value: str) -> str:
    """Validate and canonicalize a tenant name.

    Empty, wildcard/reserved and malformed values are rejected with 422 so an
    empty tenant can never be treated as a wildcard by accident.
    """

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


def tenant_key(value: Optional[str]) -> str:
    """Comparison key for tenant values without applying validation."""

    return (value or "").strip().lower()


def role_value(user) -> Optional[str]:
    role = getattr(user, "role", None)
    return role.value if hasattr(role, "value") else role


def is_platform_admin(user) -> bool:
    """An ADMIN without a tenant is a platform administrator.

    Admins created inside a tenant are tenant-bound and must not manage other
    tenants. VIEWERs are always bound to their own tenant.
    """

    return role_value(user) == "ADMIN" and not tenant_key(getattr(user, "tenant", None))


def resolve_read_tenant(user, requested: Optional[str] = None) -> Optional[str]:
    """Resolve the tenant filter for read endpoints.

    ``None`` means "all tenants" and is reserved for platform admins. Any
    non-platform account without a tenant receives 403 instead of an unscoped
    query, so an empty tenant can never act as a wildcard.
    """

    if is_platform_admin(user):
        requested_key = tenant_key(requested)
        if requested_key in ("", "all"):
            return None
        return normalize_tenant(requested)

    tenant = getattr(user, "tenant", None)
    if not tenant_key(tenant):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not assigned to a tenant",
        )
    return tenant


def effective_tenant(user, requested=None):
    """Backwards-compatible alias for :func:`resolve_read_tenant`."""

    return resolve_read_tenant(user, requested)
