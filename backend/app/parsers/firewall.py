import re
from datetime import datetime, timezone
from typing import Any, Optional

from app.parsers.firewall_helpers import (
    parse_syslog_pri,
    parse_syslog_timestamp,
    parse_key_value_message,
    validate_ip,
    validate_port,
)


SYSLOG_SEVERITY_MAP = {
    0: 10,
    1: 9,
    2: 8,
    3: 7,
    4: 5,
    5: 4,
    6: 2,
    7: 1,
}

ACTION_MAP = {
    "allow": "allow",
    "permit": "allow",
    "pass": "allow",
    "deny": "deny",
    "block": "deny",
    "drop": "deny",
    "reject": "deny",
}

EVENT_TYPE_MAP = {
    "deny": "firewall_deny",
    "block": "firewall_deny",
    "drop": "firewall_deny",
    "reject": "firewall_deny",
    "allow": "firewall_allow",
    "permit": "firewall_allow",
    "pass": "firewall_allow",
    "alert": "firewall_alert",
}


def normalize_firewall(
    raw_event: dict[str, Any],
    tenant: Optional[str] = None,
) -> Any:
    from app.schemas.normalized_event import NormalizedEvent, Source, Action

    priority = raw_event.get("priority", raw_event.get("pri", raw_event.get("PRI", 0)))

    is_valid_pri = (
        isinstance(priority, int) and
        0 <= priority <= 191
    ) or (
        isinstance(priority, str) and
        priority.isdigit() and
        0 <= int(priority) <= 191
    )

    if is_valid_pri:
        pri_int = int(priority)
    else:
        pri_int = None

    if pri_int is not None:
        facility, syslog_severity = parse_syslog_pri(pri_int)
        normalized_severity = SYSLOG_SEVERITY_MAP.get(syslog_severity, 2)
    else:
        normalized_severity = SYSLOG_SEVERITY_MAP.get(6, 2)

    action_str = raw_event.get("action", "").lower() if raw_event.get("action") else ""
    action_enum = None
    event_type = "network_traffic"

    if action_str in ACTION_MAP:
        action_enum = Action(ACTION_MAP[action_str]) if ACTION_MAP[action_str] in [a.value for a in Action] else None
        event_type = EVENT_TYPE_MAP.get(action_str, "firewall_deny")

    timestamp = raw_event.get("timestamp", raw_event.get("@timestamp"))
    parsing_error = False

    if timestamp is None:
        if "msg" in raw_event:
            ts_match = re.search(r'(\w+\s+\d+\s+\d+:\d+:\d+)', str(raw_event.get("msg", "")))
            if ts_match:
                timestamp = parse_syslog_timestamp(ts_match.group(1))
        if timestamp is None:
            parsing_error = True

    if timestamp is None:
        timestamp = datetime.now(timezone.utc)
        parsing_error = True

    if isinstance(timestamp, str):
        parsed = parse_syslog_timestamp(timestamp)
        if parsed:
            timestamp = parsed
        else:
            timestamp = datetime.now(timezone.utc)
            parsing_error = True

    raw_timestamp = timestamp.isoformat() if isinstance(timestamp, datetime) else str(timestamp)

    hostname = raw_event.get("host", raw_event.get("hostname", raw_event.get("host_name")))

    message = raw_event.get("msg", raw_event.get("message", raw_event.get("description")))
    kv_pairs = {}
    if message:
        kv_pairs = parse_key_value_message(str(message))
        if not raw_event.get("src"):
            raw_event["src"] = kv_pairs.get("src")
        if not raw_event.get("dst"):
            raw_event["dst"] = kv_pairs.get("dst")
        if not raw_event.get("spt"):
            raw_event["spt"] = kv_pairs.get("spt")
        if not raw_event.get("dpt"):
            raw_event["dpt"] = kv_pairs.get("dpt")
        if not raw_event.get("proto"):
            raw_event["proto"] = kv_pairs.get("proto")
        if not raw_event.get("action"):
            raw_event["action"] = kv_pairs.get("action")
        if not raw_event.get("policy"):
            raw_event["policy"] = kv_pairs.get("policy")
        if not raw_event.get("vendor"):
            raw_event["vendor"] = kv_pairs.get("vendor")
        if not raw_event.get("product"):
            raw_event["product"] = kv_pairs.get("product")

    rule_name = raw_event.get("policy", raw_event.get("rule", raw_event.get("rule_name")))
    vendor = raw_event.get("vendor") or raw_event.get("vendor_name") or "firewall"
    product = raw_event.get("product") or raw_event.get("product_name") or "generic"

    src_ip = validate_ip(raw_event.get("src", raw_event.get("src_ip", raw_event.get("sourceIp", raw_event.get("source_ip")))))
    dst_ip = validate_ip(raw_event.get("dst", raw_event.get("dst_ip", raw_event.get("destinationIp", raw_event.get("destination_ip")))))

    src_port = validate_port(raw_event.get("spt", raw_event.get("src_port", raw_event.get("srcPort"))))
    dst_port = validate_port(raw_event.get("dpt", raw_event.get("dst_port", raw_event.get("dstPort"))))

    protocol = raw_event.get("proto", raw_event.get("protocol"))
    if protocol:
        protocol = str(protocol).lower()

    event_severity = raw_event.get("severity", raw_event.get("Severity", normalized_severity))
    if event_severity is not None:
        try:
            event_severity = int(event_severity)
            event_severity = max(0, min(10, event_severity))
        except (ValueError, TypeError):
            event_severity = normalized_severity
    else:
        event_severity = normalized_severity

    final_tenant = tenant if tenant is not None else "default"

    raw = dict(raw_event)
    raw["ts"] = raw_timestamp
    if parsing_error:
        raw["_parse_error"] = True

    normalized = NormalizedEvent(
        ts=timestamp,
        tenant=final_tenant,
        source=Source.firewall,
        vendor=vendor,
        product=product,
        event_type=event_type,
        severity=event_severity,
        action=action_enum,
        src_ip=src_ip,
        dst_ip=dst_ip,
        src_port=src_port,
        dst_port=dst_port,
        protocol=protocol,
        host=hostname,
        rule_name=rule_name,
        raw=raw,
        tags=[],
    )

    return normalized
