"""Alert rule evaluation and deduplication.

The seeded brute-force rule (five failed AD logons from one source IP in five
minutes) is exercised through the real ingestion API. The direct service check
proves repeated evaluations update one alert row instead of creating duplicates.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import httpx
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import async_session_maker
from app.models.alert import Alert, AlertRule, EmailNotification
from app.models.events import Event
from app.services.alerting.alerter import create_or_update_alert
from app.services.notifier import (
    build_webhook_payload,
    send_email,
    send_email_notification,
    send_resend_email,
    send_webhook,
)

from conftest import ADMIN_EMAIL, ADMIN_PASSWORD, login

AD_FAILURE = {
    "source": "ad",
    "event_id": 4625,
    "event_type": "LogonFailed",
    "host": "DC01",
    "action": "LOGIN",
    "status": "Failure",
    "severity": 7,
}


def _ingest_failure(client, api_key, *, tenant, src_ip, user, tag, ts):
    return client.post(
        "/api/ingest",
        json={
            **AD_FAILURE,
            "tenant": tenant,
            "src_ip": src_ip,
            "user": user,
            "src_port": "49152",
            "@timestamp": ts.isoformat(),
            "tags": [tag],
        },
        headers={"X-API-Key": api_key, "Content-Type": "application/json"},
    )


def _alerts_for_tag(client, tag: str) -> list[dict]:
    response = client.get("/api/get-alerts", params={"search": tag})
    assert response.status_code == 200, response.text
    return response.json()["alerts"]


def test_threshold_rule_triggers_one_alert_and_aggregates(client, api_key_demoa):
    tag = f"brute-a-{uuid.uuid4().hex}"
    src_ip = "203.0.113.201"
    now = datetime.now(timezone.utc)

    for index in range(5):
        response = _ingest_failure(
            client,
            api_key_demoa,
            tenant="demoa",
            src_ip=src_ip,
            user=f"demo\\user{index}",
            tag=tag,
            ts=now - timedelta(seconds=30 * index),
        )
        assert response.status_code == 200, response.text

    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    alerts = _alerts_for_tag(client, tag)
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert["tenant"] == "demoa"
    assert alert["status"] == "open"
    assert alert["count"] == 5
    assert "Brute force" in alert["description"]

    for index in range(5, 7):
        response = _ingest_failure(
            client,
            api_key_demoa,
            tenant="demoa",
            src_ip=src_ip,
            user=f"demo\\user{index}",
            tag=tag,
            ts=datetime.now(timezone.utc),
        )
        assert response.status_code == 200, response.text

    alerts = _alerts_for_tag(client, tag)
    assert len(alerts) == 1, "new failures must update the existing alert"
    assert alerts[0]["count"] == 7


def test_rule_does_not_fire_below_threshold_or_across_ips(client, api_key_demoa):
    now = datetime.now(timezone.utc)

    low_tag = f"brute-low-{uuid.uuid4().hex}"
    for index in range(4):
        response = _ingest_failure(
            client,
            api_key_demoa,
            tenant="demoa",
            src_ip="198.51.100.150",
            user=f"low{index}",
            tag=low_tag,
            ts=now - timedelta(seconds=10 * index),
        )
        assert response.status_code == 200, response.text

    spread_tag = f"brute-spread-{uuid.uuid4().hex}"
    for index in range(5):
        response = _ingest_failure(
            client,
            api_key_demoa,
            tenant="demoa",
            src_ip=f"198.51.100.{160 + index}",
            user=f"spread{index}",
            tag=spread_tag,
            ts=now - timedelta(seconds=10 * index),
        )
        assert response.status_code == 200, response.text

    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    assert _alerts_for_tag(client, low_tag) == []
    assert _alerts_for_tag(client, spread_tag) == []


def test_alert_records_a_notification(client, api_key_demoa):
    tag = f"brute-notify-{uuid.uuid4().hex}"
    now = datetime.now(timezone.utc)

    for index in range(5):
        response = _ingest_failure(
            client,
            api_key_demoa,
            tenant="demoa",
            src_ip="203.0.113.202",
            user=f"notify{index}",
            tag=tag,
            ts=now - timedelta(seconds=20 * index),
        )
        assert response.status_code == 200, response.text

    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    alerts = _alerts_for_tag(client, tag)
    assert len(alerts) == 1

    notifications = alerts[0]["notifications"]
    assert notifications, "a triggered alert must record a notification attempt"
    assert any(
        notification["channel"] == "webhook" and notification["status"] == "sent"
        for notification in notifications
    )

    # Provider-neutral notifier paths: SSRF refusal, Resend retries, and the
    # disabled-provider guards. Network I/O is replaced with a mock transport.
    payload = build_webhook_payload(
        alert_id="alert-1",
        rule={"id": "rule-1", "name": "notifier probe"},
        tenant="demoa",
        severity="high",
        group_value="203.0.113.9",
        count=5,
        window_minutes=5,
        first_seen=now.isoformat(),
        last_seen=now.isoformat(),
        link="/alerts/alert-1",
    )
    assert payload["alert_id"] == "alert-1"
    assert payload["notified_at"]

    async def _notifier_checks() -> None:
        blocked = await send_webhook(
            webhook_url="http://127.0.0.1/hook", payload=payload, retries=1
        )
        assert blocked[0]["status"] == "failed"
        assert "blocked destination" in blocked[0]["error"]

        def accept(request: httpx.Request) -> httpx.Response:
            assert request.headers["Authorization"] == "Bearer test-key"
            return httpx.Response(200, json={"id": "msg-1"})

        sent_result = await send_resend_email(
            recipient="soc@example.test",
            subject="probe",
            html_body="<p>probe</p>",
            from_email="alerts@example.test",
            api_key="test-key",
            transport=httpx.MockTransport(accept),
            retry_delays=(0,),
        )
        assert sent_result["status"] == "sent"
        assert sent_result["message_id"] == "msg-1"

        def reject(request: httpx.Request) -> httpx.Response:
            return httpx.Response(422, text="bad request")

        rejected = await send_resend_email(
            recipient="soc@example.test",
            subject="probe",
            html_body="<p>probe</p>",
            from_email="alerts@example.test",
            api_key="test-key",
            transport=httpx.MockTransport(reject),
            retry_delays=(0,),
        )
        assert rejected["status"] == "failed"
        assert "http_422" in rejected["error"]

        calls = {"count": 0}

        def flaky(request: httpx.Request) -> httpx.Response:
            calls["count"] += 1
            if calls["count"] == 1:
                return httpx.Response(500, text="temporary")
            return httpx.Response(200, json={"id": "msg-2"})

        retried = await send_resend_email(
            recipient="soc@example.test",
            subject="probe",
            html_body="<p>probe</p>",
            from_email="alerts@example.test",
            api_key="test-key",
            transport=httpx.MockTransport(flaky),
            retry_delays=(0,),
            max_attempts=2,
        )
        assert retried["status"] == "sent"
        assert len(retried["attempts"]) == 2

        assert (
            await send_resend_email(recipient="soc@example.test", subject="x", api_key=None)
        )["error"] == "missing_resend_api_key"
        assert (
            await send_resend_email(
                recipient="bad",
                subject="x",
                html_body="x",
                from_email="alerts@example.test",
                api_key="k",
            )
        )["error"] == "invalid_recipient"
        assert (
            await send_resend_email(
                recipient="soc@example.test",
                subject="x",
                html_body="x",
                from_email="bad",
                api_key="k",
            )
        )["error"] == "invalid_sender"
        assert (
            await send_resend_email(
                recipient="soc@example.test",
                subject="x",
                from_email="alerts@example.test",
                api_key="k",
            )
        )["error"] == "empty_body"

        def timeout_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("slow provider")

        timed_out = await send_resend_email(
            recipient="soc@example.test",
            subject="x",
            html_body="x",
            from_email="alerts@example.test",
            api_key="k",
            transport=httpx.MockTransport(timeout_handler),
            retry_delays=(0,),
            max_attempts=1,
        )
        assert timed_out["status"] == "failed"
        assert "timeout" in timed_out["error"]

        exhausted = await send_resend_email(
            recipient="soc@example.test",
            subject="x",
            html_body="x",
            from_email="alerts@example.test",
            api_key="k",
            transport=httpx.MockTransport(lambda request: httpx.Response(500, text="down")),
            retry_delays=(0,),
            max_attempts=2,
        )
        assert exhausted["status"] == "failed"
        assert len(exhausted["attempts"]) == 2

        # Webhook delivery branches with a fake HTTP client.
        class FakeResponse:
            def __init__(self, status_code: int = 200, content: bytes = b"ok") -> None:
                self.status_code = status_code
                self.content = content
                self.text = content.decode(errors="replace")
                self.is_success = 200 <= status_code < 300

        class FakeClient:
            def __init__(self, response=None, exc=None) -> None:
                self._response = response
                self._exc = exc

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args) -> bool:
                return False

            async def post(self, *args, **kwargs):
                if self._exc is not None:
                    raise self._exc
                return self._response

        async def _webhook_with(client: FakeClient, retries: int = 1):
            with patch("app.services.notifier.httpx.AsyncClient", return_value=client):
                return await send_webhook(
                    webhook_url="https://93.184.216.34/hook",
                    payload=payload,
                    retries=retries,
                    retry_delays=(0,),
                )

        delivered = await _webhook_with(FakeClient(FakeResponse()))
        assert delivered[0]["status"] == "sent"

        rejected_webhook = await _webhook_with(FakeClient(FakeResponse(500)))
        assert rejected_webhook[0]["status"] == "failed"
        assert rejected_webhook[0]["http_code"] == 500

        oversized = await _webhook_with(
            FakeClient(FakeResponse(200, b"x" * (1_048_576 + 10))), retries=2
        )
        assert "response too large" in oversized[0]["error"]
        assert len(oversized) == 2

        timed_out_webhook = await _webhook_with(
            FakeClient(exc=httpx.TimeoutException("slow webhook"))
        )
        assert "timeout" in timed_out_webhook[0]["error"]

        crashed_webhook = await _webhook_with(FakeClient(exc=RuntimeError("boom")))
        assert "RuntimeError" in crashed_webhook[0]["error"]

        # SMTP and provider routing.
        with patch("aiosmtplib.send", new=AsyncMock(return_value=None)):
            mail = await send_email(
                recipient="soc@example.test",
                subject="probe",
                body="probe",
                smtp_host="localhost",
                smtp_port=25,
                smtp_username="user",
                smtp_password="secret",
            )
        assert mail["status"] == "sent"

        with patch(
            "aiosmtplib.send", new=AsyncMock(side_effect=RuntimeError("smtp down"))
        ):
            mail_failed = await send_email(
                recipient="soc@example.test",
                subject="probe",
                body="probe",
                smtp_host="localhost",
                smtp_port=25,
                smtp_username="user",
                smtp_password="secret",
            )
        assert mail_failed["status"] == "failed"

        settings = get_settings()
        original = (settings.EMAIL_ENABLED, settings.EMAIL_PROVIDER, settings.SMTP_ENABLED)
        try:
            settings.EMAIL_ENABLED = False
            disabled = await send_email_notification(recipient="soc@example.test", subject="x")
            assert disabled["status"] == "skipped"
            assert disabled["error"] == "email_disabled"

            settings.EMAIL_ENABLED = True
            settings.EMAIL_PROVIDER = "smtp"
            settings.SMTP_ENABLED = False
            smtp_off = await send_email_notification(recipient="soc@example.test", subject="x")
            assert smtp_off["status"] == "skipped"
            assert smtp_off["error"] == "smtp_disabled"

            settings.EMAIL_PROVIDER = "resend"
            with patch(
                "app.services.notifier.send_resend_email",
                new=AsyncMock(return_value={"status": "sent", "attempts": []}),
            ):
                routed = await send_email_notification(
                    recipient="soc@example.test", subject="x", text_body="x"
                )
            assert routed["status"] == "sent"

            settings.EMAIL_PROVIDER = "smtp"
            settings.SMTP_ENABLED = True
            with patch(
                "app.services.notifier.send_email",
                new=AsyncMock(return_value={"status": "sent", "error": None}),
            ):
                smtp_routed = await send_email_notification(
                    recipient="soc@example.test", subject="x", text_body="x"
                )
            assert smtp_routed["status"] == "sent"
            assert smtp_routed["attempts"][0]["status"] == "sent"
        finally:
            (
                settings.EMAIL_ENABLED,
                settings.EMAIL_PROVIDER,
                settings.SMTP_ENABLED,
            ) = original

    asyncio.run(_notifier_checks())


def test_alert_evidence_stays_within_tenant(client, api_key_demoa, api_key_demob):
    tag = f"evidence-{uuid.uuid4().hex}"
    src_ip = "198.51.100.210"
    now = datetime.now(timezone.utc)

    for tenant, api_key, offset in (
        ("demoa", api_key_demoa, 0),
        ("demob", api_key_demob, 100),
    ):
        for index in range(5):
            response = _ingest_failure(
                client,
                api_key,
                tenant=tenant,
                src_ip=src_ip,
                user=f"evidence{index}",
                tag=tag,
                ts=now + timedelta(seconds=offset + index),
            )
            assert response.status_code == 200, response.text

    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    alerts = client.get("/api/get-alerts").json()["alerts"]
    demoa_alerts = [
        alert
        for alert in alerts
        if alert["tenant"] == "demoa" and src_ip in (alert.get("dedupeKey") or "")
    ]
    demob_alerts = [
        alert
        for alert in alerts
        if alert["tenant"] == "demob" and src_ip in (alert.get("dedupeKey") or "")
    ]
    assert len(demoa_alerts) == 1
    assert len(demob_alerts) == 1
    assert demoa_alerts[0]["count"] == 5
    assert demob_alerts[0]["count"] == 5

    demoa_ids = set(demoa_alerts[0]["eventIds"])
    demob_ids = set(demob_alerts[0]["eventIds"])
    assert len(demoa_ids) == len(demob_ids) == 5
    assert demoa_ids.isdisjoint(demob_ids)

    async def _tenants_by_event_id() -> dict[str, str]:
        async with async_session_maker() as session:
            rows = (
                await session.execute(
                    select(Event.id, Event.tenant).where(
                        Event.id.in_(demoa_ids | demob_ids)
                    )
                )
            ).all()
            return {event_id: tenant for event_id, tenant in rows}

    tenants_by_id = asyncio.run(_tenants_by_event_id())
    assert set(tenants_by_id) == demoa_ids | demob_ids
    assert all(tenants_by_id[event_id] == "demoa" for event_id in demoa_ids)
    assert all(tenants_by_id[event_id] == "demob" for event_id in demob_ids)


def test_rule_validation_and_viewer_boundary(client):
    payload = {
        "name": "Consolidated viewer rule",
        "tenant": "demoa",
        "conditions": [{"type": "event_type", "value": "viewer_probe"}],
    }
    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    client.post("/api/auth/logout")

    from conftest import VIEWER_A_EMAIL, VIEWER_A_PASSWORD

    login(client, VIEWER_A_EMAIL, VIEWER_A_PASSWORD)
    response = client.post("/api/create-alertRule", json=payload)
    assert response.status_code == 403, response.text

    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    response = client.post(
        "/api/create-alertRule",
        json={
            "name": "Invalid condition rule",
            "tenant": "demoa",
            "conditions": [{"type": "unknown_condition_type", "threshold": 5}],
        },
    )
    assert response.status_code == 422, response.text

    response = client.post(
        "/api/create-alertRule",
        json={
            "name": f"Valid rule {uuid.uuid4().hex[:8]}",
            "tenant": "demob",
            "conditions": [{"type": "event_type", "value": "rotation_probe"}],
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["createdRule"]["tenant"] == "demob"
    rule_id = response.json()["createdRule"]["id"]

    listing = client.get("/api/get-rules", params={"search": "Valid rule"})
    assert listing.status_code == 200, listing.text
    assert any(row["id"] == rule_id for row in listing.json()["rules"])
    missing_cursor = client.get("/api/get-rules", params={"cursor": "missing-rule"})
    assert missing_cursor.json()["rules"] == []

    updated = client.put(
        f"/api/update-rule/{rule_id}",
        json={
            "name": f"Updated rule {uuid.uuid4().hex[:8]}",
            "description": "updated by lifecycle test",
            "severity": "low",
            "threshold": 9,
            "window_minutes": 10,
            "cooldown_minutes": 5,
            "group_by": "src_ip",
            "conditions": [{"type": "event_type", "value": "rotation_probe"}],
            "filter": {"event_type": "rotation_probe"},
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["rule"]["severity"] == "low"

    # Metadata-only edit keeps the existing condition.
    metadata = client.put(f"/api/update-rule/{rule_id}", json={"description": "metadata only"})
    assert metadata.status_code == 200, metadata.text
    assert metadata.json()["rule"]["description"] == "metadata only"

    assert client.put(f"/api/update-rule/{rule_id}", json={"tenant": "demoa"}).status_code == 403
    assert client.put(f"/api/update-rule/{rule_id}", json={"severity": "extreme"}).status_code == 400
    assert client.put(f"/api/update-rule/{rule_id}", json={"name": "   "}).status_code == 400
    assert client.put("/api/update-rule/missing-rule", json={"name": "x"}).status_code == 404

    toggled = client.patch(f"/api/rules/{rule_id}/enabled", params={"enabled": "false"})
    assert toggled.status_code == 200, toggled.text
    assert toggled.json()["rule"]["enabled"] is False
    assert client.patch(f"/api/rules/{rule_id}/enabled", params={"enabled": "true"}).status_code == 200
    assert client.patch("/api/rules/missing-rule/enabled", params={"enabled": "true"}).status_code == 404

    tested = client.post(f"/api/rules/{rule_id}/test")
    assert tested.status_code == 200, tested.text
    assert {"rule_id", "evaluated_at", "would_trigger", "matches"} <= set(tested.json())
    assert client.post("/api/rules/missing-rule/test").status_code == 404

    # A second rule owns an alert so deletion rules can be checked independently.
    alert_rule_response = client.post(
        "/api/create-alertRule",
        json={
            "name": f"Alert status rule {uuid.uuid4().hex[:8]}",
            "tenant": "demoa",
            "conditions": [{"type": "event_type", "value": "alert_status_probe"}],
        },
    )
    assert alert_rule_response.status_code == 201, alert_rule_response.text
    alert_rule_id = alert_rule_response.json()["createdRule"]["id"]
    alert_id = uuid.uuid4().hex[:25]
    now = datetime.now(timezone.utc)

    async def _seed_alert() -> None:
        async with async_session_maker() as session:
            session.add(
                Alert(
                    id=alert_id,
                    rule_id=alert_rule_id,
                    tenant="demoa",
                    description="alert status probe",
                    triggered_at=now,
                    event_ids=[],
                    severity="low",
                    status="open",
                    title="alert status probe",
                    tags=[],
                    dedupe_key=f"status-{alert_id}",
                    count=1,
                    first_seen=now,
                    last_seen=now,
                )
            )
            await session.commit()

    asyncio.run(_seed_alert())

    patched = client.patch(f"/api/alerts/{alert_id}", json={"status": "resolved"})
    assert patched.status_code == 200, patched.text
    assert patched.json()["alert"]["status"] == "resolved"
    assert client.patch(f"/api/alerts/{alert_id}", json={"status": "bogus"}).status_code == 400
    assert client.patch("/api/alerts/missing-alert", json={"status": "open"}).status_code == 404

    # Notification test endpoint: error branches and both successful channels.
    assert client.post(
        "/api/alerts/test-notification", json={"channel": "email"}
    ).status_code == 400
    assert client.post(
        "/api/alerts/test-notification", json={"channel": "nope"}
    ).status_code == 400
    settings = get_settings()
    original_webhook = settings.ALERT_WEBHOOK_URL
    settings.ALERT_WEBHOOK_URL = None
    try:
        assert client.post(
            "/api/alerts/test-notification", json={"channel": "webhook"}
        ).status_code == 400
    finally:
        settings.ALERT_WEBHOOK_URL = original_webhook
    assert client.post(
        "/api/alerts/test-notification",
        json={"channel": "webhook", "webhook_url": "not-a-url"},
    ).status_code == 400

    sent = [{
        "attempt": 1,
        "timestamp": now.isoformat(),
        "status": "sent",
        "http_code": 200,
        "error": None,
    }]
    with patch("app.api.routes.ingest.send_webhook", return_value=sent):
        webhook_ok = client.post(
            "/api/alerts/test-notification",
            json={"channel": "webhook", "webhook_url": "https://hooks.example.test/x"},
        )
    assert webhook_ok.status_code == 200, webhook_ok.text
    assert webhook_ok.json()["status"] == "sent"

    with patch("app.api.routes.ingest.send_webhook", return_value=[{"status": "failed", "error": "nope"}]):
        assert client.post(
            "/api/alerts/test-notification",
            json={"channel": "webhook", "webhook_url": "https://hooks.example.test/x"},
        ).status_code == 502
    with patch("app.api.routes.ingest.send_webhook", side_effect=RuntimeError("boom")):
        assert client.post(
            "/api/alerts/test-notification",
            json={"channel": "webhook", "webhook_url": "https://hooks.example.test/x"},
        ).status_code == 502

    settings = get_settings()
    original_enabled = settings.EMAIL_ENABLED
    original_provider = settings.EMAIL_PROVIDER
    settings.EMAIL_ENABLED = True
    settings.EMAIL_PROVIDER = "smtp"
    try:
        assert client.post(
            "/api/alerts/test-notification",
            json={"channel": "email", "recipient": "not-an-email"},
        ).status_code == 400
        with patch(
            "app.api.routes.ingest.send_email_notification",
            return_value={"status": "sent", "attempts": sent, "message_id": "m1"},
        ):
            email_ok = client.post(
                "/api/alerts/test-notification",
                json={"channel": "email", "recipient": "soc@example.test"},
            )
        assert email_ok.status_code == 200, email_ok.text
        assert email_ok.json()["status"] == "sent"
        with patch(
            "app.api.routes.ingest.send_email_notification",
            return_value={"status": "failed", "error": "invalid_recipient", "attempts": []},
        ):
            assert client.post(
                "/api/alerts/test-notification",
                json={"channel": "email", "recipient": "soc@example.test"},
            ).status_code == 400
        with patch(
            "app.api.routes.ingest.send_email_notification",
            side_effect=RuntimeError("smtp down"),
        ):
            assert client.post(
                "/api/alerts/test-notification",
                json={"channel": "email", "recipient": "soc@example.test"},
            ).status_code == 502
    finally:
        settings.EMAIL_ENABLED = original_enabled
        settings.EMAIL_PROVIDER = original_provider

    assert client.delete(f"/api/delete-rule/{rule_id}").status_code == 200
    assert client.delete(f"/api/delete-rule/{rule_id}").status_code == 404
    # The rule with an alert cannot be deleted until the alert is gone.
    assert client.delete(f"/api/delete-rule/{alert_rule_id}").status_code == 409


def test_create_or_update_alert_is_idempotent(test_database):
    now = datetime.now(timezone.utc)

    async def _exercise() -> None:
        async with async_session_maker() as session:
            rule = AlertRule(
                id=uuid.uuid4().hex[:25],
                name=f"idempotency-{uuid.uuid4().hex[:8]}",
                description="dedupe test",
                tenant="demoa",
                enabled=True,
                severity="high",
                filter={"outcome": "failure", "action": "login"},
                conditions=[{"type": "event_type", "value": "LogonFailed"}],
                group_by="src_ip",
                threshold=5,
                window_minutes=5,
                cooldown_minutes=15,
            )
            session.add(rule)
            await session.flush()

            sent = [{
                "attempt": 1,
                "timestamp": now.isoformat(),
                "status": "sent",
                "http_code": 200,
                "error": None,
            }]
            notify = {
                "webhook_url": "https://hooks.example.test/alert",
                "email": "soc@example.test",
                "cooldown_minutes": 15,
            }
            kwargs = dict(
                session=session,
                rule_id=rule.id,
                rule_name=rule.name,
                rule_severity="high",
                tenant="demoa",
                group_by="src_ip",
                group_value="203.0.113.77",
                count=3,
                first_seen=now,
                last_seen=now,
                evidence_ids=["e1", "e2"],
                tags=["demo"],
                window_minutes=5,
                notify=notify,
                now=now,
            )
            with (
                patch("app.services.alerting.alerter.send_webhook", return_value=sent),
                patch(
                    "app.services.alerting.alerter.send_email_notification",
                    return_value={"status": "sent", "attempts": sent, "message_id": "m1"},
                ),
            ):
                first = await create_or_update_alert(**kwargs)
                # Same window: cooldown suppresses a second notification.
                second = await create_or_update_alert(**kwargs)
                # Window expired: delivery happens again for the same alert.
                third = await create_or_update_alert(
                    **dict(kwargs, evidence_ids=["e3", "e4"], now=now + timedelta(minutes=30))
                )

            assert first["dedupe_key"] == f"{rule.id}:demoa:203.0.113.77"
            assert first["id"] == second["id"] == third["id"]
            assert (first["count"], second["count"], third["count"]) == (3, 3, 5)
            assert second["notified"] is False
            assert third["notified"] is True

            rows = (
                await session.execute(
                    select(Alert).where(Alert.dedupe_key == first["dedupe_key"])
                )
            ).scalars().all()
            assert len(rows) == 1
            alert = rows[0]
            assert alert.count == 5
            channels = [note["channel"] for note in alert.notifications]
            assert channels == ["webhook", "email", "webhook", "email"]
            assert all(
                note["status"] == "sent"
                for note in alert.notifications
                if note["channel"] in ("webhook", "email")
            )

            email_rows = (
                await session.execute(
                    select(EmailNotification).where(EmailNotification.alert_id == alert.id)
                )
            ).scalars().all()
            assert len(email_rows) == 1
            assert email_rows[0].attempts >= 1

            # Invalid recipient is recorded without contacting a provider.
            with patch("app.services.alerting.alerter.send_webhook", return_value=sent):
                invalid = await create_or_update_alert(
                    **dict(
                        kwargs,
                        group_value="203.0.113.78",
                        notify={"email": "not-an-email"},
                    )
                )
            invalid_alert = (
                await session.execute(
                    select(Alert).where(Alert.dedupe_key == invalid["dedupe_key"])
                )
            ).scalar_one()
            assert invalid_alert.notifications[-1]["error"] == "invalid_recipient"
            assert invalid_alert.notifications[-1]["status"] == "failed"

            await session.rollback()

    asyncio.run(_exercise())
