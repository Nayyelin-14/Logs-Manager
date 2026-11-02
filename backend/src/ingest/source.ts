import { Source } from "../generated/prisma";

export function normalizeSourceInput(value: unknown): Source | undefined {
  const raw = Array.isArray(value)
    ? value.find((item) => typeof item === "string" && item.trim() !== "")
    : value;

  if (typeof raw !== "string" || raw.trim() === "") return undefined;

  const key = raw.trim().toLowerCase().replace(/[\s-]+/g, "_");

  switch (key) {
    case "firewall":
    case "syslog":
    case "fortinet":
    case "paloalto":
    case "fortigate":
      return Source.FIREWALL;
    case "network":
    case "router":
    case "switch":
      return Source.NETWORK;
    case "api":
    case "http":
    case "json":
      return Source.API;
    case "aws":
    case "cloudtrail":
    case "amazon":
    case "aws_cloudtrail":
      return Source.AWS;
    case "crowdstrike":
    case "falcon":
    case "cs":
      return Source.CROWDSTRIKE;
    case "m365":
    case "o365":
    case "office365":
    case "microsoft365":
      return Source.M365;
    case "ad":
    case "active_directory":
    case "windows_ad":
    case "windows":
    case "logon":
      return Source.AD;
    default:
      return Object.values(Source).find(
        (source) => source.toLowerCase() === key
      );
  }
}

export function inferSourceFromEvent(event: any): Source {
  const payload =
    event && typeof event === "object" && !Array.isArray(event)
      ? event.raw && typeof event.raw === "object" && !Array.isArray(event.raw)
        ? event.raw
        : event
      : {};

  if (
    hasAny(payload, [
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
    ])
  ) {
    return Source.AWS;
  }

  if (
    hasAny(payload, [
      "DetectName",
      "detect_name",
      "ComputerName",
      "computer_name",
      "SHA256String",
      "sha256",
      "event_simpleName",
      "ImageFileName",
      "file_name",
    ])
  ) {
    return Source.CROWDSTRIKE;
  }

  if (
    hasAny(payload, [
      "EventID",
      "event_id",
      "TargetUserName",
      "target_user_name",
      "SubjectUserName",
      "subject_user_name",
      "LogonType",
      "logon_type",
    ])
  ) {
    return Source.AD;
  }

  if (
    hasAny(payload, [
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
    ])
  ) {
    return Source.M365;
  }

  return Source.API;
}

function hasAny(record: Record<string, any>, keys: string[]): boolean {
  return keys.some((key) => record[key] !== undefined && record[key] !== null);
}
