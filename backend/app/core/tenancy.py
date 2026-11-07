"""
Tenancy helpers — shared tenant name validation and resolution.

Used ONLY where a tenant name comes from external input:
- admin ?tenant= query parameter
- create-user / update-user tenant fields

Never used to override a viewer's JWT-bound tenant.
"""

import re
from fastapi import HTTPException, status

_TENANT_NAME_RE = re.compile(r"^[a-z0-9_-]{2,50}$")


def normalize_tenant(value: str) -> str:
    """Normalize and validate a tenant name from user input.

    Rules:
    - Strip whitespace and lowercase
    - Must match ^[a-z0-9_-]{2,50}$
    - "all" is rejected (reserved for admin "all tenants" semantics)
    - Empty is rejected

    Raises HTTPException(422) on invalid input.
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


def effective_tenant(user, requested=None):
    """Resolve the effective tenant for a user, enforcing role-based rules.

    - ADMIN: None if requested in (None, "", "all"), else normalize_tenant(requested)
    - VIEWER: always user.tenant (requested is ignored); 403 if no tenant
    """
    if user.role == "ADMIN":
        if requested is None or requested == "" or requested == "all":
            return None
        return normalize_tenant(requested)
    # VIEWER: always from JWT, never None
    if not user.tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Viewer has no tenant assigned",
        )
    return user.tenant