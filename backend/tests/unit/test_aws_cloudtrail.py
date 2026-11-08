from datetime import datetime, timezone

import pytest

from app.parsers.cloud import normalize_aws
from app.models.enums import Source, Action


class TestAWSCloudTrailBasic:

    def test_normalize_create_user(self):
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
        raw = {"eventTime": "2026-10-30T22:17:00Z"}

        result = normalize_aws(raw)

        assert result["timestamp"] == "2026-10-30T22:17:00+00:00"

    def test_raw_preserved(self):
        raw = {"eventName": "CreateUser", "extra": "data"}

        result = normalize_aws(raw)

        assert result["raw"] == raw


class TestAWSCloudTrailActionMapping:

    def test_create_maps_to_create(self):
        raw = {"eventName": "CreateUser"}

        result = normalize_aws(raw)

        assert result["action"] == "CREATE"

    def test_delete_maps_to_delete(self):
        raw = {"eventName": "DeleteUser"}

        result = normalize_aws(raw)

        assert result["action"] == "DELETE"

    def test_login_maps_to_login(self):
        raw = {"eventName": "ConsoleLogin"}

        result = normalize_aws(raw)

        assert result["action"] == "LOGIN"


class TestAWSCloudTrailOutcome:

    def test_success_without_error(self):
        raw = {"eventName": "CreateUser"}

        result = normalize_aws(raw)

        assert result["outcome"] == "unknown"

    def test_failure_with_error_code(self):
        raw = {
            "eventName": "CreateUser",
            "errorCode": "AccessDenied",
        }

        result = normalize_aws(raw)

        assert result["outcome"] == "failure"

    def test_error_code_in_description(self):
        raw = {
            "eventName": "CreateUser",
            "errorCode": "AccessDenied",
        }

        result = normalize_aws(raw)

        assert "AccessDenied" in result["description"]


class TestAWSCloudTrailSeverity:

    def test_no_error_default_severity(self):
        raw = {"eventName": "CreateUser"}

        result = normalize_aws(raw)

        assert result["severity"] == 3

    def test_error_higher_severity(self):
        raw = {
            "eventName": "CreateUser",
            "errorCode": "AccessDenied",
        }

        result = normalize_aws(raw)

        assert result["severity"] == 7


class TestAWSCloudTrailEdgeCases:

    def test_empty_event(self):
        raw = {}

        result = normalize_aws(raw)

        assert result is not None
        assert "source" in result
        assert result["source"] == Source.AWS

    def test_region_extraction(self):
        raw = {"region": "eu-west-1"}

        result = normalize_aws(raw)

        assert result["cloud_region"] == "eu-west-1"
