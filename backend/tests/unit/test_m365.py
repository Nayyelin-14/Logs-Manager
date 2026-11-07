"""Unit tests for Microsoft 365 normalizer."""

import pytest

from app.parsers.identity import normalize_m365
from app.models.enums import Source


class TestM365Basic:
    """Basic Microsoft 365 normalization tests."""

    def test_normalize_user_logged_in(self):
        """Test normalizing an M365 UserLoggedIn event."""
        raw = {
            "source": "m365",
            "Operation": "UserLoggedIn",
            "Workload": "AzureActiveDirectory",
            "RecordType": 15,
            "UserId": "alice@example.com",
            "ClientIP": "203.0.113.20",
            "ResultStatus": "Success",
            "CreationTime": "2026-10-30T22:18:00Z",
            "OrganizationId": "11111111-2222-3333-4444-555555555555",
        }

        result = normalize_m365(raw)

        assert result["source"] == Source.M365
        assert result["event_type"] == "UserLoggedIn"
        assert result["canonical_event_type"] == "m365_user_login"
        assert result["user"] == "alice@example.com"
        assert result["src_ip"] == "203.0.113.20"
        assert result["product"] == "AzureActiveDirectory"
        assert result["vendor"] == "microsoft"

    def test_timestamp_utc_conversion(self):
        """Test timestamp is parsed and returned as ISO format string."""
        raw = {"CreationTime": "2026-10-30T22:18:00Z"}

        result = normalize_m365(raw)

        assert result["timestamp"] == "2026-10-30T22:18:00+00:00"

    def test_raw_preserved(self):
        """Test raw event is preserved unchanged."""
        raw = {"Operation": "UserLoggedIn", "extra": "data"}

        result = normalize_m365(raw)

        assert result["raw"] == raw


class TestM365EventTypes:
    """Test various M365 event type mappings."""

    def test_user_loggend_in(self):
        """UserLoggedIn maps to canonical m365_user_login."""
        raw = {"Operation": "UserLoggedIn"}

        result = normalize_m365(raw)

        assert result["canonical_event_type"] == "m365_user_login"

    def test_mailbox_login(self):
        """MailboxLogin maps to m365_mailbox_login."""
        raw = {"Operation": "MailboxLogin"}

        result = normalize_m365(raw)

        assert result["canonical_event_type"] == "m365_mailbox_login"

    def test_user_added_to_group(self):
        """AddMemberToGroup maps to m365_admin_action."""
        raw = {"Operation": "AddMemberToGroup"}

        result = normalize_m365(raw)

        assert result["canonical_event_type"] == "m365_admin_action"


class TestM365Outcome:
    """Test outcome determination for M365 events."""

    def test_success_outcome(self):
        """Success status should result in success outcome."""
        raw = {"Operation": "UserLoggedIn", "ResultStatus": "Success"}

        result = normalize_m365(raw)

        assert result["outcome"] == "success"

    def test_failure_outcome(self):
        """Failure status should result in failure outcome."""
        raw = {"Operation": "MailboxLogin", "ResultStatus": "Failure"}

        result = normalize_m365(raw)

        assert result["outcome"] == "failure"

    def test_success_status_overrides_event_name(self):
        """Success status takes precedence over event name containing 'failed'."""
        raw = {"Operation": "failed_login", "ResultStatus": "Success"}

        result = normalize_m365(raw)

        assert result["outcome"] == "success"

    def test_failure_status_overrides_event_name(self):
        """Failure status takes precedence over event name containing 'success'."""
        raw = {"Operation": "successful_operation", "ResultStatus": "Failure"}

        result = normalize_m365(raw)

        assert result["outcome"] == "failure"


class TestM365Action:
    """Test action mapping for M365 events."""

    def test_user_loggined_maps_to_login(self):
        """UserLoggedIn maps to login action."""
        raw = {"Operation": "UserLoggedIn"}

        result = normalize_m365(raw)

        assert result["action"] == "LOGIN"

    def test_logout_maps_to_logout(self):
        """UserLoggedOut maps to logout action."""
        raw = {"Operation": "UserLoggedOut"}

        result = normalize_m365(raw)

        assert result["action"] == "LOGOUT"

    def test_delete_maps_to_delete(self):
        """Delete operations map to delete action."""
        raw = {"Operation": "Delete"}

        result = normalize_m365(raw)

        assert result["action"] == "DELETE"

    def test_create_maps_to_create(self):
        """Create operations map to create action."""
        raw = {"Operation": "Create"}

        result = normalize_m365(raw)

        assert result["action"] == "CREATE"


class TestM365IPExtraction:
    """Test IP address extraction from M365 events."""

    def test_client_ip_extraction(self):
        """ClientIP should be extracted as src_ip."""
        raw = {"ClientIP": "198.51.100.23"}

        result = normalize_m365(raw)

        assert result["src_ip"] == "198.51.100.23"

    def test_ip_from_event(self):
        """IP can come from event-level field."""
        raw = {"ip": "203.0.113.30"}

        result = normalize_m365(raw)

        assert result["src_ip"] == "203.0.113.30"

    def test_invalid_ip_not_validated(self):
        """IP is not validated at normalization time (validation happens in schema)."""
        raw = {"ClientIP": "not-an-ip"}

        result = normalize_m365(raw)

        assert result["src_ip"] == "not-an-ip"


class TestM365Severity:
    """Test severity mapping for M365 events."""

    def test_failure_status_severity(self):
        """Failed operations without explicit status should have default severity."""
        raw = {"Operation": "SomeOperation", "ResultStatus": "Failure"}

        result = normalize_m365(raw)

        assert result["severity"] == 2

    def test_success_derives_severity_2(self):
        """Successful operations without explicit severity should have severity 2."""
        raw = {"Operation": "SomeOperation", "ResultStatus": "Success"}

        result = normalize_m365(raw)

        assert result["severity"] == 2

    def test_explicit_severity_used(self):
        """Explicit severity should override derived value."""
        raw = {"Operation": "SomeOperation", "severity": 8}

        result = normalize_m365(raw)

        assert result["severity"] == 8