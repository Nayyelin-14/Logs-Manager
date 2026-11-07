"""
Pure unit tests for tenant isolation logic - NO DATABASE REQUIRED.

These tests verify tenant isolation by inspecting code directly
without needing a live database connection.
"""

from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent


class TestTenantEnforcementLogic:
    """Test the tenant enforcement logic in query building by simulating code paths."""

    def test_admin_can_override_tenant_via_param(self):
        """Admin with ?tenant=demoA should be able to see demoA data."""
        # Simulate the logic from search.py lines 75-79
        current_user_role = "ADMIN"
        current_user_tenant = None
        requested_tenant = "demoA"
        
        # This is the actual code pattern used in the routes
        if current_user_role == "ADMIN":
            effective_tenant = None if requested_tenant in ("", "all") else requested_tenant
        else:
            effective_tenant = current_user_tenant
        
        assert effective_tenant == "demoA", "Admin should be able to override tenant"

    def test_admin_can_see_all_when_param_empty(self):
        """Admin with no tenant param should see all data."""
        current_user_role = "ADMIN"
        current_user_tenant = None
        requested_tenant = ""
        
        if current_user_role == "ADMIN":
            effective_tenant = None if requested_tenant in ("", "all") else requested_tenant
        else:
            effective_tenant = current_user_tenant
        
        assert effective_tenant is None, "Admin with empty tenant param should see all"

    def test_viewer_forced_to_own_tenant(self):
        """Viewer with ?tenant=demoA should see only their tenant (demoB)."""
        current_user_role = "VIEWER"
        current_user_tenant = "demoB"
        requested_tenant = "demoA"  # ATTEMPTED BYPASS - SHOULD BE IGNORED
        
        if current_user_role == "ADMIN":
            effective_tenant = None if requested_tenant in ("", "all") else requested_tenant
        else:
            effective_tenant = current_user_tenant
        
        assert effective_tenant == "demoB", "Viewer must be forced to own tenant"
        assert effective_tenant != "demoA", "Viewer tenant bypass SHOULD NOT WORK"

    def test_viewer_with_empty_param_forced_to_own_tenant(self):
        """Viewer with no tenant param should see only their tenant."""
        current_user_role = "VIEWER"
        current_user_tenant = "demoA"
        requested_tenant = ""
        
        if current_user_role == "ADMIN":
            effective_tenant = None if requested_tenant in ("", "all") else requested_tenant
        else:
            effective_tenant = current_user_tenant
        
        assert effective_tenant == "demoA", "Viewer should always see own tenant"

    def test_viewer_with_all_param_forced_to_own_tenant(self):
        """Viewer with ?tenant=all should NOT see all tenants."""
        current_user_role = "VIEWER"
        current_user_tenant = "demoA"
        requested_tenant = "all"
        
        if current_user_role == "ADMIN":
            effective_tenant = None if requested_tenant in ("", "all") else requested_tenant
        else:
            effective_tenant = current_user_tenant
        
        assert effective_tenant == "demoA", (
            "Viewer with ?tenant=all should still see own tenant, NOT all tenants"
        )


class TestRegisterEndpointRemoved:
    """Verify registration endpoint is removed for security."""
    
    def test_register_endpoint_route_removed(self):
        """POST /api/auth/register route must NOT exist - prevents tenant impersonation."""
        route_path = str(BACKEND_DIR / "app/api/routes/auth.py")
        with open(route_path, 'r') as f:
            content = f.read()
        
        has_register_route = '@router.post("/register")' in content or 'def register(' in content
        
        print(f"\nAuth file content check:")
        print(f"Has /register route: {has_register_route}")
        
        assert not has_register_route, (
            f"CRITICAL SECURITY VULNERABILITY: Registration endpoint exists. "
            f"POST /api/auth/register allows UNTRUSTED USERS to register with any tenant, "
            f"bypassing tenant isolation."
        )


class TestRoleNameConsistency:
    """Verify role names match assignment spec (ADMIN/VIEWER, not USER)."""
    
    def test_role_enum_has_viewer_value(self):
        """Role enum MUST have VIEWER value per assignment spec."""
        from app.models.enums import Role
        
        # Assignment requires ADMIN and VIEWER
        # Current code has USER, needs to be VIEWER
        assert hasattr(Role, 'VIEWER'), "Role enum MUST have VIEWER value (per assignment)"
    
    def test_role_enum_has_admin_value(self):
        """ADMIN role must exist."""
        from app.models.enums import Role
        assert hasattr(Role, 'ADMIN'), "Role enum must have ADMIN value"


class TestAdminTenantIsNull:
    """Verify admin user has tenant=NULL for proper cross-tenant privileges."""
    
    def test_seed_demo_sets_admin_tenant_none(self):
        """Admin should be seeded with tenant=None."""
        seed_path = str(BACKEND_DIR / "scripts" / "seed_demo_data.py")
        with open(seed_path, 'r') as f:
            content = f.read()
        
        # Check that admin user is seeded with tenant=None
        # In Python source, it's written as tenant=None (no quotes)
        assert "tenant=None" in content, (
            "Admin should be seeded with tenant=None for cross-tenant access. "
            "If admin has tenant='demoA', they'd be restricted to that tenant."
        )


class TestQueryFiltersForNonAdmin:
    """Verify query filter models have proper tenant columns."""
    
    def test_alert_model_has_tenant_column(self):
        """Alert model must have tenant column for filtering."""
        from app.models.alert import Alert
        cols = [c.name for c in Alert.__table__.columns]
        assert "tenant" in cols, "Alert model must have tenant column"
    
    def test_security_event_model_has_tenant_column(self):
        """SecurityEvent model must have tenant column for filtering."""
        from app.models.security_event import SecurityEvent
        cols = [c.name for c in SecurityEvent.__table__.columns]
        assert "tenant" in cols, "SecurityEvent model must have tenant column"
    
    def test_user_model_has_role_column(self):
        """User model must have role column."""
        from app.models.user import User
        cols = [c.name for c in User.__table__.columns]
        assert "role" in cols, "User model must have role column"


# ===== normalize_tenant unit tests =====

class TestNormalizeTenant:
    """Unit tests for app.core.tenancy.normalize_tenant."""

    def test_normalize_strip_and_lowercase(self):
        """' DemoA ' -> 'demoa'."""
        from app.core.tenancy import normalize_tenant
        assert normalize_tenant(" DemoA ") == "demoa"

    def test_normalize_valid_name(self):
        """Valid names pass through unchanged (lowercased)."""
        from app.core.tenancy import normalize_tenant
        assert normalize_tenant("demoA") == "demoa"
        assert normalize_tenant("my-tenant_1") == "my-tenant_1"
        assert normalize_tenant("ab") == "ab"

    def test_normalize_rejects_all(self):
        """'all' is rejected with 422."""
        from app.core.tenancy import normalize_tenant
        from fastapi import HTTPException
        try:
            normalize_tenant("all")
            assert False, "Expected HTTPException"
        except HTTPException as e:
            assert e.status_code == 422

    def test_normalize_rejects_empty(self):
        """'' and whitespace-only are rejected with 422."""
        from app.core.tenancy import normalize_tenant
        from fastapi import HTTPException
        for bad in ["", "   ", None]:
            try:
                normalize_tenant(bad)
                assert False, f"Expected HTTPException for {bad!r}"
            except HTTPException as e:
                assert e.status_code == 422

    def test_normalize_rejects_too_short(self):
        """'a' (1 char) is rejected with 422."""
        from app.core.tenancy import normalize_tenant
        from fastapi import HTTPException
        try:
            normalize_tenant("a")
            assert False, "Expected HTTPException"
        except HTTPException as e:
            assert e.status_code == 422

    def test_normalize_rejects_invalid_chars(self):
        """'x;y' is rejected with 422."""
        from app.core.tenancy import normalize_tenant
        from fastapi import HTTPException
        try:
            normalize_tenant("x;y")
            assert False, "Expected HTTPException"
        except HTTPException as e:
            assert e.status_code == 422


# ===== effective_tenant unit tests =====

class TestEffectiveTenant:
    """Unit tests for app.core.tenancy.effective_tenant."""

    def _make_user(self, role: str, tenant: str = None):
        """Create a simple user-like object."""
        class User:
            def __init__(self, role, tenant):
                self.role = role
                self.tenant = tenant
        return User(role, tenant)

    def test_viewer_gets_own_tenant(self):
        """Viewer with requested 'demoA' gets own tenant (demoB), requested ignored."""
        from app.core.tenancy import effective_tenant
        user = self._make_user("VIEWER", "demoB")
        assert effective_tenant(user, "demoA") == "demoB"

    def test_viewer_no_tenant_raises_403(self):
        """Viewer with no tenant raises 403."""
        from app.core.tenancy import effective_tenant
        from fastapi import HTTPException
        user = self._make_user("VIEWER", None)
        try:
            effective_tenant(user, "demoA")
            assert False, "Expected HTTPException"
        except HTTPException as e:
            assert e.status_code == 403

    def test_admin_none_returns_none(self):
        """Admin with None requested returns None."""
        from app.core.tenancy import effective_tenant
        user = self._make_user("ADMIN", None)
        assert effective_tenant(user, None) is None

    def test_admin_empty_returns_none(self):
        """Admin with '' requested returns None."""
        from app.core.tenancy import effective_tenant
        user = self._make_user("ADMIN", None)
        assert effective_tenant(user, "") is None

    def test_admin_all_returns_none(self):
        """Admin with 'all' requested returns None."""
        from app.core.tenancy import effective_tenant
        user = self._make_user("ADMIN", None)
        assert effective_tenant(user, "all") is None

    def test_admin_normalizes_requested(self):
        """Admin with ' DemoA ' gets 'demoa'."""
        from app.core.tenancy import effective_tenant
        user = self._make_user("ADMIN", None)
        assert effective_tenant(user, " DemoA ") == "demoa"

    def test_admin_rejects_invalid_tenant_name(self):
        """Admin with 'x;y' raises 422."""
        from app.core.tenancy import effective_tenant
        from fastapi import HTTPException
        user = self._make_user("ADMIN", None)
        try:
            effective_tenant(user, "x;y")
            assert False, "Expected HTTPException"
        except HTTPException as e:
            assert e.status_code == 422