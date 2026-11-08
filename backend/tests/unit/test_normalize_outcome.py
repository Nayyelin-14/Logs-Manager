import pytest
from app.parsers.helpers import determine_outcome
from app.models.enums import Source
class TestDetermineOutcome:


    def test_ad_4624_event_id_returns_success(self):

        assert determine_outcome(
            event_type=None, canonical_event_type=None, status=None,
            action=None, severity=None, event_id=4624, source="AD"
        ) == "success"
    def test_ad_4625_event_id_returns_failure(self):
        assert determine_outcome(
            event_type=None, canonical_event_type=None, status=None,
            action=None, severity=None, event_id=4625, source="AD"
        ) == "failure"
    def test_ad_4634_event_id_returns_unknown(self):
        assert determine_outcome(
            event_type=None, canonical_event_type=None, status=None,
            action=None, severity=None, event_id=4634, source="AD"
        ) == "unknown"
    def test_m365_status_success_returns_success(self):

        assert determine_outcome(
            event_type="UserLoggedIn", canonical_event_type=None, status="Success",
            action=None, severity=None, event_id=None, source="M365"
        ) == "success"
    def test_m365_status_failure_returns_failure(self):
        assert determine_outcome(
            event_type=None, canonical_event_type=None, status="Failure",
            action=None, severity=None, event_id=None, source="M365"
        ) == "failure"
    def test_m365_status_failed_returns_failure(self):
        assert determine_outcome(
            event_type=None, canonical_event_type=None, status="Failed",
            action=None, severity=None, event_id=None, source="M365"
        ) == "failure"
    def test_canonical_ad_logon_success_returns_success(self):

        assert determine_outcome(
            event_type=None, canonical_event_type="ad_logon_success", status=None,
            action=None, severity=None, event_id=None, source="AD"
        ) == "success"
    def test_canonical_login_failed_returns_failure(self):
        assert determine_outcome(
            event_type=None, canonical_event_type="login_failed", status=None,
            action=None, severity=None, event_id=None, source="API"
        ) == "failure"
    def test_canonical_user_logged_in_returns_success(self):
        assert determine_outcome(
            event_type=None, canonical_event_type="UserLoggedIn", status=None,
            action=None, severity=None, event_id=None, source="M365"
        ) == "success"
    def test_status_error_returns_failure(self):

        assert determine_outcome(
            event_type=None, canonical_event_type=None, status="error",
            action=None, severity=None, event_id=None, source=None
        ) == "failure"
    def test_status_denied_returns_failure(self):
        assert determine_outcome(
            event_type=None, canonical_event_type=None, status="denied",
            action=None, severity=None, event_id=None, source=None
        ) == "failure"
    def test_status_denied_returns_unknown_for_firewall(self):
        assert determine_outcome(
            event_type=None, canonical_event_type=None, status="denied",
            action=None, severity=None, event_id=None, source="FIREWALL"
        ) == "unknown"
    def test_status_succeeded_returns_success(self):
        assert determine_outcome(
            event_type=None, canonical_event_type=None, status="succeeded",
            action=None, severity=None, event_id=None, source=None
        ) == "success"
    def test_event_type_with_failed_returns_failure(self):

        assert determine_outcome(
            event_type="app_login_failed", canonical_event_type=None, status=None,
            action=None, severity=None, event_id=None, source="API"
        ) == "failure"
    def test_event_type_with_failure_returns_failure(self):
        assert determine_outcome(
            event_type="login_failure", canonical_event_type=None, status=None,
            action=None, severity=None, event_id=None, source="API"
        ) == "failure"
    def test_event_type_with_success_returns_success(self):
        assert determine_outcome(
            event_type="user_login_success", canonical_event_type=None, status=None,
            action=None, severity=None, event_id=None, source=None
        ) == "success"
    def test_action_failure_returns_failure(self):

        assert determine_outcome(
            event_type=None, canonical_event_type=None, status=None,
            action="FAILURE", severity=None, event_id=None, source=None
        ) == "failure"
    def test_action_deny_returns_unknown(self):
        assert determine_outcome(
            event_type=None, canonical_event_type=None, status=None,
            action="DENY", severity=None, event_id=None, source="FIREWALL"
        ) == "unknown"
    def test_action_allowed_returns_unknown(self):
        assert determine_outcome(
            event_type=None, canonical_event_type=None, status=None,
            action="ALLOWED", severity=None, event_id=None, source="FIREWALL"
        ) == "unknown"
    def test_action_allow_returns_unknown(self):
        assert determine_outcome(
            event_type=None, canonical_event_type=None, status=None,
            action="ALLOW", severity=None, event_id=None, source="FIREWALL"
        ) == "unknown"
    def test_all_none_returns_unknown(self):

        assert determine_outcome(
            event_type=None, canonical_event_type=None, status=None,
            action=None, severity=None, event_id=None, source=None
        ) == "unknown"
    def test_firewall_deny_returns_unknown(self):
        assert determine_outcome(
            event_type="deny", canonical_event_type="firewall_deny",
            status=None, action="DENY", severity=None, event_id=None,
            source="FIREWALL"
        ) == "unknown"
    def test_firewall_allow_returns_unknown(self):
        assert determine_outcome(
            event_type="allow", canonical_event_type="firewall_allow",
            status=None, action="ALLOW", severity=None, event_id=None,
            source="FIREWALL"
        ) == "unknown"
    def test_aws_error_code_returns_failure(self):
        assert determine_outcome(
            event_type="CreateUser", canonical_event_type="aws_create_user",
            status="AccessDenied", action="CREATE", severity=None, event_id=None,
            source="AWS"
        ) == "failure"
