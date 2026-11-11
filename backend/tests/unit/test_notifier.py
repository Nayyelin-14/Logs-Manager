import asyncio
import pytest
from unittest.mock import AsyncMock, patch

from app.services.notifier import (
    build_webhook_payload,
    send_webhook,
    append_notification,
    DEFAULT_RETRY_DELAYS,
    _resolve_retry_delays,
)


class TestBuildWebhookPayload:

    def test_build_payload_basic(self):
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

    def test_send_webhook_success_first_attempt(self):
        async def run_test():
            with patch("app.services.notifier.validate_webhook_url"), \
                 patch("app.services.notifier.httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_resp = AsyncMock()
                mock_resp.is_success = True
                mock_resp.status_code = 200
                mock_resp.text = ""
                mock_resp.content = b""
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
        async def run_test():
            with patch("app.services.notifier.validate_webhook_url"), \
                 patch("app.services.notifier.httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_resp = AsyncMock()
                mock_resp.is_success = False
                mock_resp.status_code = 500
                mock_resp.text = "Internal Server Error"
                mock_resp.content = b""
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
        async def run_test():
            import httpx
            with patch("app.services.notifier.validate_webhook_url"), \
                 patch("app.services.notifier.httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                success_resp = AsyncMock(is_success=True, status_code=200, text="")
                success_resp.content = b""
                mock_client.__aenter__.return_value.post.side_effect = [
                    httpx.TimeoutException("timeout"),
                    success_resp,
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

    def test_send_webhook_blocked_destination_is_not_retried(self):
        from app.core.webhook_security import WebhookUrlError

        async def run_test():
            with patch(
                "app.services.notifier.validate_webhook_url",
                side_effect=WebhookUrlError("private or reserved IP address"),
            ), patch("app.services.notifier.httpx.AsyncClient") as mock_client_class:
                attempts = await send_webhook(
                    webhook_url="http://127.0.0.1/alert",
                    payload={"test": "data"},
                    retries=3,
                    retry_delays=(0.01, 0.01, 0.01),
                )
                mock_client_class.assert_not_called()
                assert len(attempts) == 1
                assert attempts[0]["status"] == "failed"
                assert "blocked destination" in attempts[0]["error"]

        asyncio.run(run_test())

        asyncio.run(run_test())


class TestResolveRetryDelays:

    def test_explicit_delays_override_env(self, monkeypatch):
        monkeypatch.setenv("WEBHOOK_RETRY_DELAYS", "1.0,2.0,3.0")
        assert _resolve_retry_delays((0.1, 0.2)) == (0.1, 0.2)

    def test_env_valid(self, monkeypatch):
        monkeypatch.setenv("WEBHOOK_RETRY_DELAYS", "0,0,0")
        assert _resolve_retry_delays(None) == (0.0, 0.0, 0.0)

    def test_env_empty_falls_back(self, monkeypatch):
        monkeypatch.setenv("WEBHOOK_RETRY_DELAYS", "")
        assert _resolve_retry_delays(None) == DEFAULT_RETRY_DELAYS

    def test_env_whitespace_only_falls_back(self, monkeypatch):
        monkeypatch.setenv("WEBHOOK_RETRY_DELAYS", "   ")
        assert _resolve_retry_delays(None) == DEFAULT_RETRY_DELAYS

    def test_env_non_numeric_falls_back(self, monkeypatch):
        monkeypatch.setenv("WEBHOOK_RETRY_DELAYS", "a,b,c")
        assert _resolve_retry_delays(None) == DEFAULT_RETRY_DELAYS

    def test_env_negative_falls_back(self, monkeypatch):
        monkeypatch.setenv("WEBHOOK_RETRY_DELAYS", "-1.0,2.0,3.0")
        assert _resolve_retry_delays(None) == DEFAULT_RETRY_DELAYS

    def test_env_unset_falls_back(self, monkeypatch):
        monkeypatch.delenv("WEBHOOK_RETRY_DELAYS", raising=False)
        assert _resolve_retry_delays(None) == DEFAULT_RETRY_DELAYS

    def test_env_read_at_call_time(self, monkeypatch):
        monkeypatch.setenv("WEBHOOK_RETRY_DELAYS", "1.0,1.0,1.0")
        assert _resolve_retry_delays(None) == (1.0, 1.0, 1.0)
        monkeypatch.setenv("WEBHOOK_RETRY_DELAYS", "2.0,2.0,2.0")
        assert _resolve_retry_delays(None) == (2.0, 2.0, 2.0)


class TestAppendNotification:

    def test_append_notification_first(self):
        result = append_notification(None, "webhook", [], "http://test")
        assert len(result) == 1
        assert result[0]["channel"] == "webhook"
        assert result[0]["target"] == "http://test"
        assert result[0]["final_status"] in ("sent", "failed")

    def test_append_notification_appends(self):
        existing = [{"id": "abc123", "channel": "email", "attempts": [{"status": "sent"}]}]
        result = append_notification(existing, "webhook", [{"status": "sent", "http_code": 200}], "http://webhook")
        assert len(result) == 2
        assert result[1]["channel"] == "webhook"

    def test_append_notification_tracks_all_attempts(self):
        attempts = [
            {"attempt": 1, "status": "failed", "http_code": None, "error": "timeout"},
            {"attempt": 2, "status": "sent", "http_code": 200, "error": None},
        ]
        result = append_notification(None, "webhook", attempts, "http://test")
        assert len(result[0]["attempts"]) == 2

    def test_append_notification_final_status_sent(self):
        attempts = [{"attempt": 1, "status": "sent", "http_code": 200, "error": None}]
        result = append_notification(None, "webhook", attempts, "http://test")
        assert result[0]["final_status"] == "sent"

    def test_append_notification_final_status_failed(self):
        attempts = [
            {"attempt": 1, "status": "failed", "http_code": 500, "error": "error"},
            {"attempt": 2, "status": "failed", "http_code": 500, "error": "error"},
        ]
        result = append_notification(None, "webhook", attempts, "http://test")
        assert result[0]["final_status"] == "failed"

    def test_append_notification_creates_id(self):
        result = append_notification(None, "webhook", [{"status": "sent"}], "http://test")
        assert "id" in result[0]
        assert len(result[0]["id"]) > 0

    def test_append_notification_includes_created_at(self):
        result = append_notification(None, "webhook", [{"status": "sent"}], "http://test")
        assert "created_at" in result[0]
