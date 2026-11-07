"""
Unit tests for the outcome normalization function.
Tests per source type: AD, M365, AWS, CrowdStrike, API, Firewall.
"""

import pytest
from app.parsers.helpers import determine_outcome
from app.models.enums import Source


class TestDetermineOutcome:
    """Unit tests for determine_outcome function."""
    
    # AD Event ID tests
    def test_ad_4624_event_id_returns_success(self):
        """AD Event ID 4624 (successful logon) -> success."""
        assert determine_outcome(
            event_type=None, canonical_event_type=None, status=None,
            action=None, severity=None, event_id=4624, source="AD"
        ) == "success"
    
    def test_ad_4625_event_id_returns_failure(self):
        """AD Event ID 4625 (failed logon) -> failure."""
        assert determine_outcome(
            event_type=None, canonical_event_type=None, status=None,
            action=None, severity=None, event_id=4625, source="AD"
        ) == "failure"
    
    def test_ad_4634_event_id_returns_unknown(self):
        """AD Event ID 4634 (logoff) -> unknown."""
        assert determine_outcome(
            event_type=None, canonical_event_type=None, status=None,
            action=None, severity=None, event_id=4634, source="AD"
        ) == "unknown"
    
    # M365 status tests
    def test_m365_status_success_returns_success(self):
        """M365 with status=Success -> success."""
        assert determine_outcome(
            event_type="UserLoggedIn", canonical_event_type=None, status="Success",
            action=None, severity=None, event_id=None, source="M365"
        ) == "success"
    
    def test_m365_status_failure_returns_failure(self):
        """M365 with status=Failure -> failure."""
        assert determine_outcome(
            event_type=None, canonical_event_type=None, status="Failure",
            action=None, severity=None, event_id=None, source="M365"
        ) == "failure"
    
    def test_m365_status_failed_returns_failure(self):
        """M365 with status=Failed -> failure."""
        assert determine_outcome(
            event_type=None, canonical_event_type=None, status="Failed",
            action=None, severity=None, event_id=None, source="M365"
        ) == "failure"
    
    # Canonical event type tests
    def test_canonical_ad_logon_success_returns_success(self):
        """canonical_event_type ad_logon_success -> success."""
        assert determine_outcome(
            event_type=None, canonical_event_type="ad_logon_success", status=None,
            action=None, severity=None, event_id=None, source="AD"
        ) == "success"
    
    def test_canonical_login_failed_returns_failure(self):
        """canonical_event_type login_failed -> failure."""
        assert determine_outcome(
            event_type=None, canonical_event_type="login_failed", status=None,
            action=None, severity=None, event_id=None, source="API"
        ) == "failure"
    
    def test_canonical_user_logged_in_returns_success(self):
        """canonical_event_type UserLoggedIn (case insensitive) -> success."""
        assert determine_outcome(
            event_type=None, canonical_event_type="UserLoggedIn", status=None,
            action=None, severity=None, event_id=None, source="M365"
        ) == "success"
    
    # Status field tests
    def test_status_error_returns_failure(self):
        """status=error -> failure."""
        assert determine_outcome(
            event_type=None, canonical_event_type=None, status="error",
            action=None, severity=None, event_id=None, source=None
        ) == "failure"
    
    def test_status_denied_returns_failure(self):
        """status=denied -> failure (for non-firewall sources)."""
        assert determine_outcome(
            event_type=None, canonical_event_type=None, status="denied",
            action=None, severity=None, event_id=None, source=None
        ) == "failure"
    
    def test_status_denied_returns_unknown_for_firewall(self):
        """status=denied for firewall source -> unknown."""
        assert determine_outcome(
            event_type=None, canonical_event_type=None, status="denied",
            action=None, severity=None, event_id=None, source="FIREWALL"
        ) == "unknown"
    
    def test_status_succeeded_returns_success(self):
        """status=succeeded -> success."""
        assert determine_outcome(
            event_type=None, canonical_event_type=None, status="succeeded",
            action=None, severity=None, event_id=None, source=None
        ) == "success"
    
    # Event type tests
    def test_event_type_with_failed_returns_failure(self):
        """event_type containing 'failed' -> failure."""
        assert determine_outcome(
            event_type="app_login_failed", canonical_event_type=None, status=None,
            action=None, severity=None, event_id=None, source="API"
        ) == "failure"
    
    def test_event_type_with_failure_returns_failure(self):
        """event_type containing 'failure' -> failure."""
        assert determine_outcome(
            event_type="login_failure", canonical_event_type=None, status=None,
            action=None, severity=None, event_id=None, source="API"
        ) == "failure"
    
    def test_event_type_with_success_returns_success(self):
        """event_type containing 'success' -> success."""
        assert determine_outcome(
            event_type="user_login_success", canonical_event_type=None, status=None,
            action=None, severity=None, event_id=None, source=None
        ) == "success"
    
    # Action tests
    def test_action_failure_returns_failure(self):
        """action=FAILURE -> failure."""
        assert determine_outcome(
            event_type=None, canonical_event_type=None, status=None,
            action="FAILURE", severity=None, event_id=None, source=None
        ) == "failure"
    
    def test_action_deny_returns_unknown(self):
        """action=DENY for FIREWALL returns unknown (outcome is for auth only)."""
        assert determine_outcome(
            event_type=None, canonical_event_type=None, status=None,
            action="DENY", severity=None, event_id=None, source="FIREWALL"
        ) == "unknown"
    
    def test_action_allowed_returns_unknown(self):
        """action=ALLOWED for FIREWALL returns unknown (outcome is for auth only)."""
        assert determine_outcome(
            event_type=None, canonical_event_type=None, status=None,
            action="ALLOWED", severity=None, event_id=None, source="FIREWALL"
        ) == "unknown"
    
    def test_action_allow_returns_unknown(self):
        """action=ALLOW for FIREWALL returns unknown (outcome is for auth only)."""
        assert determine_outcome(
            event_type=None, canonical_event_type=None, status=None,
            action="ALLOW", severity=None, event_id=None, source="FIREWALL"
        ) == "unknown"
    
    # Unknown / default cases
    def test_all_none_returns_unknown(self):
        """All None values -> unknown."""
        assert determine_outcome(
            event_type=None, canonical_event_type=None, status=None,
            action=None, severity=None, event_id=None, source=None
        ) == "unknown"
    
    def test_firewall_deny_returns_unknown(self):
        """Firewall deny action -> unknown (outcome is not for firewall actions)."""
        assert determine_outcome(
            event_type="deny", canonical_event_type="firewall_deny",
            status=None, action="DENY", severity=None, event_id=None,
            source="FIREWALL"
        ) == "unknown"
    
    def test_firewall_allow_returns_unknown(self):
        """Firewall allow action -> unknown (outcome is not for firewall actions)."""
        assert determine_outcome(
            event_type="allow", canonical_event_type="firewall_allow",
            status=None, action="ALLOW", severity=None, event_id=None,
            source="FIREWALL"
        ) == "unknown"
    
    def test_aws_error_code_returns_failure(self):
        """AWS with error code status -> failure."""
        assert determine_outcome(
            event_type="CreateUser", canonical_event_type="aws_create_user",
            status="AccessDenied", action="CREATE", severity=None, event_id=None,
            source="AWS"
        ) == "failure"