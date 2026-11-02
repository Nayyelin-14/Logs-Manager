"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.normalizeSourceInput = normalizeSourceInput;
exports.inferSourceFromEvent = inferSourceFromEvent;
const prisma_1 = require("../generated/prisma");
function normalizeSourceInput(value) {
    const raw = Array.isArray(value)
        ? value.find((item) => typeof item === "string" && item.trim() !== "")
        : value;
    if (typeof raw !== "string" || raw.trim() === "")
        return undefined;
    const key = raw.trim().toLowerCase().replace(/[\s-]+/g, "_");
    switch (key) {
        case "firewall":
        case "syslog":
        case "fortinet":
        case "paloalto":
        case "fortigate":
            return prisma_1.Source.FIREWALL;
        case "network":
        case "router":
        case "switch":
            return prisma_1.Source.NETWORK;
        case "api":
        case "http":
        case "json":
            return prisma_1.Source.API;
        case "aws":
        case "cloudtrail":
        case "amazon":
        case "aws_cloudtrail":
            return prisma_1.Source.AWS;
        case "crowdstrike":
        case "falcon":
        case "cs":
            return prisma_1.Source.CROWDSTRIKE;
        case "m365":
        case "o365":
        case "office365":
        case "microsoft365":
            return prisma_1.Source.M365;
        case "ad":
        case "active_directory":
        case "windows_ad":
        case "windows":
        case "logon":
            return prisma_1.Source.AD;
        default:
            return Object.values(prisma_1.Source).find((source) => source.toLowerCase() === key);
    }
}
function inferSourceFromEvent(event) {
    const payload = event && typeof event === "object" && !Array.isArray(event)
        ? event.raw && typeof event.raw === "object" && !Array.isArray(event.raw)
            ? event.raw
            : event
        : {};
    if (hasAny(payload, [
        "eventSource",
        "event_source",
        "recipientAccountId",
        "recipient_account_id",
        "awsRegion",
        "aws_region",
        "userIdentity",
        "user_identity",
        "eventVersion",
        "event_version",
    ])) {
        return prisma_1.Source.AWS;
    }
    if (hasAny(payload, [
        "DetectName",
        "detect_name",
        "ComputerName",
        "computer_name",
        "SHA256String",
        "sha256",
        "event_simpleName",
        "ImageFileName",
        "file_name",
    ])) {
        return prisma_1.Source.CROWDSTRIKE;
    }
    if (hasAny(payload, [
        "EventID",
        "event_id",
        "TargetUserName",
        "target_user_name",
        "SubjectUserName",
        "subject_user_name",
        "LogonType",
        "logon_type",
    ])) {
        return prisma_1.Source.AD;
    }
    if (hasAny(payload, [
        "Operation",
        "operation",
        "Workload",
        "workload",
        "RecordType",
        "record_type",
        "UserPrincipalName",
        "user_principal_name",
        "ClientIP",
        "client_ip",
    ])) {
        return prisma_1.Source.M365;
    }
    return prisma_1.Source.API;
}
function hasAny(record, keys) {
    return keys.some((key) => record[key] !== undefined && record[key] !== null);
}
//# sourceMappingURL=source.js.map