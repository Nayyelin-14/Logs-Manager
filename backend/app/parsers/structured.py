from typing import Any, Dict, Optional
from app.models.enums import Source, Action
from app.parsers.helpers import (
    as_record, pick, safe_string, safe_number, safe_severity, safe_timestamp, safe_tags,
    get_firewall_event_type, map_aws_verb, map_m365_action, map_ad_event_type, map_ad_action,
    SecurityEventInput, determine_outcome,
)
from app.parsers.canonical import resolve_canonical_event_type, infer_source_from_event
def normalize_syslog(event: Dict[str, Any]) -> Dict[str, Any]:
    priority = safe_number(pick(event, ["priority", "pri", "PRI", "Priority"]))
    action = pick(event, ["action", "Action", "act", "disposition"])
    original_event_type = safe_string(
        pick(event, ["eventType", "event_type", "event", "event_name"])
    ) or get_firewall_event_type(action)
    canonical_event_type = resolve_canonical_event_type(original_event_type, Source.FIREWALL)
    status = safe_string(pick(event, ["status", "disposition"])) or safe_string(pick(event, ["result"]))
    outcome = determine_outcome(
        event_type=original_event_type,
        canonical_event_type=canonical_event_type,
        status=status,
        action=action,
        severity=None,
        event_id=None,
        source=Source.FIREWALL
    )
    return {
        "tenant": safe_string(pick(event, ["tenant", "Tenant"])),
        "source": Source.FIREWALL,
        "event_type": original_event_type or get_firewall_event_type(action),
        "canonical_event_type": canonical_event_type,
        "original_event_type": original_event_type,
        "timestamp": safe_timestamp(pick(event, ["timestamp", "@timestamp", "time", "ts", "date"])),
        "priority": priority,
        "severity": safe_severity(pick(event, ["severity", "Severity"]))
            if safe_severity(pick(event, ["severity", "Severity"])) is not None
            else (priority % 8 if priority is not None else 0),
        "host": safe_string(pick(event, ["host", "hostname", "host_name", "device"])),
        "vendor": safe_string(pick(event, ["vendor", "vendor_name"])) or "generic",
        "product": safe_string(pick(event, ["product", "product_name"])) or "firewall",
        "action": safe_string(action).upper() if safe_string(action) else None,
        "src_ip": safe_string(pick(event, ["src", "srcIp", "src_ip", "sourceIp", "source_ip", "saddr"])),
        "src_port": safe_number(pick(event, ["spt", "srcPort", "src_port", "source_port"])),
        "dst_ip": safe_string(pick(event, ["dst", "dstIp", "dst_ip", "destinationIp", "destination_ip", "daddr"])),
        "dst_port": safe_number(pick(event, ["dpt", "dstPort", "dst_port", "destination_port"])),
        "protocol": safe_string(pick(event, ["proto", "protocol", "network.protocol"])),
        "user": safe_string(pick(event, ["user", "username", "user_name"])),
        "description": safe_string(pick(event, ["msg", "message", "description", "reason"])),
        "rule_name": safe_string(pick(event, ["policy", "rule", "ruleName", "rule_name"])),
        "rule_id": safe_string(pick(event, ["ruleId", "rule_id"])),
        "interface": safe_string(pick(event, ["if", "interface", "interfaceName", "interface_name"])),
        "mac": safe_string(pick(event, ["mac", "macAddress", "mac_address"])),
        "status": status,
        "outcome": outcome,
        "raw": event,
        "tags": safe_tags(event.get("tags")),
    }
def normalize_api(event: Dict[str, Any]) -> Dict[str, Any]:
    payload = as_record(event.get("raw")) or event
    original_event_type = safe_string(
        pick(event, ["eventType", "event_type", "eventName", "event_name", "type"])
    ) or safe_string(pick(payload, ["eventType", "event_type"])) or "api_event"
    canonical_event_type = resolve_canonical_event_type(original_event_type, Source.API)
    status = safe_string(pick(event, ["status"])) or safe_string(pick(payload, ["status_code", "statusCode"]))
    severity = safe_severity(pick(event, ["severity", "Severity"]))
    if severity is None:
        severity = safe_severity(pick(payload, ["severity", "Severity"]))
    action = safe_string(pick(event, ["action", "Action"])).upper() if safe_string(pick(event, ["action", "Action"])) else None
    outcome = determine_outcome(
        event_type=original_event_type,
        canonical_event_type=canonical_event_type,
        status=status,
        action=action,
        severity=None,
        event_id=None,
        source=Source.API
    )
    return {
        "tenant": safe_string(pick(event, ["tenant", "Tenant"])),
        "source": Source.API,
        "event_type": original_event_type or safe_string(pick(payload, ["eventType", "event_type"])) or "api_event",
        "canonical_event_type": canonical_event_type,
        "original_event_type": original_event_type,
        "event_subtype": safe_string(pick(event, ["eventSubtype", "event_subtype"])),
        "severity": severity if severity is not None else 0,
        "user": safe_string(pick(event, ["user", "username", "user_name", "userId", "user_id"])),
        "src_ip": safe_string(pick(event, ["srcIp", "src_ip", "ip", "sourceIp", "source_ip", "clientIp", "client_ip"])),
        "src_port": safe_number(pick(event, ["srcPort", "src_port", "spt"])),
        "dst_ip": safe_string(pick(event, ["dstIp", "dst_ip", "destinationIp", "destination_ip", "daddr"])),
        "dst_port": safe_number(pick(event, ["dstPort", "dst_port", "dpt"])),
        "protocol": safe_string(pick(event, ["protocol", "proto"])),
        "host": safe_string(pick(event, ["host", "hostname", "host_name"])),
        "process": safe_string(pick(event, ["process", "processName", "process_name"])),
        "rule_id": safe_string(pick(event, ["ruleId", "rule_id"])),
        "event_id": safe_number(pick(event, ["eventId", "event_id"])),
        "url": safe_string(pick(event, ["url", "request_url"])),
        "http_method": safe_string(pick(event, ["httpMethod", "http_method", "method"])),
        "status_code": safe_number(pick(event, ["statusCode", "status_code"])),
        "action": action,
        "rule_name": safe_string(pick(event, ["ruleName", "rule_name"])),
        "description": safe_string(pick(event, ["reason", "description", "message", "msg"])) or "",
        "status": status,
        "outcome": outcome,
        "raw": event,
        "timestamp": safe_timestamp(pick(event, [
            "@timestamp", "timestamp", "time", "eventTime", "event_time", "created_at", "createdAt"
        ])),
        "tags": safe_tags(event.get("tags")),
    }
def normalize_network(event: Dict[str, Any]) -> Dict[str, Any]:

    firewall = normalize_syslog(event)
    message = safe_string(pick(event, ["message", "msg", "raw"]))
    regex = r"<(\d+)>(\w+ \d+ \d+:\d+:\d+) (\S+)(?: if=(\S+))?(?: event=(\S+))?(?: mac=(\S+))?(?: reason=(\S+))?"
    match = message and re.match(regex, message)
    has_explicit_timestamp = bool(pick(event, ["timestamp", "@timestamp", "time", "ts"]))
    original_event_type = (
        firewall["event_type"] if firewall["event_type"] != "network_traffic"
        else (match.group(5) if match else "link_event")
    )
    canonical_event_type = resolve_canonical_event_type(original_event_type, Source.NETWORK)
    result = {
        **firewall,
        "source": Source.NETWORK,
        "priority": firewall["priority"] or (match.group(1) if match else None),
        "timestamp": has_explicit_timestamp and firewall["timestamp"] or (match and safe_timestamp(match.group(2)) or firewall["timestamp"]),
        "host": firewall["host"] or (match and match.group(3) or None),
        "event_type": original_event_type,
        "canonical_event_type": canonical_event_type,
        "original_event_type": original_event_type,
        "description": firewall["description"] or (match and match.group(7) or None),
        "mac": firewall["mac"] or (match and match.group(6) or None),
        "interface": firewall["interface"] or (match and match.group(4) or None),
        "vendor": firewall["vendor"] if firewall["vendor"] != "generic" else "generic",
        "product": firewall["product"] if firewall["product"] != "firewall" else "network",
    }
    return result
def normalize_unknown(event: Dict[str, Any]) -> Dict[str, Any]:
    original_event_type = safe_string(
        pick(event, ["eventType", "event_type", "event", "type"])
    ) or "unknown"
    canonical_event_type = resolve_canonical_event_type(original_event_type)
    return {
        "tenant": safe_string(pick(event, ["tenant"])),
        "source": safe_string(pick(event, ["source"])) or Source.API,
        "event_type": original_event_type,
        "canonical_event_type": canonical_event_type,
        "original_event_type": original_event_type,
        "raw": event,
        "timestamp": safe_timestamp(pick(event, ["timestamp", "@timestamp", "time"])),
        "tags": safe_tags(event.get("tags")),
    }
import re
