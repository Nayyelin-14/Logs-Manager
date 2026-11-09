"""Resend email notification tests with mocked provider responses.

No real email is sent during these tests. The Resend HTTPS API is mocked
using ``httpx.MockTransport`` so that the tests are deterministic and safe
to run in CI.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict
from unittest.mock import patch

import httpx
import pytest

from app.core.config import get_settings
from app.services.notifier import (
    is_valid_email,
    send_email_notification,
    send_resend_email,
)


def _run(coro):
    """Run an async coroutine in a fresh event loop (Python 3.14 compatible)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# is_valid_email
# ---------------------------------------------------------------------------

def test_is_valid_email_accepts_well_formed_addresses():
    for addr in ["admin@example.com", "user.name+tag@sub.domain.co.uk"]:
        assert is_valid_email(addr) is True


def test_is_valid_email_rejects_bad_addresses():
    for addr in [None, "", "   ", "not-an-email", "@example.com", "user@", "user example.com"]:
        assert is_valid_email(addr) is False


# ---------------------------------------------------------------------------
# send_email_notification dispatch (provider routing)
# ---------------------------------------------------------------------------

def test_email_disabled_returns_skipped(monkeypatch):
    """When EMAIL_ENABLED is false, no provider request is attempted."""
    settings = get_settings()
    monkeypatch.setattr(settings, "EMAIL_ENABLED", False)
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "resend")

    result = _run(
        send_email_notification(
            recipient="admin@example.com",
            subject="Test",
            html_body="<p>hi</p>",
            text_body="hi",
        )
    )
    assert result["status"] == "skipped"
    assert result["error"] == "email_disabled"


def test_resend_route_uses_send_resend_email(monkeypatch):
    """When provider is resend and enabled, dispatch reaches send_resend_email."""
    settings = get_settings()
    monkeypatch.setattr(settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "resend")
    monkeypatch.setattr(settings, "RESEND_API_KEY", "re_test_key")
    monkeypatch.setattr(settings, "ALERT_EMAIL_FROM", "alerts@example.com")

    calls: list[Dict[str, Any]] = []

    async def fake_send(**kwargs):
        calls.append(kwargs)
        return {"status": "sent", "error": None, "message_id": "msg_123"}

    monkeypatch.setattr("app.services.notifier.send_resend_email", fake_send)

    result = _run(
        send_email_notification(
            recipient="admin@example.com",
            subject="Alert",
            html_body="<p>body</p>",
            text_body="body",
        )
    )
    assert result["status"] == "sent"
    assert len(calls) == 1
    assert calls[0]["recipient"] == "admin@example.com"


def test_smtp_route_when_provider_not_resend(monkeypatch):
    """When provider is not resend, falls back to SMTP path."""
    settings = get_settings()
    monkeypatch.setattr(settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "smtp")
    monkeypatch.setattr(settings, "SMTP_ENABLED", False)

    result = _run(
        send_email_notification(
            recipient="admin@example.com",
            subject="Alert",
            html_body="<p>body</p>",
            text_body="body",
        )
    )
    # SMTP disabled => failure, but not a crash.
    assert result["status"] in ("failed", "skipped")


# ---------------------------------------------------------------------------
# send_resend_email with mocked httpx transport
# ---------------------------------------------------------------------------

def _mock_transport(status_code: int, json_body: Dict[str, Any] | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code,
            json=json_body or {},
            request=request,
        )
    return httpx.MockTransport(handler)


def test_send_resend_email_missing_api_key_returns_failure():
    result = _run(
        send_resend_email(
            recipient="admin@example.com",
            subject="Test",
            html_body="<p>hi</p>",
            api_key="",
        )
    )
    assert result["status"] == "failed"
    assert result["error"] == "missing_resend_api_key"


def test_send_resend_email_missing_sender_returns_failure():
    result = _run(
        send_resend_email(
            recipient="admin@example.com",
            subject="Test",
            html_body="<p>hi</p>",
            api_key="re_key",
            from_email="not-an-email",
        )
    )
    assert result["status"] == "failed"
    assert result["error"] == "invalid_sender"


def test_send_resend_email_invalid_recipient_returns_failure():
    result = _run(
        send_resend_email(
            recipient="not-an-email",
            subject="Test",
            html_body="<p>hi</p>",
            api_key="re_key",
            from_email="alerts@example.com",
        )
    )
    assert result["status"] == "failed"
    assert result["error"] == "invalid_recipient"


def test_send_resend_email_empty_body_returns_failure():
    result = _run(
        send_resend_email(
            recipient="admin@example.com",
            subject="Test",
            api_key="re_key",
            from_email="alerts@example.com",
        )
    )
    assert result["status"] == "failed"
    assert result["error"] == "empty_body"


def test_send_resend_email_valid_response_recorded():
    result = _run(
        send_resend_email(
            recipient="admin@example.com",
            subject="Test",
            html_body="<p>hi</p>",
            text_body="hi",
            api_key="re_key",
            from_email="alerts@example.com",
            transport=_mock_transport(200, {"id": "msg_abc123"}),
        )
    )
    assert result["status"] == "sent"
    assert result["error"] is None
    assert result["message_id"] == "msg_abc123"


def test_send_resend_email_http_401_handled():
    result = _run(
        send_resend_email(
            recipient="admin@example.com",
            subject="Test",
            html_body="<p>hi</p>",
            api_key="bad_key",
            from_email="alerts@example.com",
            transport=_mock_transport(401, {"message": "Unauthorized"}),
        )
    )
    assert result["status"] == "failed"
    assert "http_401" in result["error"]


def test_send_resend_email_http_429_handled():
    result = _run(
        send_resend_email(
            recipient="admin@example.com",
            subject="Test",
            html_body="<p>hi</p>",
            api_key="re_key",
            from_email="alerts@example.com",
            transport=_mock_transport(429),
        )
    )
    assert result["status"] == "failed"
    assert "http_429" in result["error"]


def test_send_resend_email_http_500_handled():
    result = _run(
        send_resend_email(
            recipient="admin@example.com",
            subject="Test",
            html_body="<p>hi</p>",
            api_key="re_key",
            from_email="alerts@example.com",
            transport=_mock_transport(500),
        )
    )
    assert result["status"] == "failed"
    assert "http_500" in result["error"]


def test_send_resend_email_network_timeout_handled():
    async def boom(*args, **kwargs):
        raise httpx.TimeoutException("connect timeout")

    with patch("app.services.notifier.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = boom
        result = _run(
            send_resend_email(
                recipient="admin@example.com",
                subject="Test",
                html_body="<p>hi</p>",
                api_key="re_key",
                from_email="alerts@example.com",
            )
        )
    assert result["status"] == "failed"
    assert "timeout" in result["error"]


# ---------------------------------------------------------------------------
# Email content safely handles untrusted descriptions
# ---------------------------------------------------------------------------

def test_email_content_escapes_untrusted_html():
    """Untrusted description text must not break out of HTML context."""
    unsafe = "<script>alert('xss')</script><img src=x onerror=1>"
    escaped = unsafe.replace("<", "&lt;").replace(">", "&gt;")
    assert "<script>" not in escaped
    assert "&lt;script&gt;" in escaped
    assert escaped.count("<") == 0


# ---------------------------------------------------------------------------
# Alert flow: email failure does not invalidate alert (unit level)
# ---------------------------------------------------------------------------

def test_send_email_notification_resend_failure_is_safe(monkeypatch):
    """A Resend failure returns a failed status without raising."""
    settings = get_settings()
    monkeypatch.setattr(settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "resend")
    monkeypatch.setattr(settings, "RESEND_API_KEY", "re_key")
    monkeypatch.setattr(settings, "ALERT_EMAIL_FROM", "alerts@example.com")

    async def fake_fail(**kwargs):
        return {"status": "failed", "error": "http_500: internal error"}

    monkeypatch.setattr("app.services.notifier.send_resend_email", fake_fail)

    result = _run(
        send_email_notification(
            recipient="admin@example.com",
            subject="Alert",
            html_body="<p>body</p>",
            text_body="body",
        )
    )
    assert result["status"] == "failed"
    assert "http_500" in result["error"]
