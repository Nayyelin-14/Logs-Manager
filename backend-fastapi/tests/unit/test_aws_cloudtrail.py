"""Unit tests for AWS CloudTrail normalizer."""

from datetime import datetime, timezone

import pytest

from app.parsers.cloud import normalize_aws
from app.models.enums import Source, Action


class TestAWSCloudTrailBasic:
    """Basic AWS CloudTrail normalization tests."""

    def test_normalize_create_user(self):
        """Test normalizing a CloudTrail CreateUser event."""
        raw = {
            "source": "aws",
            "userIdentity": {
                "type": "IAMUser",
                "principalId": "AIDAEXAMPLE",
                "arn": "arn:aws:iam::123456789012:user/alice",
                "accountId": "123456789012",
                "userName": "alice",
            },
            "eventTime": "2026-10-30T22:17:00Z",
            "eventSource": "iam.amazonaws.com",
            "eventName": "CreateUser",
            "awsRegion": "us-east-1",
            "sourceIPAddress": "203.0.113.10",
            "userAgent": "aws-cli/2.15.0",
            "requestParameters": {"userName": "bob"},
            "recipientAccountId": "123456789012",
        }

        result = normalize_aws(raw)

        assert result["source"] == Source.AWS
        assert result["event_type"] == "CreateUser"
        assert result["canonical_event_type"] == "aws_create_user"
        assert result["src_ip"] == "203.0.113.10"
        assert result["cloud_account_id"] == "123456789012"
        assert result["cloud_region"] == "us-east-1"
        assert result["cloud_service"] == "iam.amazonaws.com"
        assert result["user"] == "alice"

    def test_timestamp_utc_conversion(self):
        """Test timestamp is parsed and returned as ISO format string."""
        raw = {"eventTime": "2026-10-30T22:17:00Z"}

        result = normalize_aws(raw)

        assert result["timestamp"] == "2026-10-30T22:17:00+00:00"

    def test_raw_preserved(self):
        """Test raw event is preserved unchanged."""
        raw = {"eventName": "CreateUser", "extra": "data"}

        result = normalize_aws(raw)

        assert result["raw"] == raw


class TestAWSCloudTrailActionMapping:
    """Test action mapping for AWS events."""

    def test_create_maps_to_create(self):
        """Create* events map to create action."""
        raw = {"eventName": "CreateUser"}

        result = normalize_aws(raw)

        assert result["action"] == "CREATE"

    def test_delete_maps_to_delete(self):
        """Delete* events map to delete action."""
        raw = {"eventName": "DeleteUser"}

        result = normalize_aws(raw)

        assert result["action"] == "DELETE"

    def test_login_maps_to_login(self):
        """Login events map to login action."""
        raw = {"eventName": "ConsoleLogin"}

        result = normalize_aws(raw)

        assert result["action"] == "LOGIN"


class TestAWSCloudTrailOutcome:
    """Test outcome determination for AWS events."""

    def test_success_without_error(self):
        """Events without error_code should have unknown outcome (AWS doesn't derive success from absence of error)."""
        raw = {"eventName": "CreateUser"}

        result = normalize_aws(raw)

        assert result["outcome"] == "unknown"

    def test_failure_with_error_code(self):
        """Events with error_code should have failure outcome."""
        raw = {
            "eventName": "CreateUser",
            "errorCode": "AccessDenied",
        }

        result = normalize_aws(raw)

        assert result["outcome"] == "failure"

    def test_error_code_in_description(self):
        """Error code should be included in description."""
        raw = {
            "eventName": "CreateUser",
            "errorCode": "AccessDenied",
        }

        result = normalize_aws(raw)

        assert "AccessDenied" in result["description"]


class TestAWSCloudTrailSeverity:
    """Test severity mapping for AWS events."""

    def test_no_error_default_severity(self):
        """Events without error should have default severity 3."""
        raw = {"eventName": "CreateUser"}

        result = normalize_aws(raw)

        assert result["severity"] == 3

    def test_error_higher_severity(self):
        """Events with error should have higher severity 7."""
        raw = {
            "eventName": "CreateUser",
            "errorCode": "AccessDenied",
        }

        result = normalize_aws(raw)

        assert result["severity"] == 7


class TestAWSCloudTrailEdgeCases:
    """Edge cases for AWS CloudTrail normalization."""

    def test_empty_event(self):
        """Empty event should return default values."""
        raw = {}

        result = normalize_aws(raw)

        assert result is not None
        assert "source" in result
        assert result["source"] == Source.AWS

    def test_region_extraction(self):
        """Region should be extracted from multiple possible fields."""
        raw = {"region": "eu-west-1"}

        result = normalize_aws(raw)

        assert result["cloud_region"] == "eu-west-1"