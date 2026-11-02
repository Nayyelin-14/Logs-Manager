"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.normalizeM365 = normalizeM365;
exports.normalizeAD = normalizeAD;
const prisma_1 = require("../../generated/prisma");
const helpers_1 = require("./helpers");
function normalizeM365(event) {
    const payload = (0, helpers_1.asRecord)(event.raw) ?? event;
    const operation = (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["eventType", "event_type", "operation"])) ||
        (0, helpers_1.safeString)((0, helpers_1.pick)(payload, [
            "Operation",
            "operation",
            "RecordType",
            "record_type",
            "Activity",
            "activity",
        ])) ||
        "m365_event";
    const result = (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["status", "result"]) ||
        (0, helpers_1.pick)(payload, [
            "ResultStatus",
            "result_status",
            "Status",
            "status",
            "Result",
            "result",
        ])) || undefined;
    const action = (0, helpers_1.mapM365Action)(operation);
    return {
        tenant: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["tenant", "Tenant"])),
        source: prisma_1.Source.M365,
        eventType: operation,
        user: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["user", "username", "email", "userPrincipalName"])) ||
            (0, helpers_1.safeString)((0, helpers_1.pick)(payload, [
                "UserId",
                "user_id",
                "UserPrincipalName",
                "user_principal_name",
                "Actor.UserId",
                "Actor",
            ])),
        srcIp: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["ip", "srcIp", "src_ip", "clientIp"])) ||
            (0, helpers_1.safeString)((0, helpers_1.pick)(payload, [
                "ClientIP",
                "client_ip",
                "ClientIPAddress",
                "client_ip_address",
                "ClientIp",
            ])),
        action,
        severity: (0, helpers_1.safeSeverity)((0, helpers_1.pick)(event, ["severity"])) ??
            (result && /fail|error|denied/i.test(result) ? 5 : 2),
        status: result,
        product: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["workload", "product"])) ||
            (0, helpers_1.safeString)((0, helpers_1.pick)(payload, ["Workload", "workload", "Service", "service"])),
        vendor: "microsoft",
        description: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["description", "message"]) ||
            (0, helpers_1.pick)(payload, [
                "Operation",
                "operation",
                "Activity",
                "activity",
                "Description",
            ])) || (result ? `M365 ${operation}: ${result}` : operation),
        raw: event,
        timestamp: (0, helpers_1.safeTimestamp)((0, helpers_1.pick)(event, ["@timestamp", "timestamp"]) ||
            (0, helpers_1.pick)(payload, [
                "CreationTime",
                "creation_time",
                "CreationDate",
                "creation_date",
                "TimeCreated",
                "time_created",
            ])),
        tags: (0, helpers_1.safeTags)(event.tags),
    };
}
function normalizeAD(event) {
    const payload = (0, helpers_1.asRecord)(event.raw) ?? event;
    const eventId = (0, helpers_1.safeNumber)((0, helpers_1.pick)(event, ["eventId", "event_id"]) ||
        (0, helpers_1.pick)(payload, [
            "EventID",
            "eventId",
            "event_id",
            "eventCode",
            "event_code",
        ]));
    const user = (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["user", "username"])) ||
        (0, helpers_1.safeString)((0, helpers_1.pick)(payload, [
            "TargetUserName",
            "target_user_name",
            "SubjectUserName",
            "subject_user_name",
            "UserName",
            "user_name",
            "user",
        ]));
    const result = (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["status"]) ||
        (0, helpers_1.pick)(payload, ["Status", "status", "Result", "result", "Outcome"]));
    return {
        tenant: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["tenant", "Tenant"])),
        source: prisma_1.Source.AD,
        eventType: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["eventType", "event_type"])) ||
            (0, helpers_1.mapADEventType)(eventId) ||
            "ad_event",
        user,
        host: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["host", "hostname"])) ||
            (0, helpers_1.safeString)((0, helpers_1.pick)(payload, [
                "Computer",
                "ComputerName",
                "computer_name",
                "Workstation",
            ])),
        srcIp: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["ip", "srcIp", "src_ip", "sourceIp"])) ||
            (0, helpers_1.safeString)((0, helpers_1.pick)(payload, [
                "IpAddress",
                "ip_address",
                "SourceIp",
                "source_ip",
                "ClientIp",
                "client_ip",
            ])),
        action: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["action", "Action"]))?.toUpperCase() ||
            (0, helpers_1.mapADAction)(eventId),
        severity: (0, helpers_1.safeSeverity)((0, helpers_1.pick)(event, ["severity"])) ??
            (eventId === 4625 ? 7 : 3),
        eventId,
        loginType: (0, helpers_1.safeNumber)((0, helpers_1.pick)(event, ["loginType", "login_type"]) ||
            (0, helpers_1.pick)(payload, [
                "LogonType",
                "logon_type",
                "loginType",
                "login_type",
            ])),
        status: result,
        description: (0, helpers_1.safeString)((0, helpers_1.pick)(event, ["description", "message"]) ||
            (0, helpers_1.pick)(payload, ["Message", "Description", "FailureReason"])) ||
            (eventId
                ? `Active Directory event ${eventId}${user ? ` for ${user}` : ""}`
                : undefined),
        vendor: "microsoft",
        product: "active_directory",
        raw: event,
        timestamp: (0, helpers_1.safeTimestamp)((0, helpers_1.pick)(event, ["@timestamp", "timestamp"]) ||
            (0, helpers_1.pick)(payload, [
                "TimeCreated",
                "time_created",
                "TimeGenerated",
                "time_generated",
                "timestamp",
            ])),
        tags: (0, helpers_1.safeTags)(event.tags),
    };
}
//# sourceMappingURL=identity.js.map