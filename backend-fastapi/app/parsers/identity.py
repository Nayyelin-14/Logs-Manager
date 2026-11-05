"""
Identity Provider Normalizers

Normalizers for Microsoft 365 and Active Directory / Windows Security events.
"""

from typing import Any, Dict, Optional
from app.models.enums import Source, Action
from app.parsers.helpers import (
    as_record, pick, safe_string, safe_number, safe_severity, safe_timestamp, safe_tags,
    get_firewall_event_type, map_aws_verb, map_m365_action, map_ad_event_type, map_ad_action,
    SecurityEventInput, determine_outcome,
)
from app.parsers.canonical import resolve_canonical_event_type


def normalize_m365(event: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize Microsoft 365 audit events."""
    payload = as_record(event.get("raw")) or event
    original_event_type = (
        safe_string(pick(event, ["eventType", "event_type", "operation"])) or
        safe_string(pick(payload, ["Operation", "operation", "RecordType", "record_type", "Activity", "activity"])) or "m365_event"
    )
    canonical_event_type = resolve_canonical_event_type(original_event_type, Source.M365)
    result = (
        safe_string(pick(event, ["status", "result"])) or
        safe_string(pick(payload, ["ResultStatus", "result_status", "Status", "status", "Result", "result"]))
    ) or "undefined"
    action = map_m365_action(original_event_type)
    
    outcome = determine_outcome(
        event_type=original_event_type,
        canonical_event_type=canonical_event_type,
        status=result,
        action=action,
        severity=None,
        event_id=None,
        source=Source.M365
    )

    return {
        "tenant": safe_string(pick(event, ["tenant", "Tenant"])),
        "source": Source.M365,
        "event_type": original_event_type,
        "canonical_event_type": canonical_event_type,
        "original_event_type": original_event_type,
        "user": safe_string(pick(event, ["user", "username", "email", "userPrincipalName"])) or safe_string(
            pick(payload, [
                "UserId", "user_id", "UserPrincipalName", "user_principal_name",
                "Actor.UserId", "Actor"
            ])
        ),
        "src_ip": safe_string(pick(event, ["ip", "srcIp", "src_ip", "clientIp"])) or safe_string(
            pick(payload, ["ClientIP", "client_ip", "ClientIPAddress", "client_ip_address", "ClientIp"])
        ),
        "action": action,
        "severity": safe_severity(pick(event, ["severity"])) or (result and result.lower() in ["fail", "error", "denied"] and 5 or 2),
        "status": result,
        "outcome": outcome,
        "product": safe_string(pick(event, ["workload", "product"])) or safe_string(
            pick(payload, ["Workload", "workload", "Service", "service"])
        ),
        "vendor": "microsoft",
        "description": safe_string(
            pick(event, ["description", "message"]) or pick(payload, [
                "Operation", "operation", "Activity", "activity", "Description"
            ])
        ) or (result and f"M365 {original_event_type}: {result}") or original_event_type,
        "raw": event,
        "timestamp": safe_timestamp(
            pick(event, ["@timestamp", "timestamp"]) or pick(payload, [
                "CreationTime", "creation_time", "CreationDate", "creation_date",
                "TimeCreated", "time_created"
            ])
        ),
        "tags": safe_tags(event.get("tags")),
    }


def normalize_ad(event: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize Active Directory / Windows Security events."""
    payload = as_record(event.get("raw")) or event
    event_id = safe_number(
        pick(event, ["eventId", "event_id"]) or pick(payload, [
            "EventID", "eventId", "event_id", "eventCode", "event_code"
        ])
    )
    original_event_type = (
        safe_string(pick(event, ["eventType", "event_type"])) or
        map_ad_event_type(event_id) or "ad_event"
    )
    canonical_event_type = resolve_canonical_event_type(original_event_type, Source.AD)
    user = (
        safe_string(pick(event, ["user", "username"])) or
        safe_string(pick(payload, [
            "TargetUserName", "target_user_name",
            "SubjectUserName", "subject_user_name",
            "UserName", "user_name", "user"
        ]))
    )
    result = safe_string(pick(event, ["status"]) or pick(payload, ["Status", "status", "Result", "result", "Outcome"]))
    
    outcome = determine_outcome(
        event_type=original_event_type,
        canonical_event_type=canonical_event_type,
        status=result,
        action=None,
        severity=None,
        event_id=event_id,
        source=Source.AD
    )

    return {
        "tenant": safe_string(pick(event, ["tenant", "Tenant"])),
        "source": Source.AD,
        "event_type": original_event_type,
        "canonical_event_type": canonical_event_type,
        "original_event_type": original_event_type,
        "user": user,
        "host": safe_string(pick(event, ["host", "hostname"])) or safe_string(
            pick(payload, ["Computer", "ComputerName", "computer_name", "Workstation"])
        ),
        "src_ip": (
            safe_string(pick(event, ["ip", "srcIp", "src_ip", "sourceIp"])) or
            safe_string(pick(payload, [
                "IpAddress", "ip_address", "SourceIp", "source_ip",
                "ClientIp", "client_ip"
            ]))
        ),
        "action": (
            safe_string(pick(event, ["action", "Action"])).upper() if safe_string(pick(event, ["action", "Action"])) else None
        ) or map_ad_action(event_id),
        "severity": safe_severity(pick(event, ["severity"])) or (event_id == 4625 and 7 or 3),
        "event_id": event_id,
        "login_type": safe_number(
            pick(event, ["loginType", "login_type"]) or pick(payload, [
                "LogonType", "logon_type", "loginType", "login_type"
            ])
        ),
        "status": result,
        "outcome": outcome,
        "description": safe_string(
            pick(event, ["description", "message"]) or pick(payload, ["Message", "Description", "FailureReason"])
        ) or (event_id and f"Active Directory event {event_id}{' for ' + user if user else ''}"),
        "vendor": "microsoft",
        "product": "active_directory",
        "raw": event,
        "timestamp": safe_timestamp(
            pick(event, ["@timestamp", "timestamp"]) or pick(payload, [
                "TimeCreated", "time_created", "TimeGenerated", "time_generated", "timestamp"
            ])
        ),
        "tags": safe_tags(event.get("tags")),
    }