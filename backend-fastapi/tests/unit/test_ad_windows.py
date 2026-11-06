"""Unit tests for Active Directory / Windows Security normalizer."""

import pytest

from app.parsers.identity import normalize_ad
from app.models.enums import Source


class TestADWindowsBasic:
    """Basic Active Directory normalization tests."""

    def test_normalize_4624_logon_success(self):
        """Test normalizing AD Event 4624 (successful logon)."""
        raw = {
            "EventID": 4624,
            "TargetUserName": "alice",
            "SubjectUserName": "alice",
            "Computer": "DC01.corp.example.com",
            "IpAddress": "10.0.0.77",
            "LogonType": 3,
            "Status": "0x0",
            "Message": "An account was successfully logged on",
            "TimeCreated": "2026-10-30T22:19:00Z",
        }

        result = normalize_ad(raw)

        assert result["source"] == Source.AD
        assert result["event_type"] == "ad_logon_success"
        assert result["canonical_event_type"] == "ad_logon_success"
        assert result["user"] == "alice"
        assert result["src_ip"] == "10.0.0.77"
        assert result["host"] == "DC01.corp.example.com"
        assert result["event_id"] == 4624
        assert result["logon_type"] == 3

    def test_normalize_4625_logon_failure(self):
        """Test normalizing AD Event 4625 (failed logon)."""
        raw = {
            "EventID": 4625,
            "TargetUserName": "alice",
            "Computer": "DC01.corp.example.com",
            "IpAddress": "10.0.0.77",
            "LogonType": 3,
            "Status": "0xC000006D",
            "Message": "An account failed to log on",
            "TimeCreated": "2026-10-30T22:19:00Z",
        }

        result = normalize_ad(raw)

        assert result["source"] == Source.AD
        assert result["event_type"] == "ad_logon_failed"
        assert result["canonical_event_type"] == "ad_logon_failed"
        assert result["event_id"] == 4625
        assert result["user"] == "alice"
        assert result["outcome"] == "failure"

    def test_timestamp_utc_conversion(self):
        """Test timestamp is parsed and returned as ISO format string."""
        raw = {"TimeCreated": "2026-10-30T22:19:00Z"}

        result = normalize_ad(raw)

        assert result["timestamp"] == "2026-10-30T22:19:00+00:00"

    def test_raw_preserved(self):
        """Test raw event is preserved unchanged."""
        raw = {"EventID": 4624, "extra": "data"}

        result = normalize_ad(raw)

        assert "EventID" in result["raw"]


class TestADEventIdMapping:
    """Test Event ID to event type mapping."""

    def test_4624_succeeds(self):
        """Event ID 4624 maps to ad_logon_success."""
        raw = {"EventID": 4624}

        result = normalize_ad(raw)

        assert result["event_type"] == "ad_logon_success"

    def test_4625_fails(self):
        """Event ID 4625 maps to ad_logon_failed."""
        raw = {"EventID": 4625}

        result = normalize_ad(raw)

        assert result["event_type"] == "ad_logon_failed"

    def test_4634_logoff(self):
        """Event ID 4634 maps to ad_logoff."""
        raw = {"EventID": 4634}

        result = normalize_ad(raw)

        assert result["event_type"] == "ad_logoff"

    def test_4720_user_created(self):
        """Event ID 4720 maps to ad_user_created."""
        raw = {"EventID": 4720}

        result = normalize_ad(raw)

        assert result["event_type"] == "ad_user_created"

    def test_4726_user_deleted(self):
        """Event ID 4726 maps to ad_user_deleted."""
        raw = {"EventID": 4726}

        result = normalize_ad(raw)

        assert result["event_type"] == "ad_user_deleted"


class TestADActionMapping:
    """Test action mapping for AD events."""

    def test_4624_login_action(self):
        """Event ID 4624 maps to LOGIN action."""
        raw = {"EventID": 4624}

        result = normalize_ad(raw)

        assert result["action"] == "LOGIN"

    def test_4625_login_action(self):
        """Event ID 4625 maps to LOGIN action."""
        raw = {"EventID": 4625}

        result = normalize_ad(raw)

        assert result["action"] == "LOGIN"

    def test_4634_logout_action(self):
        """Event ID 4634 maps to LOGOUT action."""
        raw = {"EventID": 4634}

        result = normalize_ad(raw)

        assert result["action"] == "LOGOUT"

    def test_4720_create_user_action(self):
        """Event ID 4720 maps to CREATE action."""
        raw = {"EventID": 4720}

        result = normalize_ad(raw)

        assert result["action"] == "CREATE"

    def test_4726_delete_action(self):
        """Event ID 4726 maps to DELETE action."""
        raw = {"EventID": 4726}

        result = normalize_ad(raw)

        assert result["action"] == "DELETE"


class TestADOutcome:
    """Test outcome determination for AD events."""

    def test_4624_success(self):
        """Event ID 4624 should have success outcome."""
        raw = {"EventID": 4624}

        result = normalize_ad(raw)

        assert result["outcome"] == "success"

    def test_4625_failure(self):
        """Event ID 4625 should have failure outcome."""
        raw = {"EventID": 4625}

        result = normalize_ad(raw)

        assert result["outcome"] == "failure"

    def test_4634_unknown(self):
        """Event ID 4634 (logoff) should have unknown outcome."""
        raw = {"EventID": 4634}

        result = normalize_ad(raw)

        assert result["outcome"] == "unknown"
