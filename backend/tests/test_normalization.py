"""Normalization contract for every supported source.

The API stores one canonical shape no matter which vendor sent the event. These
checks pin the source-specific extractors (firewall, AWS CloudTrail, CrowdStrike,
Microsoft 365, Active Directory, network router) and the shared helpers they rely
on: canonical event names, outcome inference, and syslog parsing.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.integrations.syslog import (
    parse_key_values,
    parse_rfc3164_timestamp,
    parse_syslog_message,
)
from app.models.enums import Source
from app.parsers.canonical import (
    get_canonical_events_for_source,
    get_canonical_event_description,
    is_known_event_type,
    resolve_canonical_event_type,
)
from app.parsers.cloud import normalize_aws, normalize_crowdstrike
from app.parsers.firewall import normalize_firewall
from app.parsers.firewall_helpers import (
    parse_key_value_message,
    parse_syslog_pri,
    parse_syslog_timestamp,
    validate_ip,
    validate_port,
)
from app.parsers.helpers import (
    as_record,
    determine_outcome,
    get_firewall_event_type,
    map_ad_action,
    map_ad_event_type,
    map_aws_verb,
    map_m365_action,
    pick,
    safe_number,
    safe_severity,
    safe_string,
    safe_tags,
    safe_timestamp,
)
from app.parsers.identity import normalize_ad, normalize_m365
from app.parsers.structured import normalize_network
from app.schemas.normalized_event import NormalizedEvent, Source as SchemaSource


def test_firewall_normalizer_and_shared_parser_helpers():
    event = normalize_firewall(
        {
            "priority": 134,
            "timestamp": datetime(2025, 8, 20, 12, 44, 56, tzinfo=timezone.utc),
            "vendor": "demo",
            "product": "ngfw",
            "action": "deny",
            "src": "10.0.1.10",
            "dst": "8.8.8.8",
            "spt": 5353,
            "dpt": 53,
            "proto": "udp",
            "msg": "DNS blocked policy=Block-DNS",
        },
        tenant="demoa",
    )

    assert isinstance(event, NormalizedEvent)
    assert event.source == SchemaSource.firewall
    assert event.event_type == "firewall_deny"
    assert event.action.value == "deny"
    assert event.severity == 2
    assert (event.src_ip, event.dst_ip) == ("10.0.1.10", "8.8.8.8")
    assert (event.src_port, event.dst_port) == (5353, 53)
    assert event.protocol == "udp"
    assert event.rule_name == "Block-DNS"
    assert event.tenant == "demoa"

    # Firewall-specific parsers and the shared extraction helpers.
    assert parse_syslog_pri(134) == (16, 6)
    reference = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert parse_syslog_timestamp("Dec 31 23:59:59", reference).year == 2025
    for invalid in ("", "Bad 11 22:14:15", "Oct xx 22:14:15", "Oct 11 99:14:15"):
        assert parse_syslog_timestamp(invalid, reference) is None
    assert parse_key_value_message("src=10.0.0.1 msg=\"two words\"") == {
        "src": "10.0.0.1",
        "msg": '"two words"',
    }
    assert parse_key_value_message("") == {}
    assert validate_ip("10.0.0.1") == "10.0.0.1"
    assert validate_ip("not-an-ip") is None
    assert validate_ip(None) is None
    assert validate_port("443") == 443
    assert validate_port("70000") is None
    assert validate_port("bad") is None
    assert validate_port(None) is None

    assert as_record({"a": 1}) == {"a": 1}
    assert as_record([1]) is None
    assert pick({"a": {"b": 3}}, ["a.b", "a.c"]) == 3
    assert pick({"a": 1}, ["missing"]) is None
    assert safe_string(5) == "5"
    assert safe_string(None) is None
    assert safe_number(" 42 ") == 42
    assert safe_number(True) is None
    assert safe_severity("high") == 8
    assert safe_severity(99) == 10
    assert safe_severity("nonsense") is None
    assert safe_timestamp(0).startswith("1970-01-01")
    assert safe_timestamp("not-a-date")
    assert safe_tags(["a", 1]) == ["a", "1"]
    assert safe_tags("a") == []
    assert get_firewall_event_type("deny") == "firewall_deny"
    assert get_firewall_event_type(None) == "network_traffic"
    assert map_aws_verb("CreateUser") == "CREATE"
    assert map_aws_verb("DeleteUser") == "DELETE"
    assert map_aws_verb(None) is None
    assert map_m365_action("UserLoggedIn") == "LOGIN"
    assert map_m365_action("UserDeleted") == "DELETE"
    assert map_ad_event_type(4624) == "ad_logon_success"
    assert map_ad_event_type(9999) is None
    assert map_ad_action(4625) == "LOGIN"
    assert map_ad_action(None) is None

    # Remaining firewall branches: PRI coercion, embedded timestamps, fallback
    # timestamps, key/value extraction, and severity normalization.
    assert normalize_firewall({"priority": "134", "action": "other"}).severity == 2
    invalid_pri = normalize_firewall({"priority": 999, "action": "other"})
    assert invalid_pri.tenant == "default"
    assert invalid_pri.event_type == "network_traffic"

    embedded = normalize_firewall(
        {"priority": 134, "msg": "Oct 11 22:14:15 host app: traffic"}
    )
    assert embedded.ts is not None
    assert normalize_firewall({"action": "allow"}).ts is not None
    assert normalize_firewall({"action": "allow", "timestamp": "not-a-date"}).ts is not None

    key_values = normalize_firewall(
        {
            "priority": 134,
            "msg": (
                "src=10.0.0.9 dst=10.0.0.10 spt=1000 dpt=80 proto=TCP "
                "action=deny policy=web-block vendor=acme product=ngfw"
            ),
        }
    )
    assert (key_values.src_ip, key_values.dst_ip) == ("10.0.0.9", "10.0.0.10")
    assert (key_values.src_port, key_values.dst_port) == (1000, 80)
    assert key_values.protocol == "tcp"
    assert key_values.rule_name == "web-block"

    assert normalize_firewall(
        {"priority": 134, "action": "deny", "severity": "8"}
    ).severity == 8
    assert normalize_firewall(
        {"priority": 134, "action": "deny", "severity": "bad"}
    ).severity == 2
    assert normalize_firewall(
        {"priority": 134, "action": "deny", "severity": None}
    ).severity == 2


def test_cloud_and_identity_normalizers_share_field_names():
    aws = normalize_aws(
        {
            "eventName": "CreateUser",
            "eventTime": "2026-10-30T22:17:00Z",
            "sourceIPAddress": "203.0.113.10",
            "userIdentity": {"userName": "alice", "accountId": "123456789012"},
            "awsRegion": "us-east-1",
            "eventSource": "iam.amazonaws.com",
        }
    )
    assert aws["source"] == Source.AWS
    assert aws["canonical_event_type"] == "aws_create_user"
    assert aws["user"] == "alice"
    assert aws["src_ip"] == "203.0.113.10"
    assert aws["timestamp"] == "2026-10-30T22:17:00+00:00"

    crowdstrike = normalize_crowdstrike(
        {
            "event": {
                "DetectName": "MalwareDetected",
                "ComputerName": "WIN-ENG-01",
                "FileName": "invoice.exe",
                "Severity": 8,
                "SourceIpAddress": "10.0.0.42",
                "timestamp": "2026-10-30T22:16:00Z",
            }
        }
    )
    assert crowdstrike["source"] == Source.CROWDSTRIKE
    assert crowdstrike["canonical_event_type"] == "malware_detected"
    assert crowdstrike["host"] == "WIN-ENG-01"
    assert crowdstrike["process"] == "invoice.exe"
    assert crowdstrike["severity"] == 8

    m365 = normalize_m365(
        {
            "Operation": "UserLoggedIn",
            "Workload": "AzureActiveDirectory",
            "UserId": "alice@example.com",
            "ClientIP": "203.0.113.20",
            "ResultStatus": "Success",
            "CreationTime": "2026-10-30T22:18:00Z",
        }
    )
    assert m365["source"] == Source.M365
    assert m365["canonical_event_type"] == "m365_user_login"
    assert m365["user"] == "alice@example.com"
    assert m365["outcome"] == "success"

    ad = normalize_ad(
        {
            "EventID": 4625,
            "TargetUserName": "alice",
            "Computer": "DC01.corp.example.com",
            "IpAddress": "10.0.0.77",
            "LogonType": 3,
            "Status": "0xC000006D",
            "TimeCreated": "2026-10-30T22:19:00Z",
        }
    )
    assert ad["source"] == Source.AD
    assert ad["canonical_event_type"] == "ad_logon_failed"
    assert ad["event_id"] == 4625
    assert ad["outcome"] == "failure"


def test_network_normalizer_uses_network_source_and_ports():
    result = normalize_network(
        {
            "host": "router01",
            "vendor": "Cisco",
            "product": "IOS",
            "src": "192.168.1.10",
            "dst": "1.1.1.1",
            "spt": 51515,
            "dpt": 443,
            "proto": "TCP",
        }
    )

    assert result["source"] == Source.NETWORK
    assert result["host"] == "router01"
    assert (result["src_ip"], result["dst_ip"]) == ("192.168.1.10", "1.1.1.1")
    assert (result["src_port"], result["dst_port"]) == (51515, 443)


def test_tenant_is_never_trusted_from_the_payload():
    event = normalize_firewall(
        {"priority": 134, "tenant": "attacker", "Tenant": "attacker", "src": "10.0.1.10"},
        tenant="demoa",
    )
    assert event.tenant == "demoa"

    event = normalize_firewall({"priority": 134, "tenant": "attacker", "src": "10.0.1.10"})
    assert event.tenant == "default"


@pytest.mark.parametrize(
    ("event_type", "source", "expected"),
    [
        ("CreateUser", Source.AWS, "aws_create_user"),
        ("CreateUser", Source.AD, "aws_create_user"),
        ("MalwareDetected", Source.CROWDSTRIKE, "malware_detected"),
        ("UserLoggedIn", Source.M365, "m365_user_login"),
        ("app_login_failed", Source.API, "app_login_failed"),
        ("totally-new-event", Source.API, "totally_new_event"),
    ],
)
def test_canonical_event_resolution(event_type, source, expected):
    assert resolve_canonical_event_type(event_type, source) == expected


def test_canonical_helpers_describe_known_events():
    assert is_known_event_type("CreateUser", Source.AWS)
    assert not is_known_event_type("nonsense-event", Source.API)
    assert "ad_logon_success" in get_canonical_events_for_source(Source.AD)
    assert get_canonical_event_description("malware_detected")


def test_syslog_parsers_handle_rfc3164_rfc5424_and_key_values():
    rfc3164 = parse_syslog_message(
        "<34>Oct 11 22:14:15 mymachine su[1234]: 'su root' failed for lonvick"
    )
    assert rfc3164["priority"] == 34
    assert rfc3164["host"] == "mymachine"
    assert "failed for lonvick" in rfc3164["msg"]

    rfc5424 = parse_syslog_message(
        "<165>1 2003-10-11T22:14:15.003Z mymachine.example.com su - ID47 - hi"
    )
    assert rfc5424["priority"] == 165
    assert rfc5424["host"] == "mymachine.example.com"

    fields = parse_key_values('user=alice src_ip=10.0.0.1 msg="login failed" reason=bad_password')
    assert fields["user"] == "alice"
    assert fields["msg"] == "login failed"
    assert parse_rfc3164_timestamp("Oct 11 22:14:15").endswith("22:14:15+00:00")
    assert parse_syslog_message("   ") is None


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"event_id": 4624, "source": "AD"}, "success"),
        ({"event_id": 4625, "source": "AD"}, "failure"),
        ({"status": "Failure", "source": "M365"}, "failure"),
        ({"status": "denied", "source": "FIREWALL"}, "unknown"),
        ({"canonical_event_type": "ad_logon_success"}, "success"),
        ({"event_type": "user_login_success"}, "success"),
    ],
)
def test_outcome_inference(kwargs, expected):
    params = {
        "event_type": None,
        "canonical_event_type": None,
        "status": None,
        "action": None,
        "severity": None,
        "event_id": None,
    }
    params.update(kwargs)
    assert determine_outcome(**params) == expected


def test_normalized_event_validators_and_deterministic_id():
    event = NormalizedEvent(
        ts="2026-11-09T10:00:00Z",
        tenant="demoa",
        source="API",
        event_type="probe",
        severity=9,
        src_ip="not-an-ip",
        tags="single-tag",
        raw={"b": 2, "a": 1},
    )

    assert event.source == SchemaSource.api
    assert event.ts.tzinfo == timezone.utc
    assert event.severity == 9
    assert event.src_ip is None
    assert event.tags == ["single-tag"]
    assert event.id == event.model_copy(deep=True).id
    assert event.to_db_dict()["tenant"] == "demoa"
