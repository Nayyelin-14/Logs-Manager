"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.normalizeSyslog = normalizeSyslog;
exports.normalizeAPI = normalizeAPI;
exports.normalizeNetwork = normalizeNetwork;
exports.normalizeUnknown = normalizeUnknown;
const prisma_1 = require("../../generated/prisma");
const helpers_1 = require("./helpers");
function normalizeSyslog(event) {
    const priority = (0, helpers_1.safeNumber)((0, helpers_1.pick)(event, ["priority", "pri", "PRI", "Priority"]));
    const action = (0, helpers_1.pick)(event, ["action", "Action", "act", "disposition"]);
    return {
        tenant: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["tenant", "Tenant"])),
        source: prisma_1.Source.FIREWALL,
        eventType: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["eventType", "event_type", "event", "event_name"])) || (0, helpers_1.getFirewallEventType)(action),
        timestamp: (0, helpers_1.safeTimestamp)((0, helpers_1.pick)(event, ["timestamp", "@timestamp", "time", "ts", "date"])),
        priority,
        severity: (0, helpers_1.safeSeverity)((0, helpers_1.pick)(event, ["severity", "Severity"])) ??
            (priority !== undefined ? priority % 8 : 0),
        host: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["host", "hostname", "host_name", "device"])),
        vendor: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["vendor", "vendor_name"])) ||
            "generic",
        product: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["product", "product_name"])) ||
            "firewall",
        action: (0, helpers_1.safeString)(action)?.toUpperCase(),
        srcIp: (0, helpers_1.safeString)((0, helpers_1.pick)(event, [
            "src",
            "srcIp",
            "src_ip",
            "sourceIp",
            "source_ip",
            "saddr",
        ])),
        srcPort: (0, helpers_1.safeNumber)((0, helpers_1.pick)(event, ["spt", "srcPort", "src_port", "source_port"])),
        dstIp: (0, helpers_1.safeString)((0, helpers_1.pick)(event, [
            "dst",
            "dstIp",
            "dst_ip",
            "destinationIp",
            "destination_ip",
            "daddr",
        ])),
        dstPort: (0, helpers_1.safeNumber)((0, helpers_1.pick)(event, ["dpt", "dstPort", "dst_port", "destination_port"])),
        protocol: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["proto", "protocol", "network.protocol"])),
        user: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["user", "username", "user_name"])),
        description: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["msg", "message", "description", "reason"])),
        ruleName: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["policy", "rule", "ruleName", "rule_name"])),
        ruleId: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["ruleId", "rule_id"])),
        interface: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["if", "interface", "interfaceName", "interface_name"])),
        mac: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["mac", "macAddress", "mac_address"])),
        status: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["status", "disposition"])),
        raw: event,
        tags: (0, helpers_1.safeTags)(event.tags),
    };
}
function normalizeAPI(event) {
    const payload = (0, helpers_1.asRecord)(event.raw) ?? event;
    return {
        tenant: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["tenant", "Tenant"])),
        source: prisma_1.Source.API,
        eventType: (0, helpers_1.safeString)((0, helpers_1.pick)(event, [
            "eventType",
            "event_type",
            "eventName",
            "event_name",
            "type",
        ])) ||
            (0, helpers_1.safeString)((0, helpers_1.pick)(payload, ["eventType", "event_type"])) ||
            "api_event",
        eventSubtype: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["eventSubtype", "event_subtype"])),
        user: (0, helpers_1.safeString)((0, helpers_1.pick)(event, [
            "user",
            "username",
            "user_name",
            "userId",
            "user_id",
        ])),
        srcIp: (0, helpers_1.safeString)((0, helpers_1.pick)(event, [
            "srcIp",
            "src_ip",
            "ip",
            "sourceIp",
            "source_ip",
            "clientIp",
            "client_ip",
        ])),
        srcPort: (0, helpers_1.safeNumber)((0, helpers_1.pick)(event, ["srcPort", "src_port", "spt"])),
        dstIp: (0, helpers_1.safeString)((0, helpers_1.pick)(event, [
            "dstIp",
            "dst_ip",
            "destinationIp",
            "destination_ip",
            "daddr",
        ])),
        dstPort: (0, helpers_1.safeNumber)((0, helpers_1.pick)(event, ["dstPort", "dst_port", "dpt"])),
        protocol: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["protocol", "proto"])),
        host: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["host", "hostname", "host_name"])),
        process: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["process", "processName", "process_name"])),
        ruleId: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["ruleId", "rule_id"])),
        eventId: (0, helpers_1.safeNumber)((0, helpers_1.pick)(event, ["eventId", "event_id"])),
        loginType: (0, helpers_1.safeNumber)((0, helpers_1.pick)(event, ["loginType", "login_type", "logon_type"])),
        cloudAccountId: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["cloudAccountId", "cloud_account_id"])),
        cloudRegion: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["cloudRegion", "cloud_region"])),
        cloudService: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["cloudService", "cloud_service"])),
        sha256: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["sha256"])),
        status: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["status"])),
        interface: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["interface", "if", "interfaceName", "interface_name"])),
        mac: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["mac", "macAddress", "mac_address"])),
        ip: (0, helpers_1.safeString)((0, helpers_1.pick)(event, [
            "ip",
            "srcIp",
            "src_ip",
            "sourceIp",
            "source_ip",
            "clientIp",
            "client_ip",
        ])),
        severity: (0, helpers_1.safeSeverity)((0, helpers_1.pick)(event, ["severity", "Severity"])) ?? 0,
        url: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["url", "request_url"])),
        httpMethod: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["httpMethod", "http_method", "method"])),
        statusCode: (0, helpers_1.safeNumber)((0, helpers_1.pick)(event, ["statusCode", "status_code"])),
        action: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["action", "Action"]))?.toUpperCase(),
        ruleName: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["ruleName", "rule_name"])),
        description: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["reason", "description", "message", "msg"])) || "",
        raw: event,
        timestamp: (0, helpers_1.safeTimestamp)((0, helpers_1.pick)(event, [
            "@timestamp",
            "timestamp",
            "time",
            "eventTime",
            "event_time",
            "created_at",
            "createdAt",
        ])),
        tags: (0, helpers_1.safeTags)(event.tags),
    };
}
function normalizeNetwork(event) {
    const firewall = normalizeSyslog(event);
    const message = (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["message", "msg", "raw"]));
    const regex = /<(\d+)>(\w+ \d+ \d+:\d+:\d+) (\S+)(?: if=(\S+))?(?: event=(\S+))?(?: mac=(\S+))?(?: reason=(\S+))?/;
    const match = message?.match(regex);
    const hasExplicitTimestamp = Boolean((0, helpers_1.pick)(event, ["timestamp", "@timestamp", "time", "ts"]));
    return {
        ...firewall,
        source: prisma_1.Source.NETWORK,
        priority: firewall.priority ??
            (match?.[1] ? parseInt(match[1], 10) : undefined),
        timestamp: hasExplicitTimestamp
            ? firewall.timestamp
            : (0, helpers_1.safeTimestamp)(match?.[2]),
        host: firewall.host || match?.[3] || "unknown",
        eventType: firewall.eventType !== "network_traffic"
            ? firewall.eventType
            : match?.[5] || "link_event",
        description: firewall.description || match?.[7],
        mac: firewall.mac || match?.[6],
        interface: firewall.interface || match?.[4],
        vendor: firewall.vendor && firewall.vendor !== "generic"
            ? firewall.vendor
            : "generic",
        product: firewall.product && firewall.product !== "firewall"
            ? firewall.product
            : "network",
    };
}
function normalizeUnknown(event) {
    return {
        tenant: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["tenant"])),
        source: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["source"])) || prisma_1.Source.API,
        eventType: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["eventType", "event_type", "event", "type"])) || "unknown",
        raw: event,
        timestamp: (0, helpers_1.safeTimestamp)((0, helpers_1.pick)(event, ["timestamp", "@timestamp", "time"])),
        tags: (0, helpers_1.safeTags)(event.tags),
    };
}
// Helpers
//# sourceMappingURL=structured.js.map