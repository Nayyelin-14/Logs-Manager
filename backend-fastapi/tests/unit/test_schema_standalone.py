"""Unit tests for NormalizedEvent Pydantic model validation - standalone version."""

from datetime import datetime, timezone

import pytest

import sys
sys.path.insert(0, '/home/nay/projects/logs/Logs-Manager/backend-fastapi')

from app.schemas.normalized_event import NormalizedEvent, Source, Action, Outcome


class TestNormalizedEventBasic:
    """Basic validation tests for NormalizedEvent."""

    def test_required_fields(self):
        """Test that required fields are enforced."""
        with pytest.raises(Exception):
            NormalizedEvent(
                tenant="demoA",
                event_type="test",
                severity=5,
                raw={}
            )

    def test_minimal_valid_event(self):
        """Test creation of a minimal valid event."""
        ts = datetime(2025, 8, 20, 12, 0, 0, tzinfo=timezone.utc)
        event = NormalizedEvent(
            id="test123",
            ts=ts,
            tenant="demoA",
            source=Source.firewall,
            event_type="test_event",
            severity=5,
            raw={"key": "value"},
            tags=["test"]
        )
        assert event.id == "test123"
        assert event.ts == ts
        assert event.tenant == "demoA"
        assert event.source == Source.firewall
        assert event.event_type == "test_event"
        assert event.severity == 5
        assert event.raw == {"key": "value"}
        assert event.tags == ["test"]

    def test_timestamp_utc_conversion(self):
        """Test that timestamps are converted to UTC."""
        ts_naive = datetime(2025, 8, 20, 12, 0, 0)
        event = NormalizedEvent(
            ts=ts_naive,
            tenant="demoA",
            source=Source.api,
            event_type="test",
            severity=5,
            raw={}
        )
        assert event.ts.tzinfo is not None
        assert event.ts.tzinfo == timezone.utc

    def test_timestamp_iso8601_parsing(self):
        """Test parsing ISO8601 timestamp string."""
        event = NormalizedEvent(
            ts="2025-08-20T12:00:00Z",
            tenant="demoA",
            source=Source.api,
            event_type="test",
            severity=5,
            raw={}
        )
        assert event.ts.year == 2025
        assert event.ts.month == 8
        assert event.ts.day == 20

    def test_id_generation(self):
        """Test automatic ID generation when not provided."""
        ts = datetime(2025, 8, 20, 12, 0, 0, tzinfo=timezone.utc)
        event = NormalizedEvent(
            ts=ts,
            tenant="demoA",
            source=Source.firewall,
            event_type="test",
            severity=5,
            raw={"foo": "bar"}
        )
        assert len(event.id) == 64
        assert isinstance(event.id, str)

    def test_deterministic_id(self):
        """Test that same inputs produce same ID."""
        ts = datetime(2025, 8, 20, 12, 0, 0, tzinfo=timezone.utc)
        event1 = NormalizedEvent(
            ts=ts,
            tenant="demoA",
            source=Source.firewall,
            event_type="test",
            severity=5,
            raw={"foo": "bar"}
        )
        event2 = NormalizedEvent(
            ts=ts,
            tenant="demoA",
            source=Source.firewall,
            event_type="test",
            severity=5,
            raw={"foo": "bar"}
        )
        assert event1.id == event2.id


class TestNormalizedEventFieldValidation:
    """Tests for field validation."""

    def test_severity_valid_range(self):
        """Test severity accepts values 0-10."""
        event = NormalizedEvent(
            ts=datetime(2025, 8, 20, 12, 0, 0, tzinfo=timezone.utc),
            tenant="demoA",
            source=Source.api,
            event_type="test",
            severity=10,
            raw={}
        )
        assert event.severity == 10

    def test_severity_rejects_over_10(self):
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

    def test_severity_rejects_negative(self):
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

    def test_valid_ipv4_src_ip(self):
        """Test valid IPv4 address accepted."""
        event = NormalizedEvent(
            ts=datetime(2025, 8, 20, 12, 0, 0, tzinfo=timezone.utc),
            tenant="demoA",
            source=Source.api,
            event_type="test",
            severity=5,
            src_ip="192.168.1.1",
            raw={}
        )
        assert event.src_ip == "192.168.1.1"

    def test_valid_ipv6_src_ip(self):
        """Test valid IPv6 address accepted."""
        event = NormalizedEvent(
            ts=datetime(2025, 8, 20, 12, 0, 0, tzinfo=timezone.utc),
            tenant="demoA",
            source=Source.api,
            event_type="test",
            severity=5,
            src_ip="2001:db8::1",
            raw={}
        )
        assert event.src_ip == "2001:db8::1"

    def test_invalid_port_rejected(self):
        """Test port above 65535 raises validation error."""
        with pytest.raises(Exception):
            NormalizedEvent(
                ts=datetime(2025, 8, 20, 12, 0, 0, tzinfo=timezone.utc),
                tenant="demoA",
                source=Source.api,
                event_type="test",
                severity=5,
                src_port=70000,
                raw={}
            )

    def test_valid_port(self):
        """Test valid port accepted."""
        event = NormalizedEvent(
            ts=datetime(2025, 8, 20, 12, 0, 0, tzinfo=timezone.utc),
            tenant="demoA",
            source=Source.api,
            event_type="test",
            severity=5,
            src_port=53,
            raw={}
        )
        assert event.src_port == 53


class TestNormalizedEventEnums:
    """Tests for enum fields."""

    def test_source_enum_values(self):
        """Test all source enum values."""
        sources = ["firewall", "crowdstrike", "aws", "m365", "ad", "api", "network"]
        for s in sources:
            event = NormalizedEvent(
                ts=datetime(2025, 8, 20, 12, 0, 0, tzinfo=timezone.utc),
                tenant="demoA",
                source=s,
                event_type="test",
                severity=5,
                raw={}
            )
            assert event.source == s

    def test_action_enum_values(self):
        """Test action enum values."""
        actions = ["allow", "deny", "create", "delete", "login", "logout", "alert", "other"]
        for a in actions:
            event = NormalizedEvent(
                ts=datetime(2025, 8, 20, 12, 0, 0, tzinfo=timezone.utc),
                tenant="demoA",
                source=Source.api,
                event_type="test",
                severity=5,
                action=a,
                raw={}
            )
            assert event.action == a

    def test_outcome_enum_values(self):
        """Test outcome enum values."""
        outcomes = ["success", "failure", "unknown"]
        for o in outcomes:
            event = NormalizedEvent(
                ts=datetime(2025, 8, 20, 12, 0, 0, tzinfo=timezone.utc),
                tenant="demoA",
                source=Source.api,
                event_type="test",
                severity=5,
                outcome=o,
                raw={}
            )
            assert event.outcome == o
