import { Source } from "../../generated/prisma";
import {
  asRecord, pick, safeString, safeNumber, safeSeverity, safeTimestamp, safeTags, getFirewallEventType, mapAWSVerb, mapM365Action, mapADEventType, mapADAction,
  type SecurityEventInput,
} from "./helpers";

export function normalizeM365(event: any): SecurityEventInput {
  const payload = asRecord(event.raw) ?? event;
  const operation =
    safeString(
      pick(event, ["eventType", "event_type", "operation"])
    ) ||
    safeString(
      pick(payload, [
        "Operation",
        "operation",
        "RecordType",
        "record_type",
        "Activity",
        "activity",
      ])
    ) ||
    "m365_event";
  const result =
    safeString(
      pick(event, ["status", "result"]) ||
        pick(payload, [
        "ResultStatus",
        "result_status",
        "Status",
        "status",
        "Result",
        "result",
      ])
    ) || undefined;
  const action = mapM365Action(operation);

  return {
    tenant: safeString(pick(event, ["tenant", "Tenant"])),
    source: Source.M365,
    eventType: operation,
    user:
      safeString(
        pick(event, ["user", "username", "email", "userPrincipalName"])
      ) ||
      safeString(
        pick(payload, [
          "UserId",
          "user_id",
          "UserPrincipalName",
          "user_principal_name",
          "Actor.UserId",
          "Actor",
        ])
      ),
    srcIp:
      safeString(
        pick(event, ["ip", "srcIp", "src_ip", "clientIp"])
      ) ||
      safeString(
        pick(payload, [
          "ClientIP",
          "client_ip",
          "ClientIPAddress",
          "client_ip_address",
          "ClientIp",
        ])
      ),
    action,
    severity:
      safeSeverity(pick(event, ["severity"])) ??
      (result && /fail|error|denied/i.test(result) ? 5 : 2),
    status: result,
    product:
      safeString(pick(event, ["workload", "product"])) ||
      safeString(
        pick(payload, ["Workload", "workload", "Service", "service"])
      ),
    vendor: "microsoft",
    description:
      safeString(
        pick(event, ["description", "message"]) ||
          pick(payload, [
          "Operation",
          "operation",
          "Activity",
          "activity",
          "Description",
        ])
      ) || (result ? `M365 ${operation}: ${result}` : operation),
    raw: event,
    timestamp: safeTimestamp(
      pick(event, ["@timestamp", "timestamp"]) ||
        pick(payload, [
          "CreationTime",
          "creation_time",
          "CreationDate",
          "creation_date",
          "TimeCreated",
          "time_created",
        ])
    ),
    tags: safeTags(event.tags),
  };
}

export function normalizeAD(event: any): SecurityEventInput {
  const payload = asRecord(event.raw) ?? event;
  const eventId = safeNumber(
    pick(event, ["eventId", "event_id"]) ||
      pick(payload, [
        "EventID",
        "eventId",
        "event_id",
        "eventCode",
        "event_code",
      ])
  );
  const user =
    safeString(pick(event, ["user", "username"])) ||
    safeString(
      pick(payload, [
        "TargetUserName",
        "target_user_name",
        "SubjectUserName",
        "subject_user_name",
        "UserName",
        "user_name",
        "user",
      ])
    );
  const result = safeString(
    pick(event, ["status"]) ||
      pick(payload, ["Status", "status", "Result", "result", "Outcome"])
  );

  return {
    tenant: safeString(pick(event, ["tenant", "Tenant"])),
    source: Source.AD,
    eventType:
      safeString(pick(event, ["eventType", "event_type"])) ||
      mapADEventType(eventId) ||
      "ad_event",
    user,
    host:
      safeString(pick(event, ["host", "hostname"])) ||
      safeString(
        pick(payload, [
          "Computer",
          "ComputerName",
          "computer_name",
          "Workstation",
        ])
      ),
    srcIp:
      safeString(
        pick(event, ["ip", "srcIp", "src_ip", "sourceIp"])
      ) ||
      safeString(
        pick(payload, [
          "IpAddress",
          "ip_address",
          "SourceIp",
          "source_ip",
          "ClientIp",
          "client_ip",
        ])
      ),
    action:
      safeString(pick(event, ["action", "Action"]))?.toUpperCase() ||
      mapADAction(eventId),
    severity:
      safeSeverity(pick(event, ["severity"])) ??
      (eventId === 4625 ? 7 : 3),
    eventId,
    loginType: safeNumber(
      pick(event, ["loginType", "login_type"]) ||
        pick(payload, [
          "LogonType",
          "logon_type",
          "loginType",
          "login_type",
        ])
    ),
    status: result,
    description:
      safeString(
        pick(event, ["description", "message"]) ||
          pick(payload, ["Message", "Description", "FailureReason"])
      ) ||
      (eventId
        ? `Active Directory event ${eventId}${
            user ? ` for ${user}` : ""
          }`
        : undefined),
    vendor: "microsoft",
    product: "active_directory",
    raw: event,
    timestamp: safeTimestamp(
      pick(event, ["@timestamp", "timestamp"]) ||
        pick(payload, [
          "TimeCreated",
          "time_created",
          "TimeGenerated",
          "time_generated",
          "timestamp",
        ])
    ),
    tags: safeTags(event.tags),
  };
}
