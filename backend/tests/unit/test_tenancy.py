"""Tenant resolution unit checks.

Calls the real tenancy helpers instead of re-implementing their logic in the
test, so a regression in role or tenant handling fails the test.
"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core.tenancy import normalize_tenant, resolve_read_tenant


def test_tenant_resolution_and_validation():
    viewer = SimpleNamespace(role="VIEWER", tenant="demoa")
    assert resolve_read_tenant(viewer, "demob") == "demoa"

    admin = SimpleNamespace(role="ADMIN", tenant=None)
    assert resolve_read_tenant(admin, None) is None
    assert resolve_read_tenant(admin, "all") is None
    assert resolve_read_tenant(admin, "Demob") == "demob"

    assert normalize_tenant(" DemoA ") == "demoa"

    for bad in ("all", "", "x", "bad;name"):
        with pytest.raises(HTTPException):
            normalize_tenant(bad)
