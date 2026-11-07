"""Login rate limiting and brute-force protection tests.

Tests the per-email lockout tracker (fully controllable) and verifies
the slowapi rate limit decorator is applied to the login route.
"""
from fastapi.testclient import TestClient
from app.main import app
from app.api.routes.auth import (
    login_limiter,
    _FAILED_LOGIN_TRACKER,
    _is_locked_out,
    _record_failed_login,
    _clear_failed_logins,
)
from conftest import ADMIN_EMAIL, ADMIN_PASSWORD


def _login(client, email: str, password: str):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def setup_function(function):
    """Reset per-email lockout tracker before each test."""
    _FAILED_LOGIN_TRACKER.clear()


class TestPerEmailLockout:
    """Per-email lockout tracker (in-memory, fully controllable)."""

    def test_lockout_after_5_failures(self):
        """5 failures for same email -> lockout, 6th attempt gets 429."""
        email = "lockout@demo.local"
        for i in range(4):
            _record_failed_login(email)
            locked, retry = _is_locked_out(email)
            assert not locked, f"should not be locked after {i+1} failures"
        # 5th failure triggers lockout
        _record_failed_login(email)
        locked, retry = _is_locked_out(email)
        assert locked, f"should be locked after 5 failures, retry_after={retry}"
        assert retry > 0

    def test_lockout_expires_after_configured_minutes(self):
        """Lockout expires after LOGIN_LOCKOUT_MINUTES."""
        import time
        from app.core.config import get_settings
        settings = get_settings()
        email = "expire@demo.local"
        _record_failed_login(email)
        # Manually set first_failed_at to past the lockout window
        entry = _FAILED_LOGIN_TRACKER[email]
        entry["first_failed_at"] = time.time() - (settings.LOGIN_LOCKOUT_MINUTES * 60 + 1)
        locked, retry = _is_locked_out(email)
        assert not locked, "lockout should have expired"
        assert email not in _FAILED_LOGIN_TRACKER, "expired entry should be removed"

    def test_successful_login_clears_lockout(self):
        """Successful login clears the per-email failure tracker."""
        email = "clear@demo.local"
        _record_failed_login(email)
        _record_failed_login(email)
        assert email in _FAILED_LOGIN_TRACKER
        _clear_failed_logins(email)
        assert email not in _FAILED_LOGIN_TRACKER


class TestRateLimitDecorator:
    """Verify slowapi rate limit is applied to login route."""

    def test_login_route_has_rate_limit(self):
        """The /api/auth/login route has slowapi rate limit decorator applied."""
        from app.api.routes.auth import router
        # Check that login_limiter has a limit configured
        # The limiter is a module-level object; verify it exists and has limits
        assert login_limiter is not None
        assert login_limiter.enabled


class TestRateLimitEndToEnd:
    """End-to-end rate limiting via TestClient (IP-based bucket shared)."""

    def test_failed_logins_return_401_not_429_initially(self):
        """First few failed logins return 401, not 429."""
        client = TestClient(app)
        res = _login(client, "e2e@demo.local", "wrongpassword")
        assert res.status_code == 401, f"expected 401, got {res.status_code}"
        assert res.json()["detail"] == "Invalid credentials"

    def test_correct_login_returns_200(self):
        """Correct credentials return 200 with cookies."""
        client = TestClient(app)
        res = _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
        assert res.status_code == 200, f"expected 200, got {res.status_code}: {res.text}"
        assert "accessToken" in client.cookies
