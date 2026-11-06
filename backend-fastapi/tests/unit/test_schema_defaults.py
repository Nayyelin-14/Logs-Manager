"""Unit tests for NormalizedEvent Pydantic model validation - standalone version."""

from datetime import datetime, timezone

import pytest

import sys
sys.path.insert(0, '/home/nay/projects/logs/Logs-Manager/backend-fastapi')

from app.schemas.normalized_event import NormalizedEvent, Source, Action, Outcome


class TestNormalizedEventDefaults:
    """Tests for default values."""

    def test_empty_tags_default(self):
        """Test tags default to empty list."""
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
        """Test raw defaults to empty dict."""
        event = NormalizedEvent(
            ts=datetime(2025, 8, 20, 12, 0, 0, tzinfo=timezone.utc),
            tenant="demoA",
            source=Source.api,
            event_type="test",
            severity=5
        )
        assert event.raw == {}

    def test_none_optional_fields(self):
        """Test optional fields can be None or omitted."""
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
    """Tests for to_db_dict method."""

    def test_to_dict_basic(self):
        """Test basic dict conversion."""
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
        """Test that to_db_dict returns 'ts' column, not '@timestamp'."""
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
        """Test that to_db_dict returns '_tags' column for tags field."""
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
        """Test that user is correctly included when present."""
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
        """Test that enum fields are converted to their string values."""
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
        """Test that all expected database columns are in to_db_dict output."""
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
    """Tests for normalized event field validation."""

    def test_severity_valid_range(self):
        """Test severity accepts valid values 0-10."""
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
        """Test severity < 0 raises validation error."""
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
        """Test severity > 10 raises validation error."""
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
        """Invalid source IP is sanitized to None."""
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