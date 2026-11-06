"""
Cloud Provider Normalizers

Normalizers for AWS CloudTrail and CrowdStrike events.
"""

from typing import Any, Dict, Optional
from app.models.enums import Source, Action
from app.parsers.helpers import (
    as_record, pick, safe_string, safe_number, safe_severity, safe_timestamp, safe_tags,
    get_firewall_event_type, map_aws_verb, map_m365_action, map_ad_event_type, map_ad_action,
    SecurityEventInput, determine_outcome,
)
from app.parsers.canonical import resolve_canonical_event_type


def normalize_aws(event: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize AWS CloudTrail events."""
    payload = as_record(event.get("raw")) or event
    original_event_type = (
        safe_string(pick(event, ["eventType", "event_type", "eventName", "event_name"])) or
        safe_string(pick(payload, ["eventName", "event_name"]))
    )
    canonical_event_type = resolve_canonical_event_type(original_event_type, Source.AWS)
    error_code = safe_string(pick(event, ["errorCode", "error_code"])) or pick(payload, ["errorCode", "error_code"])
    cloud_service = safe_string(pick(event, ["cloudService", "cloud.service"])) or safe_string(pick(payload, ["eventSource", "event_source"]))
    
    status = safe_string(pick(event, ["status"])) or safe_string(pick(payload, ["errorCode"]))
    
    outcome = determine_outcome(
        event_type=original_event_type,
        canonical_event_type=canonical_event_type,
        status=status,
        action=None,
        severity=None,
        event_id=None,
        source=Source.AWS
    )

    return {
        "tenant": safe_string(pick(event, ["tenant", "Tenant"])),
        "source": Source.AWS,
        "event_type": original_event_type or "aws_event",
        "canonical_event_type": canonical_event_type,
        "original_event_type": original_event_type,
        "user": safe_string(pick(event, ["user", "username", "user_name", "userId"])) or safe_string(
            pick(payload, [
                "userIdentity.userName", "userIdentity.user_name",
                "user_identity.user_name", "user_name",
                "userIdentity.arn",
                "requestParameters.userName", "requestParameters.user_name"
            ])
        ),
        "src_ip": safe_string(pick(event, ["srcIp", "src_ip", "ip", "sourceIp", "source_ip"])) or safe_string(
            pick(payload, ["sourceIPAddress", "source_ip_address"])
        ),
        "cloud_account_id": safe_string(pick(event, [
            "cloudAccountId", "cloud.account_id", "cloud.accountId"
        ])) or safe_string(pick(payload, [
            "recipientAccountId", "recipient_account_id",
            "userIdentity.accountId", "userIdentity.account_id"
        ])),
        "cloud_region": safe_string(pick(event, ["cloudRegion", "cloud.region", "region"])) or safe_string(
            pick(payload, ["awsRegion", "aws_region", "region"])
        ),
        "cloud_service": cloud_service,
        "action": safe_string(pick(event, ["action", "Action"])).upper() if safe_string(pick(event, ["action", "Action"])) else map_aws_verb(original_event_type),
        "severity": safe_severity(pick(event, ["severity"])) or (7 if error_code else 3),
        "status": status,
        "outcome": outcome,
        "description": error_code and f"AWS {original_event_type or 'event'} failed: {error_code}" or safe_string(pick(payload, ["eventName", "eventType"])),
        "vendor": "aws",
        "product": cloud_service,
        "raw": event,
        "timestamp": safe_timestamp(
            pick(event, ["@timestamp", "timestamp"]) or pick(payload, [
                "eventTime", "event_time", "awsEventTime", "time_created"
            ])
        ),
        "tags": safe_tags(event.get("tags")),
    }


def normalize_crowdstrike(event: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize CrowdStrike Falcon events."""
    payload = (
        as_record(event.get("raw")) or
        as_record(event.get("event")) or
        as_record(event.get("detect")) or
        event
    )
    
    original_event_type = (
        safe_string(pick(event, ["eventType", "event_type"])) or
        safe_string(pick(payload, [
            "EventType", "eventType", "DetectName", "detect_name",
            "event_simpleName", "event_simple_name"
        ])) or "crowdstrike_event"
    )
    
    canonical_event_type = resolve_canonical_event_type(original_event_type, Source.CROWDSTRIKE)
    
    action = (
        safe_string(pick(event, ["action", "Action"])) or
        safe_string(pick(payload, ["action", "Action"])) or "ALERT"
    ).upper()

    return {
        "tenant": safe_string(pick(event, ["tenant", "Tenant"])),
        "source": Source.CROWDSTRIKE,
        "event_type": original_event_type,
        "canonical_event_type": canonical_event_type,
        "original_event_type": original_event_type,
        "user": (
            safe_string(pick(event, ["user", "username"])) or
            safe_string(pick(payload, ["UserName", "user_name", "UserNameString"]))
        ),
        "src_ip": (
            safe_string(pick(event, ["srcIp", "src_ip", "ip"])) or
            safe_string(pick(payload, [
                "SourceIpAddress", "source_ip_address", "LocalAddressIP4", "RemoteAddressIP4"
            ])) or
            safe_string(pick(event, ["SourceIpAddress", "source_ip_address", "LocalAddressIP4", "RemoteAddressIP4"]))
        ),
        "host": (
            safe_string(pick(event, ["host", "hostname"])) or
            safe_string(pick(payload, ["ComputerName", "computer_name", "Hostname", "host.name"]))
        ),
        "process": (
            safe_string(pick(event, ["process", "processName"])) or
            safe_string(pick(payload, [
                "FileName", "file_name", "ImageFileName",
                "CommandLine", "command_line", "process_name"
            ]))
        ),
        "action": action,
        "severity": safe_severity(pick(event, ["severity"])) or safe_severity(
            pick(payload, ["Severity", "severity", "SeverityName"])
        ) or 0,
        "sha256": (
            safe_string(pick(event, ["sha256"])) or
            safe_string(pick(payload, ["SHA256String", "SHA256", "sha256"]))
        ),
        "description": (
            safe_string(pick(payload, [
                "DetectName", "detect_name", "Description", "CommandLine", "command_line"
            ])) or original_event_type
        ),
        "vendor": "crowdstrike",
        "product": "falcon",
        "raw": event,
        "timestamp": safe_timestamp(
            pick(event, ["@timestamp", "timestamp"]) or pick(payload, [
                "timestamp", "ProcessStartTime", "process_start_time",
                "UtcTime", "utc_time", "CreationTime", "creation_time"
            ])
        ),
        "tags": safe_tags(event.get("tags")),
    }