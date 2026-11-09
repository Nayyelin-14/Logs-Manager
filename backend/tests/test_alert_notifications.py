"""Alert delivery tests: Resend retries, test endpoint, isolation, dedup.

All provider calls are mocked. No real email or webhook is sent.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.database import async_session_maker
from app.models.alert import Alert, AlertRule, EmailNotification, EmailStatus
from app.services.alerting.alerter import create_or_update_alert
from app.services.notifier import send_resend_email


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _sequence_transport(steps):
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        index = calls["count"]
        calls["count"] += 1
        step = steps[min(index, len(steps) - 1)]
        if isinstance(step, Exception):
            raise step
        return httpx.Response(step, json={}, request=request)

    return httpx.MockTransport(handler), calls


def _resend(**kwargs):
    defaults = {
        "recipient": "admin@example.com",
        "subject": "Test",
        "html_body": "<p>hi</p>",
        "text_body": "hi",
        "api_key": "re_test_key",
        "from_email": "alerts@example.com",
        "retry_delays": (0.0, 0.0),
    }
    defaults.update(kwargs)
    return _run(send_resend_email(**defaults))


# ---------------------------------------------------------------------------
# Resend retry policy
# ---------------------------------------------------------------------------

def test_resend_429_then_success_retries_and_succeeds():
    transport, calls = _sequence_transport([429, 200])
    result = _resend(transport=transport)

    assert result["status"] == "sent"
    assert calls["count"] == 2
    assert len(result["attempts"]) == 2
    assert result["attempts"][0]["http_code"] == 429
    assert result["attempts"][1]["http_code"] == 200


def test_resend_500_retries_max_three_times():
    transport, calls = _sequence_transport([500, 500, 500])
    result = _resend(transport=transport)

    assert result["status"] == "failed"
    assert calls["count"] == 3
    assert len(result["attempts"]) == 3
    assert "http_500" in result["error"]


def test_resend_timeout_retries_max_three_times():
    transport, calls = _sequence_transport(
        [httpx.TimeoutException("connect timeout")] * 3
    )
    result = _resend(transport=transport)

    assert result["status"] == "failed"
    assert calls["count"] == 3
    assert "timeout" in result["error"]


def test_resend_401_is_not_retried():
    transport, calls = _sequence_transport([401])
    result = _resend(transport=transport)

    assert result["status"] == "failed"
    assert calls["count"] == 1
    assert len(result["attempts"]) == 1
    assert "http_401" in result["error"]


def test_resend_422_is_not_retried():
    transport, calls = _sequence_transport([422])
    result = _resend(transport=transport)

    assert result["status"] == "failed"
    assert calls["count"] == 1
    assert "http_422" in result["error"]


def test_resend_error_does_not_leak_api_key():
    key = "re_super_secret_value"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text=f"bad key {key}", request=request)

    result = _resend(api_key=key, transport=httpx.MockTransport(handler))
    assert key not in str(result)


# ---------------------------------------------------------------------------
# Admin test-notification endpoint
# ---------------------------------------------------------------------------

def _enable_resend(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "resend")
    monkeypatch.setattr(settings, "RESEND_API_KEY", "re_secret_key")
    monkeypatch.setattr(settings, "ALERT_EMAIL_FROM", "alerts@example.com")
    return settings


def test_test_notification_email_success(admin_client, monkeypatch):
    _enable_resend(monkeypatch)

    async def fake_send(**kwargs):
        return {
            "status": "sent",
            "error": None,
            "message_id": "msg_test",
            "attempts": [{"attempt": 1, "status": "sent"}],
        }

    monkeypatch.setattr("app.api.routes.ingest.send_email_notification", fake_send)
    response = admin_client.post(
        "/api/alerts/test-notification",
        json={"channel": "email", "recipient": "admin@example.com"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True
    assert body["channel"] == "email"
    assert body["status"] == "sent"
    assert body["message_id"] == "msg_test"
    assert "re_secret_key" not in response.text


def test_test_notification_email_disabled(admin_client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "EMAIL_ENABLED", False)

    response = admin_client.post(
        "/api/alerts/test-notification",
        json={"channel": "email", "recipient": "admin@example.com"},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "email_disabled"


def test_test_notification_missing_resend_key(admin_client, monkeypatch):
    settings = _enable_resend(monkeypatch)
    monkeypatch.setattr(settings, "RESEND_API_KEY", None)

    response = admin_client.post(
        "/api/alerts/test-notification",
        json={"channel": "email", "recipient": "admin@example.com"},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "missing_resend_api_key"
    assert "re_secret_key" not in response.text


def test_test_notification_invalid_recipient(admin_client, monkeypatch):
    _enable_resend(monkeypatch)

    response = admin_client.post(
        "/api/alerts/test-notification",
        json={"channel": "email", "recipient": "not-an-email"},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "invalid_recipient"


def test_test_notification_provider_rejection_is_clear(admin_client, monkeypatch):
    _enable_resend(monkeypatch)

    async def fake_send(**kwargs):
        return {"status": "failed", "error": "http_422: domain not verified", "attempts": []}

    monkeypatch.setattr("app.api.routes.ingest.send_email_notification", fake_send)
    response = admin_client.post(
        "/api/alerts/test-notification",
        json={"channel": "email", "recipient": "admin@example.com"},
    )
    assert response.status_code == 502
    assert response.json()["detail"]["error"] == "provider_rejected"


def test_test_notification_webhook_success(admin_client, monkeypatch):
    calls = []

    async def fake_webhook(**kwargs):
        calls.append(kwargs)
        return [{"attempt": 1, "status": "sent", "http_code": 200, "error": None}]

    monkeypatch.setattr("app.api.routes.ingest.send_webhook", fake_webhook)
    response = admin_client.post(
        "/api/alerts/test-notification",
        json={"channel": "webhook", "webhook_url": "https://example.com/hook"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "sent"
    assert len(calls) == 1


def test_test_notification_webhook_invalid_url(admin_client):
    response = admin_client.post(
        "/api/alerts/test-notification",
        json={"channel": "webhook", "webhook_url": "file:///etc/passwd"},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "invalid_webhook_url"


def test_test_notification_webhook_failure(admin_client, monkeypatch):
    async def fake_webhook(**kwargs):
        return [{"attempt": 1, "status": "failed", "http_code": 500, "error": "boom"}]

    monkeypatch.setattr("app.api.routes.ingest.send_webhook", fake_webhook)
    response = admin_client.post(
        "/api/alerts/test-notification",
        json={"channel": "webhook", "webhook_url": "https://example.com/hook"},
    )
    assert response.status_code == 502
    assert response.json()["detail"]["error"] == "webhook_delivery_failed"


def test_test_notification_is_admin_only(viewer_a_client):
    response = viewer_a_client.post(
        "/api/alerts/test-notification",
        json={"channel": "email", "recipient": "admin@example.com"},
    )
    assert response.status_code == 403


def test_test_notification_route_is_registered():
    from app.main import app

    paths = app.openapi()["paths"]
    assert "/api/alerts/test-notification" in paths
    assert "post" in paths["/api/alerts/test-notification"]


# ---------------------------------------------------------------------------
# Alert-flow isolation and dedup
# ---------------------------------------------------------------------------

async def _make_rule(session, tenant: str):
    rule = AlertRule(
        id=uuid.uuid4().hex[:25],
        name=f"Delivery test {uuid.uuid4().hex[:8]}",
        description="delivery test",
        tenant=tenant,
        conditions=[],
        filter={},
        enabled=True,
        severity="high",
        rule_type="threshold",
        group_by="src_ip",
        threshold=1,
        window_minutes=5,
        cooldown_minutes=15,
        notify={},
    )
    session.add(rule)
    await session.flush()
    return rule


@pytest.mark.asyncio
async def test_email_failure_does_not_block_webhook_or_alert(test_database, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "ALERT_EMAIL_TO", "admin@example.com")

    webhook_calls = []

    async def fake_webhook(**kwargs):
        webhook_calls.append(kwargs)
        return [{"attempt": 1, "status": "sent", "http_code": 200, "error": None}]

    async def boom_email(**kwargs):
        raise RuntimeError("email provider exploded")

    monkeypatch.setattr("app.services.alerting.alerter.send_webhook", fake_webhook)
    monkeypatch.setattr("app.services.alerting.alerter.send_email_notification", boom_email)

    now = datetime.now(timezone.utc)
    async with async_session_maker() as session:
        rule = await _make_rule(session, "delivery-isolation")
        await session.commit()

        result = await create_or_update_alert(
            session,
            rule_id=rule.id,
            rule_name=rule.name,
            rule_severity=rule.severity,
            tenant="delivery-isolation",
            group_by="src_ip",
            group_value="203.0.113.44",
            count=1,
            first_seen=now,
            last_seen=now,
            evidence_ids=["evt-1"],
            tags=[],
            window_minutes=5,
            notify={"webhook_url": "https://example.com/hook", "cooldown_minutes": 15},
            now=now,
        )
        await session.commit()

        alert = await session.get(Alert, result["id"])
        assert alert is not None, "email failure must not roll back alert creation"
        assert len(webhook_calls) == 1, "webhook must still be delivered"

        by_channel = {n["channel"]: n for n in (alert.notifications or [])}
        assert by_channel["webhook"]["status"] == "sent"
        assert by_channel["email"]["status"] == "failed"

        await session.execute(
            delete(EmailNotification).where(EmailNotification.alert_id == alert.id)
        )
        await session.execute(delete(Alert).where(Alert.id == alert.id))
        await session.execute(delete(AlertRule).where(AlertRule.id == rule.id))
        await session.commit()


@pytest.mark.asyncio
async def test_dedup_sends_one_email_and_one_notification_row(test_database, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "ALERT_EMAIL_TO", "admin@example.com")

    email_calls = []

    async def fake_email(**kwargs):
        email_calls.append(kwargs)
        return {
            "status": "sent",
            "error": None,
            "message_id": "msg_dedup",
            "attempts": [{"attempt": 1, "status": "sent"}],
        }

    monkeypatch.setattr("app.services.alerting.alerter.send_email_notification", fake_email)

    now = datetime.now(timezone.utc)
    async with async_session_maker() as session:
        rule = await _make_rule(session, "delivery-dedup")
        await session.commit()

        first = await create_or_update_alert(
            session,
            rule_id=rule.id,
            rule_name=rule.name,
            rule_severity=rule.severity,
            tenant="delivery-dedup",
            group_by="src_ip",
            group_value="198.51.100.7",
            count=1,
            first_seen=now,
            last_seen=now,
            evidence_ids=["evt-1"],
            tags=[],
            window_minutes=5,
            notify={"cooldown_minutes": 15},
            now=now,
        )
        await session.commit()

        second = await create_or_update_alert(
            session,
            rule_id=rule.id,
            rule_name=rule.name,
            rule_severity=rule.severity,
            tenant="delivery-dedup",
            group_by="src_ip",
            group_value="198.51.100.7",
            count=1,
            first_seen=now,
            last_seen=now + timedelta(seconds=10),
            evidence_ids=["evt-2"],
            tags=[],
            window_minutes=5,
            notify={"cooldown_minutes": 15},
            now=now + timedelta(seconds=10),
        )
        await session.commit()

        assert first["id"] == second["id"]
        assert len(email_calls) == 1, "dedup must not send a second email"

        rows = (
            await session.execute(
                select(EmailNotification).where(
                    EmailNotification.alert_id == first["id"]
                )
            )
        ).scalars().all()
        assert len(rows) == 1, "dedup must not create a second email_notifications row"
        assert rows[0].status == EmailStatus.SENT
        assert rows[0].attempts == 1

        await session.execute(
            delete(EmailNotification).where(EmailNotification.alert_id == first["id"])
        )
        await session.execute(delete(Alert).where(Alert.id == first["id"]))
        await session.execute(delete(AlertRule).where(AlertRule.id == rule.id))
        await session.commit()


# ---------------------------------------------------------------------------
# Alert API exposes delivery status
# ---------------------------------------------------------------------------

def test_alerts_api_includes_notifications(admin_client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "ALERT_EMAIL_TO", None)

    async def setup():
        now = datetime.now(timezone.utc)
        async with async_session_maker() as session:
            rule = await _make_rule(session, "notifications-api")
            await session.commit()
            result = await create_or_update_alert(
                session,
                rule_id=rule.id,
                rule_name="Notifications API test",
                rule_severity="high",
                tenant="notifications-api",
                group_by="src_ip",
                group_value="192.0.2.10",
                count=1,
                first_seen=now,
                last_seen=now,
                evidence_ids=["evt-api"],
                tags=[],
                window_minutes=5,
                notify={"webhook_url": "https://example.com/hook"},
                now=now,
            )
            await session.commit()
            return rule.id, result["id"]

    rule_id, alert_id = _run(setup())
    try:
        response = admin_client.get(
            "/api/get-alerts",
            params={"tenant": "notifications-api", "search": "Notifications API test"},
        )
        assert response.status_code == 200, response.text
        alerts = response.json()["alerts"]
        assert any(a["id"] == alert_id for a in alerts)
        matched = next(a for a in alerts if a["id"] == alert_id)
        assert matched["notifications"], "alert API must expose delivery status"
        assert matched["notifications"][0]["channel"] == "webhook"
    finally:
        async def cleanup():
            async with async_session_maker() as session:
                await session.execute(delete(Alert).where(Alert.id == alert_id))
                await session.execute(delete(AlertRule).where(AlertRule.id == rule_id))
                await session.commit()

        _run(cleanup())
