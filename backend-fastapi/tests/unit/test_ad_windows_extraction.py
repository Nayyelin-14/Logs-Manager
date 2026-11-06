"""Unit tests for Active Directory / Windows Security normalizer."""

import pytest

from app.parsers.identity import normalize_ad
from app.models.enums import Source


class TestADSeverity:
    """Test severity mapping for AD events."""

    def test_4625_severity_7(self):
        """Event ID 4625 (failed logon) should have severity 7."""
        raw = {"EventID": 4625}

        result = normalize_ad(raw)

        assert result["severity"] == 7

    def test_4624_severity_3(self):
        """Event ID 4624 (successful logon) should have default severity 3."""
        raw = {"EventID": 4624}

        result = normalize_ad(raw)

        assert result["severity"] == 3

    def test_explicit_severity_used(self):
        """Explicit severity should override derived value."""
        raw = {"EventID": 4624, "severity": 8}

        result = normalize_ad(raw)

        assert result["severity"] == 8


class TestADIPExtraction:
    """Test IP address extraction from AD events."""

    def test_ip_address_extraction(self):
        """IpAddress should be extracted as src_ip."""
        raw = {"IpAddress": "192.168.1.50"}

        result = normalize_ad(raw)

        assert result["src_ip"] == "192.168.1.50"

    def test_ip_from_event_field(self):
        """IP can come from event-level field."""
        raw = {"ip": "10.0.0.100"}

        result = normalize_ad(raw)

        assert result["src_ip"] == "10.0.0.100"

    def test_invalid_ip_not_validated(self):
        """IP is not validated at normalization time (validation happens in schema)."""
        raw = {"IpAddress": "not-an-ip"}

        result = normalize_ad(raw)

        assert result["src_ip"] == "not-an-ip"


class TestADUserExtraction:
    """Test user name extraction from AD events."""

    def test_target_user_name(self):
        """TargetUserName should be extracted as user."""
        raw = {"TargetUserName": "testuser"}

        result = normalize_ad(raw)

        assert result["user"] == "testuser"

    def test_subject_user_name(self):
        """SubjectUserName should be used if TargetUserName not present."""
        raw = {"SubjectUserName": "subjectuser"}

        result = normalize_ad(raw)

        assert result["user"] == "subjectuser"

    def test_user_name_field(self):
        """user_name field should be used as fallback."""
        raw = {"user_name": "fielduser"}

        result = normalize_ad(raw)

        assert result["user"] == "fielduser"


class TestADHostExtraction:
    """Test host/computer name extraction from AD events."""

    def test_computer_extraction(self):
        """Computer should be extracted as host."""
        raw = {"Computer": "SERVER01.corp.local"}

        result = normalize_ad(raw)

        assert result["host"] == "SERVER01.corp.local"

    def test_hostname_field(self):
        """host field should be used as fallback."""
        raw = {"host": "HOST01"}

        result = normalize_ad(raw)

        assert result["host"] == "HOST01"

    def test_hostname_extraction(self):
        """hostname field should be used as fallback."""
        raw = {"hostname": "HOSTNAME01"}

        result = normalize_ad(raw)

        assert result["host"] == "HOSTNAME01"


class TestADEventDescription:
    """Test description handling for AD events."""

    def test_message_used_as_description(self):
        """Message field should be used as description."""
        raw = {"Message": "Test message"}

        result = normalize_ad(raw)

        assert "Test message" in result["description"]

    def test_failure_reason_used(self):
        """FailureReason should be used as description if no message."""
        raw = {"FailureReason": "Bad password"}

        result = normalize_ad(raw)

        assert "Bad password" in result["description"]

    def test_event_id_in_description(self):
        """Description should include event ID for unknown events."""
        raw = {"EventID": 4624, "TargetUserName": "testuser"}

        result = normalize_ad(raw)

        assert "4624" in result["description"]
