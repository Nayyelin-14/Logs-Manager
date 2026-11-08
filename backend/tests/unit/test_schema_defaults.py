from datetime import datetime, timezone

import pytest

from app.schemas.normalized_event import NormalizedEvent, Source, Action, Outcome


class TestNormalizedEventDefaults:

    def test_empty_tags_default(self):
        event = NormalizedEvent(
            ts=datetime(2025, 8, 20, 12, 0, 0, tzinfo=timezone.utc),
            tenant="demoA",
            source=Source.api,
            event_type="test",
            severity=5,
            raw={}
        )
        assert event.tags == []

    def test_empty_raw_default(self):
        event = NormalizedEvent(
            ts=datetime(2025, 8, 20, 12, 0, 0, tzinfo=timezone.utc),
            tenant="demoA",
            source=Source.api,
            event_type="test",
            severity=5
        )
        assert event.raw == {}

    def test_none_optional_fields(self):
        event = NormalizedEvent(
            ts=datetime(2025, 8, 20, 12, 0, 0, tzinfo=timezone.utc),
            tenant="demoA",
            source=Source.api,
            event_type="test",
            severity=5,
            raw={}
        )
        assert event.vendor is None
        assert event.product is None
        assert event.action is None
        assert event.outcome is None
        assert event.src_ip is None


class TestNormalizedEventToDict:

    def test_to_dict_basic(self):
        ts = datetime(2025, 8, 20, 12, 0, 0, tzinfo=timezone.utc)
        event = NormalizedEvent(
            id="test123",
            ts=ts,
            tenant="demoA",
            source=Source.firewall,
            event_type="test",
            severity=5,
            raw={"key": "value"},
            tags=["tag1"]
        )
        d = event.to_db_dict()
        assert d["id"] == "test123"
        assert d["tenant"] == "demoA"
        assert d["event_type"] == "test"
        assert d["raw"] == {"key": "value"}

    def test_to_dict_uses_ts_not_timestamp(self):
        event = NormalizedEvent(
            ts=datetime(2025, 8, 20, 12, 0, 0, tzinfo=timezone.utc),
            tenant="demoA",
            source=Source.api,
            event_type="test",
            severity=5,
            raw={},
            tags=[]
        )
        d = event.to_db_dict()
        assert "ts" in d, "Database column 'ts' should be present"
        assert "@timestamp" not in d, "@timestamp alias should not be in output"

    def test_to_dict_uses_tags_not_underscore_tags(self):
        event = NormalizedEvent(
            ts=datetime(2025, 8, 20, 12, 0, 0, tzinfo=timezone.utc),
            tenant="demoA",
            source=Source.api,
            event_type="test",
            severity=5,
            raw={},
            tags=["tag1", "tag2"]
        )
        d = event.to_db_dict()
        assert "_tags" in d, "Database column '_tags' should be present"
        assert "tags" not in d, "Pydantic field 'tags' should not be in output"
        assert d["_tags"] == ["tag1", "tag2"]

    def test_to_dict_preserves_user(self):
        event = NormalizedEvent(
            ts=datetime(2025, 8, 20, 12, 0, 0, tzinfo=timezone.utc),
            tenant="demoA",
            source=Source.api,
            event_type="test",
            severity=5,
            user="alice",
            raw={},
            tags=[]
        )
        d = event.to_db_dict()
        assert "user_name" in d, "user_name should be in output"
        assert d["user_name"] == "alice"

    def test_to_dict_enums_as_values(self):
        event = NormalizedEvent(
            ts=datetime(2025, 8, 20, 12, 0, 0, tzinfo=timezone.utc),
            tenant="demoA",
            source=Source.firewall,
            event_type="test",
            severity=5,
            action=Action.deny,
            outcome=Outcome.failure,
            raw={},
            tags=[]
        )
        d = event.to_db_dict()
        assert d["source"] == "firewall", "source should be string value"
        assert d["action"] == "deny", "action should be string value"
        assert d["outcome"] == "failure", "outcome should be string value"

    def test_to_dict_all_columns_present(self):
        event = NormalizedEvent(
            ts=datetime(2025, 8, 20, 12, 0, 0, tzinfo=timezone.utc),
            tenant="demoA",
            source=Source.firewall,
            event_type="test",
            severity=5,
            raw={"key": "value"},
            tags=["tag1"]
        )
        d = event.to_db_dict()
        expected_columns = [
            "id", "ts", "tenant", "source", "vendor", "product", "event_type",
            "event_subtype", "severity", "action", "action_detail", "outcome",
            "src_ip", "src_port", "dst_ip", "dst_port", "protocol", "user_name",
            "host", "process", "url", "http_method", "status_code", "rule_name",
            "rule_id", "cloud_account_id", "cloud_region", "cloud_service",
            "event_id", "logon_type", "raw", "_tags", "ingested_at"
        ]
        for col in expected_columns:
            assert col in d, f"Column '{col}' should be in to_db_dict() output"


class TestNormalizedEventFieldValidation:

    def test_severity_valid_range(self):
        event = NormalizedEvent(
            ts=datetime(2025, 8, 20, 12, 0, 0, tzinfo=timezone.utc),
            tenant="demoA",
            source=Source.api,
            event_type="test",
            severity=0,
            raw={}
        )
        assert event.severity == 0

        event2 = NormalizedEvent(
            ts=datetime(2025, 8, 20, 12, 0, 0, tzinfo=timezone.utc),
            tenant="demoA",
            source=Source.api,
            event_type="test",
            severity=10,
            raw={}
        )
        assert event2.severity == 10

    def test_severity_invalid_negative(self):
        with pytest.raises(Exception):
            NormalizedEvent(
                ts=datetime(2025, 8, 20, 12, 0, 0, tzinfo=timezone.utc),
                tenant="demoA",
                source=Source.api,
                event_type="test",
                severity=-5,
                raw={}
            )

    def test_severity_invalid_high(self):
        with pytest.raises(Exception):
            NormalizedEvent(
                ts=datetime(2025, 8, 20, 12, 0, 0, tzinfo=timezone.utc),
                tenant="demoA",
                source=Source.api,
                event_type="test",
                severity=15,
                raw={}
            )

    def test_invalid_src_ip_sanitized(self):
        event = NormalizedEvent(
            ts=datetime(2025, 8, 20, 12, 0, 0, tzinfo=timezone.utc),
            tenant="demoA",
            source=Source.api,
            event_type="test",
            severity=5,
            src_ip="not-an-ip",
            raw={}
        )
        assert event.src_ip is None
