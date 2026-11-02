import { Source } from "../../generated/prisma";
import {
  asRecord, pick, safeString, safeNumber, safeSeverity, safeTimestamp, safeTags, getFirewallEventType, mapAWSVerb, mapM365Action, mapADEventType, mapADAction,
  type SecurityEventInput,
} from "./helpers";

export function normalizeSyslog(event: any): SecurityEventInput {
  const priority = safeNumber(
    pick(event, ["priority", "pri", "PRI", "Priority"])
  );
  const action = pick(event, ["action", "Action", "act", "disposition"]);

  return {
    tenant: safeString(pick(event, ["tenant", "Tenant"])),
    source: Source.FIREWALL,
    eventType:
      safeString(
        pick(event, ["eventType", "event_type", "event", "event_name"])
      ) || getFirewallEventType(action),
    timestamp: safeTimestamp(
      pick(event, ["timestamp", "@timestamp", "time", "ts", "date"])
    ),
    priority,
    severity:
      safeSeverity(pick(event, ["severity", "Severity"])) ??
      (priority !== undefined ? priority % 8 : 0),
    host: safeString(
      pick(event, ["host", "hostname", "host_name", "device"])
    ),
    vendor:
      safeString(pick(event, ["vendor", "vendor_name"])) ||
      "generic",
    product:
      safeString(pick(event, ["product", "product_name"])) ||
      "firewall",
    action: safeString(action)?.toUpperCase(),
    srcIp: safeString(
      pick(event, [
        "src",
        "srcIp",
        "src_ip",
        "sourceIp",
        "source_ip",
        "saddr",
      ])
    ),
    srcPort: safeNumber(
      pick(event, ["spt", "srcPort", "src_port", "source_port"])
    ),
    dstIp: safeString(
      pick(event, [
        "dst",
        "dstIp",
        "dst_ip",
        "destinationIp",
        "destination_ip",
        "daddr",
      ])
    ),
    dstPort: safeNumber(
      pick(event, ["dpt", "dstPort", "dst_port", "destination_port"])
    ),
    protocol: safeString(
      pick(event, ["proto", "protocol", "network.protocol"])
    ),
    user: safeString(pick(event, ["user", "username", "user_name"])),
    description: safeString(
      pick(event, ["msg", "message", "description", "reason"])
    ),
    ruleName: safeString(
      pick(event, ["policy", "rule", "ruleName", "rule_name"])
    ),
    ruleId: safeString(pick(event, ["ruleId", "rule_id"])),
    interface: safeString(
      pick(event, ["if", "interface", "interfaceName", "interface_name"])
    ),
    mac: safeString(
      pick(event, ["mac", "macAddress", "mac_address"])
    ),
    status: safeString(pick(event, ["status", "disposition"])),
    raw: event,
    tags: safeTags(event.tags),
  };
}

export function normalizeAPI(event: any): SecurityEventInput {
  const payload = asRecord(event.raw) ?? event;

  return {
    tenant: safeString(pick(event, ["tenant", "Tenant"])),
    source: Source.API,
    eventType:
      safeString(
        pick(event, [
          "eventType",
          "event_type",
          "eventName",
          "event_name",
          "type",
        ])
      ) ||
      safeString(pick(payload, ["eventType", "event_type"])) ||
      "api_event",
    eventSubtype: safeString(
      pick(event, ["eventSubtype", "event_subtype"])
    ),
    user: safeString(
      pick(event, [
        "user",
        "username",
        "user_name",
        "userId",
        "user_id",
      ])
    ),
    srcIp: safeString(
      pick(event, [
        "srcIp",
        "src_ip",
        "ip",
        "sourceIp",
        "source_ip",
        "clientIp",
        "client_ip",
      ])
    ),
    srcPort: safeNumber(
      pick(event, ["srcPort", "src_port", "spt"])
    ),
    dstIp: safeString(
      pick(event, [
        "dstIp",
        "dst_ip",
        "destinationIp",
        "destination_ip",
        "daddr",
      ])
    ),
    dstPort: safeNumber(
      pick(event, ["dstPort", "dst_port", "dpt"])
    ),
    protocol: safeString(pick(event, ["protocol", "proto"])),
    host: safeString(
      pick(event, ["host", "hostname", "host_name"])
    ),
    process: safeString(
      pick(event, ["process", "processName", "process_name"])
    ),
    ruleId: safeString(pick(event, ["ruleId", "rule_id"])),
    eventId: safeNumber(pick(event, ["eventId", "event_id"])),
    loginType: safeNumber(
      pick(event, ["loginType", "login_type", "logon_type"])
    ),
    cloudAccountId: safeString(
      pick(event, ["cloudAccountId", "cloud_account_id"])
    ),
    cloudRegion: safeString(
      pick(event, ["cloudRegion", "cloud_region"])
    ),
    cloudService: safeString(
      pick(event, ["cloudService", "cloud_service"])
    ),
    sha256: safeString(pick(event, ["sha256"])),
    status: safeString(pick(event, ["status"])),
    interface: safeString(
      pick(event, ["interface", "if", "interfaceName", "interface_name"])
    ),
    mac: safeString(
      pick(event, ["mac", "macAddress", "mac_address"])
    ),
    ip: safeString(
      pick(event, [
        "ip",
        "srcIp",
        "src_ip",
        "sourceIp",
        "source_ip",
        "clientIp",
        "client_ip",
      ])
    ),
    severity:
      safeSeverity(pick(event, ["severity", "Severity"])) ?? 0,
    url: safeString(pick(event, ["url", "request_url"])),
    httpMethod: safeString(
      pick(event, ["httpMethod", "http_method", "method"])
    ),
    statusCode: safeNumber(
      pick(event, ["statusCode", "status_code"])
    ),
    action: safeString(pick(event, ["action", "Action"]))?.toUpperCase(),
    ruleName: safeString(
      pick(event, ["ruleName", "rule_name"])
    ),
    description:
      safeString(
        pick(event, ["reason", "description", "message", "msg"])
      ) || "",
    raw: event,
    timestamp: safeTimestamp(
      pick(event, [
        "@timestamp",
        "timestamp",
        "time",
        "eventTime",
        "event_time",
        "created_at",
        "createdAt",
      ])
    ),
    tags: safeTags(event.tags),
  };
}

export function normalizeNetwork(event: any): SecurityEventInput {
  const firewall = normalizeSyslog(event);
  const message = safeString(
    pick(event, ["message", "msg", "raw"])
  );
  const regex =
    /<(\d+)>(\w+ \d+ \d+:\d+:\d+) (\S+)(?: if=(\S+))?(?: event=(\S+))?(?: mac=(\S+))?(?: reason=(\S+))?/;
  const match = message?.match(regex);
  const hasExplicitTimestamp = Boolean(
    pick(event, ["timestamp", "@timestamp", "time", "ts"])
  );

  return {
    ...firewall,
    source: Source.NETWORK,
    priority:
      firewall.priority ??
      (match?.[1] ? parseInt(match[1], 10) : undefined),
    timestamp: hasExplicitTimestamp
      ? firewall.timestamp
      : safeTimestamp(match?.[2]),
    host: firewall.host || match?.[3] || "unknown",
    eventType:
      firewall.eventType !== "network_traffic"
        ? firewall.eventType
        : match?.[5] || "link_event",
    description: firewall.description || match?.[7],
    mac: firewall.mac || match?.[6],
    interface: firewall.interface || match?.[4],
    vendor:
      firewall.vendor && firewall.vendor !== "generic"
        ? firewall.vendor
        : "generic",
    product:
      firewall.product && firewall.product !== "firewall"
        ? firewall.product
        : "network",
  };
}

export function normalizeUnknown(event: any): SecurityEventInput {
  return {
    tenant: safeString(pick(event, ["tenant"])),
    source: safeString(pick(event, ["source"])) || Source.API,
    eventType:
      safeString(
        pick(event, ["eventType", "event_type", "event", "type"])
      ) || "unknown",
    raw: event,
    timestamp: safeTimestamp(
      pick(event, ["timestamp", "@timestamp", "time"])
    ),
    tags: safeTags(event.tags),
  };
}

// Helpers
