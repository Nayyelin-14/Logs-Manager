import pytest

from app.parsers.identity import normalize_m365
from app.models.enums import Source


class TestM365Basic:

    def test_normalize_user_logged_in(self):
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
        raw = {"CreationTime": "2026-10-30T22:18:00Z"}

        result = normalize_m365(raw)

        assert result["timestamp"] == "2026-10-30T22:18:00+00:00"

    def test_raw_preserved(self):
        raw = {"Operation": "UserLoggedIn", "extra": "data"}

        result = normalize_m365(raw)

        assert result["raw"] == raw


class TestM365EventTypes:

    def test_user_loggend_in(self):
        raw = {"Operation": "UserLoggedIn"}

        result = normalize_m365(raw)

        assert result["canonical_event_type"] == "m365_user_login"

    def test_mailbox_login(self):
        raw = {"Operation": "MailboxLogin"}

        result = normalize_m365(raw)

        assert result["canonical_event_type"] == "m365_mailbox_login"

    def test_user_added_to_group(self):
        raw = {"Operation": "AddMemberToGroup"}

        result = normalize_m365(raw)

        assert result["canonical_event_type"] == "m365_admin_action"


class TestM365Outcome:

    def test_success_outcome(self):
        raw = {"Operation": "UserLoggedIn", "ResultStatus": "Success"}

        result = normalize_m365(raw)

        assert result["outcome"] == "success"

    def test_failure_outcome(self):
        raw = {"Operation": "MailboxLogin", "ResultStatus": "Failure"}

        result = normalize_m365(raw)

        assert result["outcome"] == "failure"

    def test_success_status_overrides_event_name(self):
        raw = {"Operation": "failed_login", "ResultStatus": "Success"}

        result = normalize_m365(raw)

        assert result["outcome"] == "success"

    def test_failure_status_overrides_event_name(self):
        raw = {"Operation": "successful_operation", "ResultStatus": "Failure"}

        result = normalize_m365(raw)

        assert result["outcome"] == "failure"


class TestM365Action:

    def test_user_loggined_maps_to_login(self):
        raw = {"Operation": "UserLoggedIn"}

        result = normalize_m365(raw)

        assert result["action"] == "LOGIN"

    def test_logout_maps_to_logout(self):
        raw = {"Operation": "UserLoggedOut"}

        result = normalize_m365(raw)

        assert result["action"] == "LOGOUT"

    def test_delete_maps_to_delete(self):
        raw = {"Operation": "Delete"}

        result = normalize_m365(raw)

        assert result["action"] == "DELETE"

    def test_create_maps_to_create(self):
        raw = {"Operation": "Create"}

        result = normalize_m365(raw)

        assert result["action"] == "CREATE"


class TestM365IPExtraction:

    def test_client_ip_extraction(self):
        raw = {"ClientIP": "198.51.100.23"}

        result = normalize_m365(raw)

        assert result["src_ip"] == "198.51.100.23"

    def test_ip_from_event(self):
        raw = {"ip": "203.0.113.30"}

        result = normalize_m365(raw)

        assert result["src_ip"] == "203.0.113.30"

    def test_invalid_ip_not_validated(self):
        raw = {"ClientIP": "not-an-ip"}

        result = normalize_m365(raw)

        assert result["src_ip"] == "not-an-ip"


class TestM365Severity:

    def test_failure_status_severity(self):
        raw = {"Operation": "SomeOperation", "ResultStatus": "Failure"}

        result = normalize_m365(raw)

        assert result["severity"] == 2

    def test_success_derives_severity_2(self):
        raw = {"Operation": "SomeOperation", "ResultStatus": "Success"}

        result = normalize_m365(raw)

        assert result["severity"] == 2

    def test_explicit_severity_used(self):
        raw = {"Operation": "SomeOperation", "severity": 8}

        result = normalize_m365(raw)

        assert result["severity"] == 8
