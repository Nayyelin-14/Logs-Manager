
from datetime import datetime, timezone
import pytest

from app.parsers.firewall import (
    parse_syslog_pri,
    parse_syslog_timestamp,
    parse_key_value_message,
    validate_ip,
    validate_port,
    normalize_firewall,
    SYSLOG_SEVERITY_MAP,
)
from app.schemas.normalized_event import NormalizedEvent, Source, Action
class TestSyslogPri:

    def test_pri_facility_and_severity(self):
        facility, severity = parse_syslog_pri(134)
        assert facility == 16
        assert severity == 6
    def test_pri_zero(self):
        facility, severity = parse_syslog_pri(0)
        assert facility == 0
        assert severity == 0
    def test_pri_boundary_values(self):
        facility, severity = parse_syslog_pri(7)
        assert facility == 0
        assert severity == 7
        facility, severity = parse_syslog_pri(8)
        assert facility == 1
        assert severity == 0

class TestSyslogSeverityMapping:

    def test_all_severity_values(self):
        assert SYSLOG_SEVERITY_MAP[0] == 10
        assert SYSLOG_SEVERITY_MAP[1] == 9
        assert SYSLOG_SEVERITY_MAP[2] == 8
        assert SYSLOG_SEVERITY_MAP[3] == 7
        assert SYSLOG_SEVERITY_MAP[4] == 5
        assert SYSLOG_SEVERITY_MAP[5] == 4
        assert SYSLOG_SEVERITY_MAP[6] == 2
        assert SYSLOG_SEVERITY_MAP[7] == 1
    def test_invalid_severity_default(self):
        assert SYSLOG_SEVERITY_MAP.get(8, 2) == 2

class TestSyslogTimestamp:

    def test_standard_timestamp(self):
        result = parse_syslog_timestamp("Aug 20 12:44:56")
        assert result is not None
        assert result.tzinfo == timezone.utc
        assert result.month == 8
        assert result.day == 20
        assert result.hour == 12
        assert result.minute == 44
        assert result.second == 56
    def test_invalid_timestamp(self):
        result = parse_syslog_timestamp("invalid")
        assert result is None

    def test_empty_timestamp(self):
        result = parse_syslog_timestamp("")
        assert result is None

    def test_missing_time(self):
        result = parse_syslog_timestamp("Aug 20")
        assert result is None

    def test_january_with_november_reference(self):
        ref = datetime(2026, 11, 15, tzinfo=timezone.utc)
        result = parse_syslog_timestamp("Jan 15 10:30:00", reference_time=ref)
        assert result is not None
        assert result.year == 2027
        assert result.month == 1
    def test_december_with_january_reference(self):
        ref = datetime(2027, 1, 15, tzinfo=timezone.utc)
        result = parse_syslog_timestamp("Dec 15 10:30:00", reference_time=ref)
        assert result is not None
        assert result.year == 2026
    def test_december_with_december_reference(self):
        ref = datetime(2026, 12, 15, tzinfo=timezone.utc)
        result = parse_syslog_timestamp("Dec 31 23:59:59", reference_time=ref)
        assert result is not None
        assert result.year == 2026
        assert result.month == 12
        assert result.day == 31
    def test_normal_same_year(self):
        ref = datetime(2026, 8, 15, tzinfo=timezone.utc)
        result = parse_syslog_timestamp("Aug 20 12:44:56", reference_time=ref)
        assert result is not None
        assert result.year == 2026
    def test_returns_utc_timezone_aware(self):
        result = parse_syslog_timestamp("Jan 01 00:00:00")
        assert result is not None
        assert result.tzinfo == timezone.utc
    def test_january_with_november_reference_closest(self):
        ref = datetime(2026, 11, 15, 12, 0, 0, tzinfo=timezone.utc)
        result = parse_syslog_timestamp("Jan 15 10:00:00", reference_time=ref)
        assert result is not None
        assert result.year == 2027
        assert result.month == 1
    def test_december_with_january_reference_closest(self):
        ref = datetime(2027, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        result = parse_syslog_timestamp("Dec 15 10:00:00", reference_time=ref)
        assert result is not None
        assert result.year == 2026
    def test_december_with_december_reference_closest(self):
        ref = datetime(2026, 12, 20, 12, 0, 0, tzinfo=timezone.utc)
        result = parse_syslog_timestamp("Dec 31 23:59:59", reference_time=ref)
        assert result is not None
        assert result.year == 2026
    def test_year_boundary_dec31_ref_jan1(self):
        ref = datetime(2027, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        result = parse_syslog_timestamp("Dec 31 23:59:59", reference_time=ref)
        assert result is not None
        assert result.year == 2026
    def test_year_boundary_jan1_ref_dec31(self):
        ref = datetime(2026, 12, 31, 0, 0, 0, tzinfo=timezone.utc)
        result = parse_syslog_timestamp("Jan 01 00:00:00", reference_time=ref)
        assert result is not None
        assert result.year == 2027
    def test_same_month_close_time(self):
        ref = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)
        result = parse_syslog_timestamp("Aug 15 10:00:00", reference_time=ref)
        assert result is not None
        assert result.year == 2026
    def test_naive_reference_time(self):
        ref = datetime(2026, 8, 15, 12, 0, 0)
        result = parse_syslog_timestamp("Aug 20 12:00:00", reference_time=ref)
        assert result is not None
        assert result.tzinfo == timezone.utc
        assert result.year == 2026
    def test_naive_reference_time(self):
        ref = datetime(2026, 8, 15, 12, 0, 0)
        result = parse_syslog_timestamp("Aug 20 12:00:00", reference_time=ref)
        assert result is not None
        assert result.tzinfo == timezone.utc
        assert result.year == 2026
    def test_leap_day_feb29_valid(self):
        ref = datetime(2024, 3, 1, tzinfo=timezone.utc)
        result = parse_syslog_timestamp("Feb 29 12:00:00", reference_time=ref)
        assert result is not None
        assert result.year == 2024
        assert result.month == 2
        assert result.day == 29
    def test_leap_day_feb29_skipped_in_non_leap(self):
        ref = datetime(2023, 3, 1, tzinfo=timezone.utc)
        result = parse_syslog_timestamp("Feb 29 12:00:00", reference_time=ref)
        assert result is not None
        assert result.year == 2024
        assert result.month == 2
        assert result.day == 29
    def test_invalid_month_name(self):
        result = parse_syslog_timestamp("Xyz 15 12:00:00")
        assert result is None
    def test_malformed_timestamp_missing_components(self):
        result = parse_syslog_timestamp("Aug 20")
        assert result is None
class TestKeyValueParsing:

    def test_simple_pairs(self):
        result = parse_key_value_message("src=10.0.1.10 dst=8.8.8.8")
        assert result["src"] == "10.0.1.10"
        assert result["dst"] == "8.8.8.8"
    def test_value_with_spaces(self):
        result = parse_key_value_message("msg=DNS blocked policy=Block-DNS")
        assert result["msg"] == "DNS blocked"
        assert result["policy"] == "Block-DNS"
    def test_empty_message(self):
        result = parse_key_value_message("")
        assert result == {}

    def test_complex_message(self):
        result = parse_key_value_message(
            "vendor=demo product=ngfw action=deny src=10.0.1.10 dst=8.8.8.8 spt=5353 dpt=53 proto=udp msg=DNS blocked policy=Block-DNS"
        )
        assert result["vendor"] == "demo"
        assert result["product"] == "ngfw"
        assert result["action"] == "deny"
        assert result["src"] == "10.0.1.10"
        assert result["dst"] == "8.8.8.8"
    def test_value_containing_equals(self):
        result = parse_key_value_message("url=https://example.com?a=b")
        assert "url" in result

    def test_no_keyvalue_pairs(self):
        result = parse_key_value_message("just a plain message")
        assert result == {}

    def test_duplicate_keys(self):
        result = parse_key_value_message("key=first key=second")
        assert result["key"] == "first"

class TestIpValidation:

    def test_valid_ipv4(self):
        assert validate_ip("192.168.1.1") == "192.168.1.1"
    def test_valid_ipv6(self):
        assert validate_ip("2001:db8::1") == "2001:db8::1"
    def test_invalid_ip(self):
        assert validate_ip("not-an-ip") is None
    def test_none_ip(self):
        assert validate_ip(None) is None

class TestPortValidation:

    def test_valid_port(self):
        assert validate_port(80) == 80
        assert validate_port(65535) == 65535
        assert validate_port(0) == 0
    def test_port_too_high(self):
        assert validate_port(70000) is None
    def test_port_negative(self):
        assert validate_port(-1) is None
    def test_none_port(self):
        assert validate_port(None) is None
    def test_string_port(self):
        assert validate_port("8080") == 8080
