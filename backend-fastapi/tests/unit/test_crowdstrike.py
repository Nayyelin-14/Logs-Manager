"""Unit tests for CrowdStrike normalizer."""

import pytest

from app.parsers.cloud import normalize_crowdstrike
from app.models.enums import Source


class TestCrowdStrikeBasic:
    """Basic CrowdStrike normalization tests."""

    def test_normalize_malware_detected(self):
        """Test normalizing a CrowdStrike malware_detected event."""
        raw = {
            "source": "crowdstrike",
            "event": {
                "DetectName": "MalwareDetected",
                "ComputerName": "WIN-ENG-01",
                "UserName": "alice",
                "FileName": "invoice.exe",
                "CommandLine": "C:\\Users\\alice\\Downloads\\invoice.exe",
                "Severity": 8,
                "SHA256String": "9f2c1d7b4a6e8f0c3b5d7a9e1f2c4b6d8e0f1a3c5b7d9e1f2a4c6b8d0e1f3a5c",
                "SourceIpAddress": "10.0.0.42",
                "timestamp": "2026-10-30T22:16:00Z",
                "DetectDescription": "Malicious executable blocked by Falcon",
            },
        }

        result = normalize_crowdstrike(raw)

        assert result["source"] == Source.CROWDSTRIKE
        assert result["event_type"] == "MalwareDetected"
        assert result["canonical_event_type"] == "malware_detected"
        assert result["host"] == "WIN-ENG-01"
        assert result["process"] == "invoice.exe"
        assert result["severity"] == 8
        assert result["src_ip"] == "10.0.0.42"
        assert result["vendor"] == "crowdstrike"
        assert result["product"] == "falcon"

    def test_timestamp_utc_conversion(self):
        """Test timestamp is parsed and returned as ISO format string."""
        raw = {"event": {"timestamp": "2026-10-30T22:16:00Z"}}

        result = normalize_crowdstrike(raw)

        assert result["timestamp"] == "2026-10-30T22:16:00+00:00"

    def test_raw_preserved(self):
        """Test raw event is preserved unchanged."""
        raw = {"event": {"DetectName": "MalwareDetected", "extra": "data"}}

        result = normalize_crowdstrike(raw)

        assert result["raw"] == raw


class TestCrowdStrikeEventTypes:
    """Test various CrowdStrike event type mappings."""

    def test_malware_detected_canonical(self):
        """MalwareDetected maps to canonical malware_detected."""
        raw = {"eventType": "MalwareDetected"}

        result = normalize_crowdstrike(raw)

        assert result["canonical_event_type"] == "malware_detected"

    def test_threat_detected_canonical(self):
        """Threat detection events map to canonical threat_detected."""
        raw = {"eventType": "ThreatDetected"}

        result = normalize_crowdstrike(raw)

        assert result["canonical_event_type"] == "threat_detected"

    def test_process_blocked_canonical(self):
        """Process blocked events map to canonical process_blocked."""
        raw = {"eventType": "ProcessBlocked"}

        result = normalize_crowdstrike(raw)

        assert result["canonical_event_type"] == "process_blocked"


class TestCrowdStrikeSHA256Preservation:
    """Test SHA256 preservation in CrowdStrike events."""

    def test_sha256_extracted(self):
        """SHA256 hash should be extracted from event."""
        sha256_hash = "abc123def456"
        raw = {"event": {"SHA256String": sha256_hash}}

        result = normalize_crowdstrike(raw)

        assert result["sha256"] == sha256_hash

    def test_sha256_from_various_fields(self):
        """SHA256 can come from multiple field names."""
        raw = {"event": {"SHA256": "hash123"}}

        result = normalize_crowdstrike(raw)

        assert result["sha256"] == "hash123"


class TestCrowdStrikeSeverity:
    """Test severity handling in CrowdStrike events."""

    def test_severity_from_field(self):
        """Severity should be extracted from event."""
        raw = {"event": {"Severity": 9}}

        result = normalize_crowdstrike(raw)

        assert result["severity"] == 9

    def test_severity_clamped(self):
        """Severity should be clamped to 0-10 range."""
        raw = {"event": {"Severity": 15}}

        result = normalize_crowdstrike(raw)

        assert result["severity"] == 10

    def test_default_severity_zero(self):
        """Events without severity should default to 0."""
        raw = {"event": {}}

        result = normalize_crowdstrike(raw)

        assert result["severity"] == 0


class TestCrowdStrikeIPExtraction:
    """Test IP address extraction from CrowdStrike events."""

    def test_source_ip_extraction(self):
        """Source IP should be extracted from event."""
        raw = {"event": {"SourceIpAddress": "192.168.1.100"}}

        result = normalize_crowdstrike(raw)

        assert result["src_ip"] == "192.168.1.100"

    def test_local_address_extraction(self):
        """LocalAddressIP4 field should be used for src_ip."""
        raw = {"event": {"LocalAddressIP4": "10.0.0.50"}}

        result = normalize_crowdstrike(raw)

        assert result["src_ip"] == "10.0.0.50"

    def test_invalid_ip_not_validated(self):
        """IP is not validated at normalization time (validation happens in schema)."""
        raw = {"event": {"SourceIpAddress": "not-an-ip"}}

        result = normalize_crowdstrike(raw)

        assert result["src_ip"] == "not-an-ip"


class TestCrowdStrikeAction:
    """Test action extraction from CrowdStrike events."""

    def test_action_extraction(self):
        """Action should be extracted from event."""
        raw = {"event": {"action": "ALERT"}}

        result = normalize_crowdstrike(raw)

        assert result["action"] == "ALERT"

    def test_default_alert_action(self):
        """Event without action should default to ALERT."""
        raw = {"event": {}}

        result = normalize_crowdstrike(raw)

        assert result["action"] == "ALERT"

    def test_action_uppercased(self):
        """Action should be uppercased."""
        raw = {"event": {"action": "alert"}}

        result = normalize_crowdstrike(raw)

        assert result["action"] == "ALERT"