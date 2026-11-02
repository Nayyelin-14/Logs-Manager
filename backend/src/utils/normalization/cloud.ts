import { Source } from "../../generated/prisma";
import {
  asRecord, pick, safeString, safeNumber, safeSeverity, safeTimestamp, safeTags, getFirewallEventType, mapAWSVerb, mapM365Action, mapADEventType, mapADAction,
  type SecurityEventInput,
} from "./helpers";

export function normalizeAWS(event: any): SecurityEventInput {
  const payload = asRecord(event.raw) ?? event;
  const eventName =
    safeString(
      pick(event, ["eventType", "event_type", "eventName", "event_name"])
    ) ||
    safeString(
      pick(payload, ["eventName", "event_name"])
    );
  const errorCode = safeString(
    pick(event, ["errorCode", "error_code"]) ||
      pick(payload, ["errorCode", "error_code"])
  );
  const cloudService =
    safeString(pick(event, ["cloudService", "cloud.service"])) ||
    safeString(
      pick(payload, ["eventSource", "event_source"])
    );

  return {
    tenant: safeString(pick(event, ["tenant", "Tenant"])),
    source: Source.AWS,
    eventType: eventName || "aws_event",
    user:
      safeString(
        pick(event, ["user", "username", "user_name", "userId"])
      ) ||
      safeString(
        pick(payload, [
          "userIdentity.userName",
          "userIdentity.user_name",
          "user_identity.user_name",
          "user_name",
          "userIdentity.arn",
          "requestParameters.userName",
          "requestParameters.user_name",
        ])
      ),
    srcIp:
      safeString(
        pick(event, ["srcIp", "src_ip", "ip", "sourceIp", "source_ip"])
      ) ||
      safeString(
        pick(payload, ["sourceIPAddress", "source_ip_address"])
      ),
    cloudAccountId:
      safeString(
        pick(event, [
          "cloudAccountId",
          "cloud.account_id",
          "cloud.accountId",
        ])
      ) ||
      safeString(
        pick(payload, [
          "recipientAccountId",
          "recipient_account_id",
          "userIdentity.accountId",
          "userIdentity.account_id",
        ])
      ),
    cloudRegion:
      safeString(
        pick(event, ["cloudRegion", "cloud.region", "region"])
      ) ||
      safeString(
        pick(payload, ["awsRegion", "aws_region", "region"])
      ),
    cloudService,
    action:
      safeString(pick(event, ["action", "Action"]))?.toUpperCase() ||
      mapAWSVerb(eventName),
    severity:
      safeSeverity(pick(event, ["severity"])) ?? (errorCode ? 7 : 3),
    status: safeString(
      pick(event, ["status"]) || pick(payload, ["errorCode"])
    ),
    description: errorCode
      ? `AWS ${eventName || "event"} failed: ${errorCode}`
      : safeString(pick(payload, ["eventName", "eventType"])),
    vendor: "aws",
    product: cloudService,
    raw: event,
    timestamp: safeTimestamp(
      pick(event, ["@timestamp", "timestamp"]) ||
        pick(payload, [
        "eventTime",
        "event_time",
        "awsEventTime",
        "time_created",
      ])
    ),
    tags: safeTags(event.tags),
  };
}

export function normalizeCrowdStrike(event: any): SecurityEventInput {
  const payload =
    asRecord(event.raw) ??
    asRecord(event.event) ??
    asRecord(event.detect) ??
    event;
  const eventType =
    safeString(pick(event, ["eventType", "event_type"])) ||
    safeString(
      pick(payload, [
        "EventType",
        "eventType",
        "DetectName",
        "detect_name",
        "event_simpleName",
        "event_simple_name",
      ])
    ) ||
    "crowdstrike_event";
  const action =
    safeString(pick(event, ["action", "Action"])) ||
    safeString(pick(payload, ["action", "Action"])) ||
    "ALERT";

  return {
    tenant: safeString(pick(event, ["tenant", "Tenant"])),
    source: Source.CROWDSTRIKE,
    eventType,
    user:
      safeString(pick(event, ["user", "username"])) ||
      safeString(
        pick(payload, ["UserName", "user_name", "UserNameString"])
      ),
    srcIp:
      safeString(pick(event, ["srcIp", "src_ip", "ip"])) ||
      safeString(
        pick(payload, [
          "SourceIpAddress",
          "source_ip_address",
          "LocalAddressIP4",
          "RemoteAddressIP4",
        ])
      ),
    host:
      safeString(pick(event, ["host", "hostname"])) ||
      safeString(
        pick(payload, [
          "ComputerName",
          "computer_name",
          "Hostname",
          "host.name",
        ])
      ),
    process:
      safeString(pick(event, ["process", "processName"])) ||
      safeString(
        pick(payload, [
          "FileName",
          "file_name",
          "ImageFileName",
          "CommandLine",
          "command_line",
          "process_name",
        ])
      ),
    action: action.toUpperCase(),
    severity:
      safeSeverity(pick(event, ["severity"])) ??
      safeSeverity(
        pick(payload, ["Severity", "severity", "SeverityName"])
      ) ??
      0,
    sha256:
      safeString(pick(event, ["sha256"])) ||
      safeString(
        pick(payload, ["SHA256String", "SHA256", "sha256"])
      ),
    description:
      safeString(
        pick(payload, [
          "DetectName",
          "detect_name",
          "Description",
          "CommandLine",
          "command_line",
        ])
      ) || eventType,
    vendor: "crowdstrike",
    product: "falcon",
    raw: event,
    timestamp: safeTimestamp(
      pick(event, ["@timestamp", "timestamp"]) ||
        pick(payload, [
          "timestamp",
          "ProcessStartTime",
          "process_start_time",
          "UtcTime",
          "utc_time",
          "CreationTime",
          "creation_time",
        ])
    ),
    tags: safeTags(event.tags),
  };
}
