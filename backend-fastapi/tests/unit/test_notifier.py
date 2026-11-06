"""Unit tests for notifier.py - webhook delivery with retries."""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch

import sys
sys.path.insert(0, '/home/nay/projects/logs/Logs-Manager/backend-fastapi')

from app.services.notifier import (
    build_webhook_payload,
    send_webhook,
    append_notification,
    DEFAULT_RETRY_DELAYS,
)


class TestBuildWebhookPayload:
    """Tests for webhook payload construction."""

    def test_build_payload_basic(self):
        """Test basic payload structure."""
        payload = build_webhook_payload(
            alert_id="abc123",
            rule={"name": "Test Rule", "conditions": []},
            tenant="demoa",
            severity="critical",
            group_value="192.168.1.1",
            count=5,
            window_minutes=5,
            first_seen="2025-08-20T10:00:00Z",
            last_seen="2025-08-20T10:03:00Z",
            link="https://app.example.com/alerts/abc123",
        )
        assert payload["alert_id"] == "abc123"
        assert payload["tenant"] == "demoa"
        assert payload["severity"] == "critical"
        assert payload["count"] == 5
        assert payload["group"] == "192.168.1.1"

    def test_build_payload_includes_notified_at(self):
        """Test payload includes notified_at timestamp."""
        payload = build_webhook_payload(
            alert_id="test",
            rule={},
            tenant="test",
            severity="low",
            group_value="test",
            count=1,
            window_minutes=1,
            first_seen="2025-08-20T10:00:00Z",
            last_seen="2025-08-20T10:01:00Z",
            link="http://test",
        )
        assert "notified_at" in payload


class TestSendWebhook:
    """Tests for webhook delivery with retries."""

    def test_send_webhook_success_first_attempt(self):
        """HTTP 200 on first attempt returns single record."""
        async def run_test():
            with patch("app.services.notifier.httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_resp = AsyncMock()
                mock_resp.is_success = True
                mock_resp.status_code = 200
                mock_resp.text = ""
                mock_client.__aenter__.return_value.post.return_value = mock_resp
                mock_client_class.return_value = mock_client

                attempts = await send_webhook(
                    webhook_url="http://webhook.test/alert",
                    payload={"test": "data"},
                    retries=3,
                    retry_delays=(0.01, 0.01, 0.01),
                )
                assert len(attempts) == 1
                assert attempts[0]["status"] == "sent"
                assert attempts[0]["http_code"] == 200

        asyncio.run(run_test())

    def test_send_webhook_retries_on_failure(self):
        """Failed HTTP 500 triggers retries with correct delays."""
        async def run_test():
            with patch("app.services.notifier.httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_resp = AsyncMock()
                mock_resp.is_success = False
                mock_resp.status_code = 500
                mock_resp.text = "Internal Server Error"
                mock_client.__aenter__.return_value.post.return_value = mock_resp
                mock_client_class.return_value = mock_client

                attempts = await send_webhook(
                    webhook_url="http://webhook.test/alert",
                    payload={"test": "data"},
                    retries=3,
                    retry_delays=(0.01, 0.01, 0.01),
                )
                assert len(attempts) == 3
                assert all(a["status"] == "failed" for a in attempts)
                assert attempts[0]["http_code"] == 500
                assert attempts[1]["http_code"] == 500
                assert attempts[2]["http_code"] == 500

        asyncio.run(run_test())

    def test_send_webhook_timeout_retry(self):
        """Timeout triggers retry."""
        async def run_test():
            import httpx
            with patch("app.services.notifier.httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value.post.side_effect = [
                    httpx.TimeoutException("timeout"),
                    AsyncMock(is_success=True, status_code=200, text=""),
                ]
                mock_client_class.return_value = mock_client

                attempts = await send_webhook(
                    webhook_url="http://webhook.test/alert",
                    payload={"test": "data"},
                    retries=3,
                    retry_delays=(0.01, 0.01, 0.01),
                )
                assert len(attempts) == 2
                assert attempts[0]["status"] == "failed"
                assert attempts[1]["status"] == "sent"

        asyncio.run(run_test())


class TestAppendNotification:
    """Tests for notification record appending."""

    def test_append_notification_first(self):
        """First notification creates new list."""
        result = append_notification(None, "webhook", [], "http://test")
        assert len(result) == 1
        assert result[0]["channel"] == "webhook"
        assert result[0]["target"] == "http://test"
        assert result[0]["final_status"] in ("sent", "failed")

    def test_append_notification_appends(self):
        """Subsequent notifications append to existing list."""
        existing = [{"id": "abc123", "channel": "email", "attempts": [{"status": "sent"}]}]
        result = append_notification(existing, "webhook", [{"status": "sent", "http_code": 200}], "http://webhook")
        assert len(result) == 2
        assert result[1]["channel"] == "webhook"

    def test_append_notification_tracks_all_attempts(self):
        """Notification includes all attempt records."""
        attempts = [
            {"attempt": 1, "status": "failed", "http_code": None, "error": "timeout"},
            {"attempt": 2, "status": "sent", "http_code": 200, "error": None},
        ]
        result = append_notification(None, "webhook", attempts, "http://test")
        assert len(result[0]["attempts"]) == 2

    def test_append_notification_final_status_sent(self):
        """Final status is 'sent' when last attempt succeeds."""
        attempts = [{"attempt": 1, "status": "sent", "http_code": 200, "error": None}]
        result = append_notification(None, "webhook", attempts, "http://test")
        assert result[0]["final_status"] == "sent"

    def test_append_notification_final_status_failed(self):
        """Final status is 'failed' when all attempts fail."""
        attempts = [
            {"attempt": 1, "status": "failed", "http_code": 500, "error": "error"},
            {"attempt": 2, "status": "failed", "http_code": 500, "error": "error"},
        ]
        result = append_notification(None, "webhook", attempts, "http://test")
        assert result[0]["final_status"] == "failed"

    def test_append_notification_creates_id(self):
        """Notification includes a unique ID."""
        result = append_notification(None, "webhook", [{"status": "sent"}], "http://test")
        assert "id" in result[0]
        assert len(result[0]["id"]) > 0

    def test_append_notification_includes_created_at(self):
        """Notification includes creation timestamp."""
        result = append_notification(None, "webhook", [{"status": "sent"}], "http://test")
        assert "created_at" in result[0]