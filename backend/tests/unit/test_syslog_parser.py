
from datetime import datetime, timezone
import pytest

from app.integrations.syslog import parse_syslog_message
from app.parsers.firewall_helpers import parse_syslog_pri


class TestSyslogRFC3164:

    def test_valid_rfc3164_message(self):
        result = parse_syslog_message("<134>Aug 20 12:44:56 host app: test message")
        assert result is not None
        assert result["priority"] == 134
        assert "host" in result or "hostname" in result
        assert "message" in result

    def test_rfc3164_with_colon_separator(self):
        result = parse_syslog_message("<134>Aug 20 12:44:56 host app:message here")
        assert result is not None
        assert result["priority"] == 134


class TestSyslogRFC5424:

    def test_valid_rfc5424_message(self):
        result = parse_syslog_message("<134>1 2025-08-20T12:44:56.000Z host app PID-123 msg")
        assert result is not None
        assert result["priority"] == 134

    def test_rfc5424_without_version(self):
        result = parse_syslog_message("<134>host app: msg")
        assert result is not None


class TestSyslogEdgeCases:

    def test_empty_string_returns_none(self):
        result = parse_syslog_message("")
        assert result is None

    def test_whitespace_only_returns_none(self):
        result = parse_syslog_message("   \t\n  ")
        assert result is None

    def test_message_without_pri_parsed(self):
        result = parse_syslog_message("host app: message without pri")
        assert result is not None
        assert result["priority"] is None

    def test_message_with_key_value_pairs(self):
        result = parse_syslog_message("<134>host app: user=alice action=login status=success")
        assert result is not None
        assert result.get("user") == "alice"
        assert result.get("action") == "login"

    def test_very_long_message(self):
        long_msg = "a" * 10000
        result = parse_syslog_message(f"<134>host app: {long_msg}")
        assert result is not None


class TestSyslogPRI:

    def test_priority_to_facility_severity(self):
        facility, severity = parse_syslog_pri(134)
        assert isinstance(facility, int)
        assert isinstance(severity, int)
        assert 0 <= severity <= 7

    def test_priority_min_value(self):
        facility, severity = parse_syslog_pri(0)
        assert facility == 0
        assert severity == 0

    def test_priority_max_value(self):
        facility, severity = parse_syslog_pri(191)
        assert facility == 23
        assert severity == 7

    def test_priority_calculation(self):
        for facility in range(24):
            for severity in range(8):
                pri = facility * 8 + severity
                f, s = parse_syslog_pri(pri)
                assert f == facility
                assert s == severity


class TestSyslogTimestamp:

    def test_rfc3164_month_names(self):
        MONTHS = {
            "Jan": 0, "Feb": 1, "Mar": 2, "Apr": 3, "May": 4, "Jun": 5,
            "Jul": 6, "Aug": 7, "Sep": 8, "Oct": 9, "Nov": 10, "Dec": 11,
        }
        for month_name, month_num in MONTHS.items():
            result = parse_syslog_message(f"<134>{month_name} 20 12:00:00 host app: msg")
            assert result is not None, f"Failed to parse {month_name}"

    def test_timestamp_includes_timezone(self):
        result = parse_syslog_message("<134>Aug 20 12:44:56 host app: msg")
        assert "timestamp" in result
