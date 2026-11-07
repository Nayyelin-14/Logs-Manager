"""Unit tests for Firewall Normalizer.

These tests verify pure Python parsing and normalization logic
and do not require a database connection.
"""

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


class TestTenantSecurity:
    """Tests for tenant isolation security."""

    def test_tenant_not_trusted_from_raw(self):
        raw = {
            "priority": 134,
            "src": "10.0.1.10",
            "dst": "8.8.8.8",
            "tenant": "MALICIOUS_TENANT",
        }
        event = normalize_firewall(raw, tenant="real_tenant")
        assert event.tenant == "real_tenant"

    def test_default_tenant_when_none_provided(self):
        event = normalize_firewall({"priority": 134, "src": "10.0.0.1", "dst": "10.0.0.2"})
        assert event.tenant == "default"

    def test_tenant_cannot_override_via_raw(self):
        raw = {
            "priority": 134,
            "tenant": "attacker_tenant",
            "Tenant": "attacker_tenant",
            "src": "10.0.0.1",
        }
        event = normalize_firewall(raw)
        assert event.tenant == "default"


class TestNormalizeFirewall:
    """Tests for firewall event normalization."""

    def test_normalize_firewall_deny_sample_41(self):
        raw = {
            "priority": 134,
            "timestamp": datetime(2025, 8, 20, 12, 44, 56, tzinfo=timezone.utc),
            "vendor": "demo",
            "product": "ngfw",
            "action": "deny",
            "src": "10.0.1.10",
            "dst": "8.8.8.8",
            "spt": 5353,
            "dpt": 53,
            "proto": "udp",
            "msg": "DNS blocked policy=Block-DNS",
        }

        event = normalize_firewall(raw, tenant="demoA")

        assert isinstance(event, NormalizedEvent)
        assert event.source == Source.firewall
        assert event.event_type == "firewall_deny"
        assert event.action == Action.deny
        assert event.severity == 2
        assert event.src_ip == "10.0.1.10"
        assert event.dst_ip == "8.8.8.8"
        assert event.src_port == 5353
        assert event.dst_port == 53
        assert event.protocol == "udp"
        assert event.rule_name == "Block-DNS"
        assert event.vendor == "demo"
        assert event.product == "ngfw"
        assert event.tenant == "demoA"

    def test_normalize_firewall_allow(self):
        event = normalize_firewall(
            {"priority": 134, "action": "allow", "src": "10.0.0.1", "dst": "10.0.0.2"},
            tenant="demoA",
        )
        assert event.source == Source.firewall
        assert event.event_type == "firewall_allow"
        assert event.action == Action.allow

    def test_normalize_keyvalue_message_parsing(self):
        raw = {
            "priority": 134,
            "host": "fw01",
            "msg": "vendor=demo product=ngfw action=deny src=10.0.1.10 dst=8.8.8.8",
        }
        event = normalize_firewall(raw, tenant="demoA")
        assert event.src_ip == "10.0.1.10"
        assert event.dst_ip == "8.8.8.8"

    def test_normalize_preserves_raw_data(self):
        raw = {
            "priority": 134,
            "src": "10.0.1.10",
            "dst": "8.8.8.8",
            "custom_field": "custom_value",
            "tenant": "demoA",
        }
        event = normalize_firewall(raw)
        assert event.raw is not None
        assert "src" in event.raw
        assert "custom_field" in event.raw

    def test_to_dict_compatibility(self):
        event = normalize_firewall(
            {"priority": 134, "src": "10.0.1.10", "dst": "8.8.8.8", "tenant": "demoA"}
        )
        d = event.to_db_dict()
        assert "ts" in d
        assert "@timestamp" not in d
        assert "_tags" in d
        assert "tags" not in d


class TestInvalidIpHandling:
    """Tests for invalid IP handling."""

    def test_invalid_src_ip_handled(self):
        event = normalize_firewall(
            {"priority": 134, "src": "not-an-ip", "dst": "8.8.8.8", "tenant": "demoA"}
        )
        assert event.src_ip is None
        assert isinstance(event, NormalizedEvent)

    def test_invalid_dst_ip_handled(self):
        event = normalize_firewall(
            {"priority": 134, "src": "10.0.0.1", "dst": "invalid-ip", "tenant": "demoA"}
        )
        assert event.dst_ip is None

    def test_both_ips_valid(self):
        event = normalize_firewall(
            {"priority": 134, "src": "10.0.0.1", "dst": "10.0.0.2", "tenant": "demoA"}
        )
        assert event.src_ip == "10.0.0.1"
        assert event.dst_ip == "10.0.0.2"


class TestInvalidPortHandling:
    """Tests for invalid port handling."""

    def test_invalid_port_handled(self):
        event = normalize_firewall(
            {"priority": 134, "src": "10.0.0.1", "spt": 99999, "tenant": "demoA"}
        )
        assert event.src_port is None

    def test_negative_port_handled(self):
        event = normalize_firewall(
            {"priority": 134, "src": "10.0.0.1", "spt": -1, "tenant": "demoA"}
        )
        assert event.src_port is None

    def test_valid_port(self):
        event = normalize_firewall(
            {"priority": 134, "src": "10.0.0.1", "spt": 8080, "tenant": "demoA"}
        )
        assert event.src_port == 8080


class TestMalformedTimestamps:
    """Tests for malformed timestamp handling."""

    def test_missing_timestamp_uses_now(self):
        event = normalize_firewall(
            {"priority": 134, "src": "10.0.1.10", "dst": "8.8.8.8", "tenant": "demoA"}
        )
        assert event.ts is not None

    def test_invalid_timestamp_uses_now(self):
        event = normalize_firewall(
            {"priority": 134, "timestamp": "invalid", "src": "10.0.1.10", "tenant": "demoA"}
        )
        assert event.ts is not None

    def test_timestamp_in_raw_has_parse_error_flag(self):
        event = normalize_firewall(
            {"priority": 134, "src": "10.0.1.10", "dst": "8.8.8.8", "tenant": "demoA"}
        )
        assert "_parse_error" in event.raw


class TestActionMapping:
    """Tests for action mapping."""

    def test_deny_mapping(self):
        for action in ["deny", "block", "drop", "reject"]:
            event = normalize_firewall(
                {"priority": 134, "action": action, "src": "10.0.0.1", "dst": "10.0.0.2", "tenant": "demoA"}
            )
            assert event.action == Action.deny, f"Failed for {action}"

    def test_allow_mapping(self):
        for action in ["allow", "permit", "pass"]:
            event = normalize_firewall(
                {"priority": 134, "action": action, "src": "10.0.0.1", "dst": "10.0.0.2", "tenant": "demoA"}
            )
            assert event.action == Action.allow, f"Failed for {action}"


class TestSeverityFallback:
    """Tests for severity fallback."""

    def test_all_syslog_severities(self):
        for syslog_sev, expected_sev in SYSLOG_SEVERITY_MAP.items():
            facility = 0
            raw_pri = facility * 8 + syslog_sev
            event = normalize_firewall(
                {"priority": raw_pri, "src": "10.0.0.1", "tenant": "demoA"}
            )
            assert event.severity == expected_sev, f"Failed for PRI {raw_pri} (sev {syslog_sev})"

    def test_invalid_priority_fallback(self):
        event = normalize_firewall(
            {"priority": "invalid", "src": "10.0.0.1", "tenant": "demoA"}
        )
        assert event.severity == SYSLOG_SEVERITY_MAP[6]
