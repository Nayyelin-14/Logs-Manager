"""Notification payload unit check.

The alerting integration test proves an alert produces a delivery notification.
This test keeps the notification contract: the generated webhook payload must
carry enough context to be actionable.
"""

from app.services.notifier import build_webhook_payload


def test_webhook_payload_contains_alert_context():
    payload = build_webhook_payload(
        alert_id="alert-1",
        rule={"name": "Brute force rule"},
        tenant="demoa",
        severity="high",
        group_value="203.0.113.201",
        count=5,
        window_minutes=5,
        first_seen="2026-11-11T10:00:00Z",
        last_seen="2026-11-11T10:03:00Z",
        link="/alerts/alert-1",
    )

    assert payload["alert_id"] == "alert-1"
    assert payload["tenant"] == "demoa"
    assert payload["severity"] == "high"
    assert payload["group"] == "203.0.113.201"
    assert payload["count"] == 5
