"""Normalization contract for every supported source.

The API stores one canonical shape no matter which vendor sent the event. These
checks pin the source-specific extractors (firewall, AWS CloudTrail, CrowdStrike,
Microsoft 365, Active Directory, network router) and the shared helpers they rely
on: canonical event names, outcome inference, and syslog parsing.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.core.database import async_session_maker
from app.integrations.syslog import (
    parse_key_values,
    parse_rfc3164_timestamp,
    parse_syslog_message,
)
from app.models.enums import Source
from app.models.events import Event
from app.parsers.canonical import (
    get_canonical_events_for_source,
    get_canonical_event_description,
    is_known_event_type,
    resolve_canonical_event_type,
)
from app.parsers.cloud import normalize_aws, normalize_crowdstrike
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


def test_shared_parser_helpers_used_by_normalizers():
    # Production normalizers share these extraction helpers even though the
    # legacy normalize_firewall wrapper is gone.
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
    assert safe_timestamp("not-a-date") is None
    assert safe_timestamp("2025-08-20T07:20:00Z").startswith("2025-08-20T07:20:00")
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


def test_syslog_timestamp_without_year_is_parsed():
    """Assignment requirement: RFC3164 timestamps carry no year."""
    parsed = parse_rfc3164_timestamp("Oct 11 22:14:15")
    assert parsed is not None
    assert parsed.endswith("22:14:15+00:00")


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


FIREWALL_LINE = (
    '<134>Aug 20 12:44:56 fw01 vendor=demo product=ngfw action=deny '
    'src=10.0.1.10 dst=8.8.8.8 spt=5353 dpt=53 proto=udp '
    'msg=DNS blocked policy=Block-DNS'
)
ROUTER_LINE = (
    '<190>Aug 20 13:01:02 r1 if=ge-0/0/1 event=link-down '
    'mac=aa:bb:cc:dd:ee:ff reason=carrier-loss'
)

ASSIGNMENT_SAMPLES = {
    "firewall": {
        "line": FIREWALL_LINE,
        "search": {"source": "firewall", "search": "fw01"},
        "event_type": "firewall_deny",
        "match": {"srcIp": "10.0.1.10"},
        "expected": {
            "source": "firewall",
            "src_ip": "10.0.1.10",
            "src_port": 5353,
            "dst_ip": "8.8.8.8",
            "dst_port": 53,
            "protocol": "udp",
            "action": "deny",
            "rule_name": "Block-DNS",
            "host": "fw01",
            "severity": 6,
        },
    },
    "router": {
        "line": ROUTER_LINE,
        "search": {"source": "network", "search": "r1"},
        "event_type": "link-down",
        "match": {"host": "r1"},
        "expected": {"source": "network", "host": "r1"},
    },
    "api": {
        "json": {
            "tenant": "demoA",
            "source": "api",
            "event_type": "app_login_failed",
            "user": "alice",
            "ip": "203.0.113.7",
            "reason": "wrong_password",
            "@timestamp": "2025-08-20T07:20:00Z",
        },
        "search": {"source": "api", "search": "203.0.113.7"},
        "event_type": "app_login_failed",
        "match": {"srcIp": "203.0.113.7"},
        "expected": {
            "source": "api",
            "user_name": "alice",
            "src_ip": "203.0.113.7",
            "event_type": "app_login_failed",
        },
        "timestamp": "2025-08-20T07:20:00",
    },
    "crowdstrike": {
        "json": {
            "tenant": "demoA",
            "source": "crowdstrike",
            "event_type": "malware_detected",
            "host": "WIN10-01",
            "process": "powershell.exe",
            "severity": 8,
            "sha256": "abc...",
            "action": "quarantine",
            "@timestamp": "2025-08-20T08:00:00Z",
            "tags": ["malware"],
        },
        "search": {"source": "crowdstrike", "search": "WIN10-01"},
        "event_type": "malware_detected",
        "match": {"host": "WIN10-01"},
        "expected": {
            "source": "crowdstrike",
            "host": "WIN10-01",
            "process": "powershell.exe",
            "severity": 8,
            # The API key's tenant is normalized to lower case before storage.
            "tenant": "demoa",
        },
    },
    "aws": {
        "json": {
            "source": "aws",
            "eventName": "CreateUser",
            "userIdentity": {"userName": "admin"},
            "sourceIPAddress": None,
            "awsRegion": "ap-southeast-1",
            "recipientAccountId": "123456789012",
            "eventSource": "iam.amazonaws.com",
            "requestParameters": {"userName": "temp-user"},
        },
        "search": {"source": "aws", "search": "admin"},
        "event_type": "CreateUser",
        "match": {"user": "admin"},
        "expected": {
            "source": "aws",
            # The stored column is cloud_service; production keeps the full
            # eventSource value rather than the short "iam" alias.
            "cloud_service": "iam.amazonaws.com",
            "cloud_account_id": "123456789012",
            "cloud_region": "ap-southeast-1",
            "event_type": "CreateUser",
            "user_name": "admin",
        },
    },
    "m365": {
        "json": {
            "source": "m365",
            "Operation": "UserLoggedIn",
            "UserId": "bob@demo.local",
            "ClientIP": "198.51.100.23",
            "ResultStatus": "Success",
            "Workload": "Exchange",
            "@timestamp": "2025-08-20T10:05:00Z",
            "tags": ["Exchange"],
        },
        "search": {"source": "m365", "search": "bob@demo.local"},
        "event_type": "UserLoggedIn",
        "match": {"user": "bob@demo.local"},
        "expected": {
            "source": "m365",
            "user_name": "bob@demo.local",
            "src_ip": "198.51.100.23",
            "outcome": "success",
        },
    },
    "ad": {
        "json": {
            "source": "ad",
            "event_id": 4625,
            "event_type": "LogonFailed",
            "TargetUserName": "demo\\eve",
            "IpAddress": "203.0.113.77",
            "Computer": "DC01",
            "LogonType": 3,
            "@timestamp": "2025-08-20T11:11:11Z",
        },
        "search": {"source": "ad", "search": "DC01"},
        "event_type": "LogonFailed",
        "match": {"user": "demo\\eve"},
        "expected": {
            "source": "ad",
            "event_id": 4625,
            "user_name": "demo\\eve",
            "host": "DC01",
            "src_ip": "203.0.113.77",
            "outcome": "failure",
        },
    },
}


async def _load_event(event_id: str) -> Event:
    async with async_session_maker() as session:
        result = await session.execute(select(Event).where(Event.id == event_id))
        return result.scalars().first()


@pytest.mark.parametrize("sample_id", list(ASSIGNMENT_SAMPLES))
def test_assignment_sample_normalizes_through_real_ingest(client, api_key, sample_id):
    """Assignment requirement: all seven source samples normalize on ingest."""
    from conftest import ADMIN_EMAIL, ADMIN_PASSWORD, login

    sample = ASSIGNMENT_SAMPLES[sample_id]
    if "line" in sample:
        response = client.post(
            "/api/ingest/syslog",
            headers={"X-API-Key": api_key, "Content-Type": "text/plain"},
            content=sample["line"].encode(),
        )
        assert response.status_code == 202, response.text
        assert response.json()["accepted"] == 1, response.text
    else:
        response = client.post(
            "/api/ingest",
            json=sample["json"],
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
        )
        assert response.status_code == 200, response.text

    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    params = {**sample["search"], "tenant": "demoa", "limit": 100}
    search = client.get("/api/events", params=params)
    assert search.status_code == 200, search.text
    matches = [
        row for row in search.json()["logs"]
        if row["eventType"] == sample["event_type"]
        and all(row.get(key) == value for key, value in sample.get("match", {}).items())
    ]
    assert matches, f"{sample_id} was not returned by search: {search.text}"

    stored = asyncio.run(_load_event(matches[0]["id"]))
    assert stored is not None

    # Every row keeps an RFC3339 timestamp and a non-empty raw payload.
    timestamp = matches[0]["timestamp"]
    parsed_timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    assert parsed_timestamp.tzinfo is not None
    assert stored.raw

    for field, expected in sample["expected"].items():
        actual = getattr(stored, field)
        if field == "source":
            actual = str(actual)
        assert actual == expected, f"{sample_id}.{field}: {actual!r} != {expected!r}"

    if sample_id in ("firewall", "router"):
        # The original syslog line is preserved verbatim in raw.message.
        assert stored.raw["message"] == sample["line"]
        assert stored.raw["raw"]["message"] == sample["line"]
    if "timestamp" in sample:
        assert parsed_timestamp.isoformat().startswith(sample["timestamp"])


def test_tenant_is_never_trusted_from_the_payload(client, api_key):
    """Assignment requirement: the tenant comes from the API key, not the body."""
    rejected = client.post(
        "/api/ingest",
        json={"tenant": "attacker", "source": "api", "event_type": "tenant_probe"},
        headers={"X-API-Key": api_key, "Content-Type": "application/json"},
    )
    assert rejected.status_code == 403, rejected.text

    accepted = client.post(
        "/api/ingest",
        json={"tenant": "demoA", "source": "api", "event_type": "tenant_probe"},
        headers={"X-API-Key": api_key, "Content-Type": "application/json"},
    )
    assert accepted.status_code == 200, accepted.text
    stored = asyncio.run(_load_event(accepted.json()["eventId"]))
    assert stored is not None
    assert stored.tenant == "demoa"


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
