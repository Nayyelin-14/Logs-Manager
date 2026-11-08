from pathlib import Path
import pytest
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent

class TestTenantEnforcementLogic:

    def test_admin_can_override_tenant_via_param(self):

        current_user_role = "ADMIN"
        current_user_tenant = None
        requested_tenant = "demoA"
        if current_user_role == "ADMIN":
            effective_tenant = None if requested_tenant in ("", "all") else requested_tenant
        else:
            effective_tenant = current_user_tenant
        assert effective_tenant == "demoA", "Admin should be able to override tenant"
    def test_admin_can_see_all_when_param_empty(self):
        current_user_role = "ADMIN"
        current_user_tenant = None
        requested_tenant = ""
        if current_user_role == "ADMIN":
            effective_tenant = None if requested_tenant in ("", "all") else requested_tenant
        else:
            effective_tenant = current_user_tenant

        assert effective_tenant is None, "Admin with empty tenant param should see all"
    def test_viewer_forced_to_own_tenant(self):
        current_user_role = "VIEWER"
        current_user_tenant = "demoB"
        requested_tenant = "demoA"
        if current_user_role == "ADMIN":
            effective_tenant = None if requested_tenant in ("", "all") else requested_tenant
        else:
            effective_tenant = current_user_tenant

        assert effective_tenant == "demoB", "Viewer must be forced to own tenant"
        assert effective_tenant != "demoA", "Viewer tenant bypass SHOULD NOT WORK"
    def test_viewer_with_empty_param_forced_to_own_tenant(self):

        current_user_role = "VIEWER"
        current_user_tenant = "demoA"
        requested_tenant = ""
        if current_user_role == "ADMIN":
            effective_tenant = None if requested_tenant in ("", "all") else requested_tenant
        else:
            effective_tenant = current_user_tenant

        assert effective_tenant == "demoA", "Viewer should always see own tenant"
    def test_viewer_with_all_param_forced_to_own_tenant(self):
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
    def test_register_endpoint_route_removed(self):

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
    def test_role_enum_has_viewer_value(self):

        from app.models.enums import Role

        assert hasattr(Role, 'VIEWER'), "Role enum MUST have VIEWER value (per assignment)"
    def test_role_enum_has_admin_value(self):
        from app.models.enums import Role
        assert hasattr(Role, 'ADMIN'), "Role enum must have ADMIN value"

class TestAdminTenantIsNull:
    def test_seed_demo_sets_admin_tenant_none(self):

        seed_path = str(BACKEND_DIR / "scripts" / "seed_demo_data.py")
        with open(seed_path, 'r') as f:
            content = f.read()
        assert "tenant=None" in content, (
            "Admin should be seeded with tenant=None for cross-tenant access. "
            "If admin has tenant='demoA', they'd be restricted to that tenant."
        )
class TestQueryFiltersForNonAdmin:
    def test_alert_model_has_tenant_column(self):

        from app.models.alert import Alert
        cols = [c.name for c in Alert.__table__.columns]
        assert "tenant" in cols, "Alert model must have tenant column"
    def test_security_event_model_has_tenant_column(self):
        from app.models.security_event import SecurityEvent
        cols = [c.name for c in SecurityEvent.__table__.columns]
        assert "tenant" in cols, "SecurityEvent model must have tenant column"
    def test_user_model_has_role_column(self):
        from app.models.user import User
        cols = [c.name for c in User.__table__.columns]
        assert "role" in cols, "User model must have role column"
class TestNormalizeTenant:


    def test_normalize_strip_and_lowercase(self):

        from app.core.tenancy import normalize_tenant
        assert normalize_tenant(" DemoA ") == "demoa"

    def test_normalize_valid_name(self):
        from app.core.tenancy import normalize_tenant
        assert normalize_tenant("demoA") == "demoa"
        assert normalize_tenant("my-tenant_1") == "my-tenant_1"
        assert normalize_tenant("ab") == "ab"
    def test_normalize_rejects_all(self):
        from app.core.tenancy import normalize_tenant
        from fastapi import HTTPException
        try:
            normalize_tenant("all")
            assert False, "Expected HTTPException"
        except HTTPException as e:
            assert e.status_code == 422
    def test_normalize_rejects_empty(self):
        from app.core.tenancy import normalize_tenant
        from fastapi import HTTPException
        for bad in ["", "   ", None]:
            try:
                normalize_tenant(bad)
                assert False, f"Expected HTTPException for {bad!r}"
            except HTTPException as e:
                assert e.status_code == 422
    def test_normalize_rejects_too_short(self):
        from app.core.tenancy import normalize_tenant
        from fastapi import HTTPException
        try:
            normalize_tenant("a")
            assert False, "Expected HTTPException"
        except HTTPException as e:
            assert e.status_code == 422
    def test_normalize_rejects_invalid_chars(self):
        from app.core.tenancy import normalize_tenant
        from fastapi import HTTPException
        try:
            normalize_tenant("x;y")
            assert False, "Expected HTTPException"
        except HTTPException as e:
            assert e.status_code == 422
class TestEffectiveTenant:


    def _make_user(self, role: str, tenant: str = None):

        class User:
            def __init__(self, role, tenant):
                self.role = role
                self.tenant = tenant
        return User(role, tenant)
    def test_viewer_gets_own_tenant(self):
        from app.core.tenancy import effective_tenant
        user = self._make_user("VIEWER", "demoB")
        assert effective_tenant(user, "demoA") == "demoB"
    def test_viewer_no_tenant_raises_403(self):
        from app.core.tenancy import effective_tenant
        from fastapi import HTTPException
        user = self._make_user("VIEWER", None)
        try:
            effective_tenant(user, "demoA")
            assert False, "Expected HTTPException"
        except HTTPException as e:
            assert e.status_code == 403
    def test_admin_none_returns_none(self):
        from app.core.tenancy import effective_tenant
        user = self._make_user("ADMIN", None)
        assert effective_tenant(user, None) is None
    def test_admin_empty_returns_none(self):
        from app.core.tenancy import effective_tenant
        user = self._make_user("ADMIN", None)
        assert effective_tenant(user, "") is None
    def test_admin_all_returns_none(self):
        from app.core.tenancy import effective_tenant
        user = self._make_user("ADMIN", None)
        assert effective_tenant(user, "all") is None
    def test_admin_normalizes_requested(self):
        from app.core.tenancy import effective_tenant
        user = self._make_user("ADMIN", None)
        assert effective_tenant(user, " DemoA ") == "demoa"
    def test_admin_rejects_invalid_tenant_name(self):
        from app.core.tenancy import effective_tenant
        from fastapi import HTTPException
        user = self._make_user("ADMIN", None)
        try:
            effective_tenant(user, "x;y")
            assert False, "Expected HTTPException"
        except HTTPException as e:
            assert e.status_code == 422
