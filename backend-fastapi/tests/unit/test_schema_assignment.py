"""Unit tests for NormalizedEvent Pydantic model validation - standalone version."""

from datetime import datetime, timezone

import pytest

import sys
sys.path.insert(0, '/home/nay/projects/logs/Logs-Manager/backend-fastapi')

from app.schemas.normalized_event import NormalizedEvent, Source, Action, Outcome


class TestNormalizedEventAssignmentSamples:
    """Tests using the assignment sample events (4.1-4.7)."""

    def test_firewall_syslog_sample(self):
        """Test sample 4.1: Firewall/Syslog."""
        event = NormalizedEvent(
            ts=datetime(2025, 8, 20, 12, 44, 56, tzinfo=timezone.utc),
            tenant="demoA",
            source=Source.firewall,
            vendor="demo",
            product="ngfw",
            event_type="firewall_deny",
            severity=2,
            action=Action.deny,
            src_ip="10.0.1.10",
            dst_ip="8.8.8.8",
            src_port=5353,
            dst_port=53,
            protocol="udp",
            rule_name="Block-DNS",
            raw={
                "vendor": "demo",
                "product": "ngfw",
                "action": "deny",
                "src": "10.0.1.10",
                "dst": "8.8.8.8",
                "spt": 5353,
                "dpt": 53,
                "proto": "udp",
                "msg": "DNS blocked policy=Block-DNS"
            },
            tags=[]
        )
        assert event.source == Source.firewall
        assert event.event_type == "firewall_deny"
        assert event.action == Action.deny
        assert event.src_ip == "10.0.1.10"
        assert event.dst_ip == "8.8.8.8"
        assert event.severity == 2

    def test_network_router_syslog_sample(self):
        """Test sample 4.2: Network Router."""
        event = NormalizedEvent(
            ts=datetime(2025, 8, 20, 13, 1, 2, tzinfo=timezone.utc),
            tenant="demoA",
            source=Source.network,
            vendor="router",
            product="cisco",
            event_type="link-down",
            severity=5,
            action=Action.alert,
            raw={
                "if": "ge-0/0/1",
                "event": "link-down",
                "mac": "aa:bb:cc:dd:ee:ff",
                "reason": "carrier-loss"
            },
            tags=["interface", "ge-0/0/1"]
        )
        assert event.source == Source.network
        assert event.event_type == "link-down"
        assert event.action == Action.alert

    def test_api_login_failed_sample(self):
        """Test sample 4.3: HTTP API app_login_failed."""
        event = NormalizedEvent(
            ts=datetime(2025, 8, 20, 7, 20, 0, tzinfo=timezone.utc),
            tenant="demoA",
            source=Source.api,
            event_type="app_login_failed",
            user="alice",
            src_ip="203.0.113.7",
            event_subtype="wrong_password",
            severity=5,
            action=Action.login,
            outcome=Outcome.failure,
            raw={
                "tenant": "demoA",
                "source": "api",
                "event_type": "app_login_failed",
                "user": "alice",
                "ip": "203.0.113.7",
                "reason": "wrong_password",
                "@timestamp": "2025-08-20T07:20:00Z"
            }
        )
        assert event.source == Source.api
        assert event.event_type == "app_login_failed"
        assert event.outcome == Outcome.failure
        assert event.action == Action.login
        assert event.user == "alice"

    def test_crowdstrike_malware_sample(self):
        """Test sample 4.4: CrowdStrike malware_detected."""
        event = NormalizedEvent(
            ts=datetime(2025, 8, 20, 8, 0, 0, tzinfo=timezone.utc),
            tenant="demoA",
            source=Source.crowdstrike,
            host="WIN10-01",
            process="powershell.exe",
            severity=8,
            action_detail="quarantine",
            event_type="malware_detected",
            action=Action.alert,
            raw={
                "tenant": "demoA",
                "source": "crowdstrike",
                "event_type": "malware_detected",
                "host": "WIN10-01",
                "process": "powershell.exe",
                "severity": 8,
                "sha256": "abc...",
                "action": "quarantine",
                "@timestamp": "2025-08-20T08:00:00Z"
            },
            tags=["malware"]
        )
        assert event.source == Source.crowdstrike
        assert event.event_type == "malware_detected"
        assert event.severity == 8
        assert event.action == Action.alert
        assert event.action_detail == "quarantine"

    def test_aws_cloudtrail_sample(self):
        """Test sample 4.5: AWS CloudTrail CreateUser."""
        event = NormalizedEvent(
            ts=datetime(2025, 8, 20, 9, 10, 0, tzinfo=timezone.utc),
            tenant="demoB",
            source=Source.aws,
            event_type="CreateUser",
            user_name="admin",
            cloud_account_id="123456789012",
            cloud_region="ap-southeast-1",
            cloud_service="iam",
            action=Action.create,
            severity=7,
            raw={
                "eventName": "CreateUser",
                "userIdentity": {"userName": "admin"},
                "sourceIPAddress": None,
                "awsRegion": "ap-southeast-1",
                "recipientAccountId": "123456789012",
                "eventSource": "iam.amazonaws.com",
                "requestParameters": {"userName": "temp-user"}
            }
        )
        assert event.source == Source.aws
        assert event.event_type == "CreateUser"
        assert event.action == Action.create
        assert event.cloud_account_id == "123456789012"
        assert event.cloud_region == "ap-southeast-1"

    def test_m365_user_logged_in_sample(self):
        """Test sample 4.6: Microsoft 365 UserLoggedIn."""
        event = NormalizedEvent(
            ts=datetime(2025, 8, 20, 10, 5, 0, tzinfo=timezone.utc),
            tenant="demoB",
            source=Source.m365,
            event_type="UserLoggedIn",
            user_name="bob@demo.local",
            src_ip="198.51.100.23",
            outcome=Outcome.success,
            action=Action.login,
            severity=4,
            url="https://outlook.office365.com",
            http_method="GET",
            raw={
                "Operation": "UserLoggedIn",
                "UserId": "bob@demo.local",
                "ClientIP": "198.51.100.23",
                "ResultStatus": "Success",
                "Workload": "Exchange",
                "@timestamp": "2025-08-20T10:05:00Z"
            },
            tags=["Exchange"]
        )
        assert event.source == Source.m365
        assert event.event_type == "UserLoggedIn"
        assert event.outcome == Outcome.success
        assert event.action == Action.login

    def test_ad_logon_failed_sample(self):
        """Test sample 4.7: Microsoft AD Windows Security 4625."""
        event = NormalizedEvent(
            ts=datetime(2025, 8, 20, 11, 11, 11, tzinfo=timezone.utc),
            tenant="demoA",
            source=Source.ad,
            event_type="LogonFailed",
            event_id=4625,
            user_name="demo\\eve",
            src_ip="203.0.113.77",
            host="DC01",
            logon_type=3,
            outcome=Outcome.failure,
            action=Action.login,
            severity=5,
            raw={
                "event_id": 4625,
                "event_type": "LogonFailed",
                "TargetUserName": "demo\\eve",
                "IpAddress": "203.0.113.77",
                "Computer": "DC01",
                "LogonType": 3,
                "@timestamp": "2025-08-20T11:11:11Z"
            }
        )
        assert event.source == Source.ad
        assert event.event_type == "LogonFailed"
        assert event.event_id == 4625
        assert event.outcome == Outcome.failure
        assert event.action == Action.login
        assert event.logon_type == 3
