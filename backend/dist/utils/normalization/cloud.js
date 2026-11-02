"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.normalizeAWS = normalizeAWS;
exports.normalizeCrowdStrike = normalizeCrowdStrike;
const prisma_1 = require("../../generated/prisma");
const helpers_1 = require("./helpers");
function normalizeAWS(event) {
    const payload = (0, helpers_1.asRecord)(event.raw) ?? event;
    const eventName = (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["eventType", "event_type", "eventName", "event_name"])) ||
        (0, helpers_1.safeString)((0, helpers_1.pick)(payload, ["eventName", "event_name"]));
    const errorCode = (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["errorCode", "error_code"]) ||
        (0, helpers_1.pick)(payload, ["errorCode", "error_code"]));
    const cloudService = (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["cloudService", "cloud.service"])) ||
        (0, helpers_1.safeString)((0, helpers_1.pick)(payload, ["eventSource", "event_source"]));
    return {
        tenant: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["tenant", "Tenant"])),
        source: prisma_1.Source.AWS,
        eventType: eventName || "aws_event",
        user: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["user", "username", "user_name", "userId"])) ||
            (0, helpers_1.safeString)((0, helpers_1.pick)(payload, [
                "userIdentity.userName",
                "userIdentity.user_name",
                "user_identity.user_name",
                "user_name",
                "userIdentity.arn",
                "requestParameters.userName",
                "requestParameters.user_name",
            ])),
        srcIp: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["srcIp", "src_ip", "ip", "sourceIp", "source_ip"])) ||
            (0, helpers_1.safeString)((0, helpers_1.pick)(payload, ["sourceIPAddress", "source_ip_address"])),
        cloudAccountId: (0, helpers_1.safeString)((0, helpers_1.pick)(event, [
            "cloudAccountId",
            "cloud.account_id",
            "cloud.accountId",
        ])) ||
            (0, helpers_1.safeString)((0, helpers_1.pick)(payload, [
                "recipientAccountId",
                "recipient_account_id",
                "userIdentity.accountId",
                "userIdentity.account_id",
            ])),
        cloudRegion: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["cloudRegion", "cloud.region", "region"])) ||
            (0, helpers_1.safeString)((0, helpers_1.pick)(payload, ["awsRegion", "aws_region", "region"])),
        cloudService,
        action: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["action", "Action"]))?.toUpperCase() ||
            (0, helpers_1.mapAWSVerb)(eventName),
        severity: (0, helpers_1.safeSeverity)((0, helpers_1.pick)(event, ["severity"])) ?? (errorCode ? 7 : 3),
        status: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["status"]) || (0, helpers_1.pick)(payload, ["errorCode"])),
        description: errorCode
            ? `AWS ${eventName || "event"} failed: ${errorCode}`
            : (0, helpers_1.safeString)((0, helpers_1.pick)(payload, ["eventName", "eventType"])),
        vendor: "aws",
        product: cloudService,
        raw: event,
        timestamp: (0, helpers_1.safeTimestamp)((0, helpers_1.pick)(event, ["@timestamp", "timestamp"]) ||
            (0, helpers_1.pick)(payload, [
                "eventTime",
                "event_time",
                "awsEventTime",
                "time_created",
            ])),
        tags: (0, helpers_1.safeTags)(event.tags),
    };
}
function normalizeCrowdStrike(event) {
    const payload = (0, helpers_1.asRecord)(event.raw) ??
        (0, helpers_1.asRecord)(event.event) ??
        (0, helpers_1.asRecord)(event.detect) ??
        event;
    const eventType = (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["eventType", "event_type"])) ||
        (0, helpers_1.safeString)((0, helpers_1.pick)(payload, [
            "EventType",
            "eventType",
            "DetectName",
            "detect_name",
            "event_simpleName",
            "event_simple_name",
        ])) ||
        "crowdstrike_event";
    const action = (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["action", "Action"])) ||
        (0, helpers_1.safeString)((0, helpers_1.pick)(payload, ["action", "Action"])) ||
        "ALERT";
    return {
        tenant: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["tenant", "Tenant"])),
        source: prisma_1.Source.CROWDSTRIKE,
        eventType,
        user: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["user", "username"])) ||
            (0, helpers_1.safeString)((0, helpers_1.pick)(payload, ["UserName", "user_name", "UserNameString"])),
        srcIp: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["srcIp", "src_ip", "ip"])) ||
            (0, helpers_1.safeString)((0, helpers_1.pick)(payload, [
                "SourceIpAddress",
                "source_ip_address",
                "LocalAddressIP4",
                "RemoteAddressIP4",
            ])),
        host: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["host", "hostname"])) ||
            (0, helpers_1.safeString)((0, helpers_1.pick)(payload, [
                "ComputerName",
                "computer_name",
                "Hostname",
                "host.name",
            ])),
        process: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["process", "processName"])) ||
            (0, helpers_1.safeString)((0, helpers_1.pick)(payload, [
                "FileName",
                "file_name",
                "ImageFileName",
                "CommandLine",
                "command_line",
                "process_name",
            ])),
        action: action.toUpperCase(),
        severity: (0, helpers_1.safeSeverity)((0, helpers_1.pick)(event, ["severity"])) ??
            (0, helpers_1.safeSeverity)((0, helpers_1.pick)(payload, ["Severity", "severity", "SeverityName"])) ??
            0,
        sha256: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["sha256"])) ||
            (0, helpers_1.safeString)((0, helpers_1.pick)(payload, ["SHA256String", "SHA256", "sha256"])),
        description: (0, helpers_1.safeString)((0, helpers_1.pick)(payload, [
            "DetectName",
            "detect_name",
            "Description",
            "CommandLine",
            "command_line",
        ])) || eventType,
        vendor: "crowdstrike",
        product: "falcon",
        raw: event,
        timestamp: (0, helpers_1.safeTimestamp)((0, helpers_1.pick)(event, ["@timestamp", "timestamp"]) ||
            (0, helpers_1.pick)(payload, [
                "timestamp",
                "ProcessStartTime",
                "process_start_time",
                "UtcTime",
                "utc_time",
                "CreationTime",
                "creation_time",
            ])),
        tags: (0, helpers_1.safeTags)(event.tags),
    };
}
//# sourceMappingURL=cloud.js.map