import pytest
from app.models.enums import Source
from app.parsers.canonical import resolve_canonical_event_type
from app.parsers.cloud import normalize_crowdstrike


class TestCanonicalResolution:

    @pytest.mark.parametrize(
        "event_type, source, expected",
        [
            ("CreateUser", Source.AWS, "aws_create_user"),
            ("create_user", Source.AWS, "create_user"),
            ("ad_user_created", Source.AD, "ad_user_created"),
            ("user_created", Source.M365, "user_created"),
            ("CreateUser", Source.AD, "aws_create_user"),
            ("malware_detected", Source.CROWDSTRIKE, "malware_detected"),
            ("app_login_failed", Source.API, "app_login_failed"),
        ],
    )
    def test_resolution(self, event_type, source, expected):
        result = resolve_canonical_event_type(event_type, Source(source))
        assert result == expected, f"{source}.{event_type} -> {result}, expected {expected}"


class TestAlertRuleModel:

    def test_alert_rule_model_has_required_columns(self):
        from sqlalchemy import inspect
        from app.models.alert import AlertRule

        cols = {c.name for c in AlertRule.__table__.columns}
        expected = {
            "id", "name", "description", "tenant", "conditions",
            "enabled", "severity", "createdAt", "updatedAt",
        }
        assert expected.issubset(cols)

    def test_alert_model_has_required_columns(self):
        from sqlalchemy import inspect
        from app.models.alert import Alert

        cols = {c.name for c in Alert.__table__.columns}
        expected = {
            "id", "rule_id", "tenant", "description", "triggeredAt",
            "event_ids", "severity", "status", "title", "dedupe_key",
        }
        assert expected.issubset(cols)

    def test_security_event_model_has_ingested_at(self):
        from sqlalchemy import inspect
        from app.models.security_event import SecurityEvent

        cols = {c.name for c in SecurityEvent.__table__.columns}
        assert "ingested_at" in cols


class TestCrowdStrikeActionMapping:

    @pytest.mark.parametrize(
        "vendor_action, expected_action",
        [
            ("quarantine", "alert"),
            ("Quarantine", "alert"),
            ("QUARANTINE", "alert"),
            ("blocked", "deny"),
            ("BLOCKED", "deny"),
            ("detected", "alert"),
            ("allowed", "allow"),
            ("unknown_action", "alert"),
            ("", "alert"),
            (None, "alert"),
        ],
    )
    def test_action_mapped_to_allowed_enum(self, vendor_action, expected_action):
        event = {
            "tenant": "demoA",
            "source": "crowdstrike",
            "event_type": "malware_detected",
            "host": "WIN10-01",
            "process": "powershell.exe",
            "severity": 8,
            "action": vendor_action,
            "@timestamp": "2026-11-07T08:00:00Z",
        }
        result = normalize_crowdstrike(event)
        assert result["action"] == expected_action, f"{vendor_action} -> {result['action']}, expected {expected_action}"

    def test_quarantine_preserved_in_event_subtype(self):
        event = {
            "tenant": "demoA",
            "source": "crowdstrike",
            "event_type": "malware_detected",
            "host": "WIN10-01",
            "process": "powershell.exe",
            "severity": 8,
            "action": "quarantine",
            "@timestamp": "2026-11-07T08:00:00Z",
        }
        result = normalize_crowdstrike(event)
        assert result["event_subtype"] == "quarantine"
        assert result["action"] == "alert"
        assert result["raw"]["action"] == "quarantine"
        assert result["severity"] == 8
        assert result["host"] == "WIN10-01"
        assert result["process"] == "powershell.exe"

    def test_unknown_action_gets_unmapped_tag(self):
        event = {
            "tenant": "demoA",
            "source": "crowdstrike",
            "event_type": "malware_detected",
            "host": "WIN10-01",
            "process": "powershell.exe",
            "severity": 5,
            "action": "weird_vendor_action",
            "@timestamp": "2026-11-07T08:00:00Z",
        }
        result = normalize_crowdstrike(event)
        assert result["action"] == "alert"
        assert "action_unmapped" in result["tags"]
