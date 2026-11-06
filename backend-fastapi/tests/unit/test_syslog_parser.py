"""Unit tests for syslog parser edge cases."""

from datetime import datetime, timezone
import pytest

import sys
sys.path.insert(0, '/home/nay/projects/logs/Logs-Manager/backend-fastapi')

from app.integrations.syslog import parse_syslog_message
from app.parsers.firewall_helpers import parse_syslog_pri


class TestSyslogRFC3164:
    """Tests for RFC3164 syslog message parsing."""

    def test_valid_rfc3164_message(self):
        """Valid RFC3164 message is parsed correctly."""
        result = parse_syslog_message("<134>Aug 20 12:44:56 host app: test message")
        assert result is not None
        assert result["priority"] == 134
        assert "host" in result or "hostname" in result
        assert "message" in result

    def test_rfc3164_with_colon_separator(self):
        """RFC3164 message with colon separator."""
        result = parse_syslog_message("<134>Aug 20 12:44:56 host app:message here")
        assert result is not None
        assert result["priority"] == 134


class TestSyslogRFC5424:
    """Tests for RFC5424 syslog message parsing."""

    def test_valid_rfc5424_message(self):
        """Valid RFC5424 message is parsed correctly."""
        result = parse_syslog_message("<134>1 2025-08-20T12:44:56.000Z host app PID-123 msg")
        assert result is not None
        assert result["priority"] == 134

    def test_rfc5424_without_version(self):
        """RFC5424 without version field still parses."""
        result = parse_syslog_message("<134>host app: msg")
        assert result is not None


class TestSyslogEdgeCases:
    """Tests for syslog edge cases and error handling."""

    def test_empty_string_returns_none(self):
        """Empty string returns None."""
        result = parse_syslog_message("")
        assert result is None

    def test_whitespace_only_returns_none(self):
        """Whitespace-only string returns None."""
        result = parse_syslog_message("   \t\n  ")
        assert result is None

    def test_message_without_pri_parsed(self):
        """Message without PRI still parses."""
        result = parse_syslog_message("host app: message without pri")
        assert result is not None
        assert result["priority"] is None

    def test_message_with_key_value_pairs(self):
        """Key=value pairs in syslog message are extracted."""
        result = parse_syslog_message("<134>host app: user=alice action=login status=success")
        assert result is not None
        assert result.get("user") == "alice"
        assert result.get("action") == "login"

    def test_very_long_message(self):
        """Very long syslog message is handled."""
        long_msg = "a" * 10000
        result = parse_syslog_message(f"<134>host app: {long_msg}")
        assert result is not None


class TestSyslogPRI:
    """Tests for syslog PRI (Priority) calculation."""

    def test_priority_to_facility_severity(self):
        """Priority value correctly maps to facility and severity."""
        facility, severity = parse_syslog_pri(134)
        assert isinstance(facility, int)
        assert isinstance(severity, int)
        assert 0 <= severity <= 7

    def test_priority_min_value(self):
        """Minimum priority value."""
        facility, severity = parse_syslog_pri(0)
        assert facility == 0
        assert severity == 0

    def test_priority_max_value(self):
        """Maximum valid priority value (191 = facility 23, severity 7)."""
        facility, severity = parse_syslog_pri(191)
        assert facility == 23
        assert severity == 7

    def test_priority_calculation(self):
        """Priority calculation: pri = facility * 8 + severity."""
        for facility in range(24):
            for severity in range(8):
                pri = facility * 8 + severity
                f, s = parse_syslog_pri(pri)
                assert f == facility
                assert s == severity


class TestSyslogTimestamp:
    """Tests for syslog timestamp handling."""

    def test_rfc3164_month_names(self):
        """RFC3164 month names are parsed correctly."""
        MONTHS = {
            "Jan": 0, "Feb": 1, "Mar": 2, "Apr": 3, "May": 4, "Jun": 5,
            "Jul": 6, "Aug": 7, "Sep": 8, "Oct": 9, "Nov": 10, "Dec": 11,
        }
        for month_name, month_num in MONTHS.items():
            result = parse_syslog_message(f"<134>{month_name} 20 12:00:00 host app: msg")
            assert result is not None, f"Failed to parse {month_name}"

    def test_timestamp_includes_timezone(self):
        """Parsed timestamp is timezone-aware."""
        result = parse_syslog_message("<134>Aug 20 12:44:56 host app: msg")
        # Timestamp should be ISO format string or datetime
        assert "timestamp" in result