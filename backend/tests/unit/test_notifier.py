import asyncio
import pytest
from unittest.mock import AsyncMock, patch

from app.services.notifier import (
    build_webhook_payload,
    send_webhook,
    append_notification,
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

        asyncio.run(run_test())

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

