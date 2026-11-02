import { Source } from "../../generated/prisma";

type AnyRecord = Record<string, any>;

export interface SecurityEventInput {
  loginType?: number;
  tenant?: string;
  source: Source | string;
  eventType: string;
  eventSubtype?: string;
  timestamp?: string;
  priority?: number;
  severity?: number;
  vendor?: string;
  product?: string;
  action?: string;
  srcIp?: string;
  srcPort?: number;
  dstIp?: string;
  dstPort?: number;
  protocol?: string;
  user?: string;
  host?: string;
  process?: string;
  eventId?: number;
  url?: string;
  httpMethod?: string;
  statusCode?: number;
  ruleName?: string;
  ruleId?: string;
  cloudAccountId?: string;
  cloudRegion?: string;
  cloudService?: string;
  sha256?: string;
  status?: string;
  login_type?: number;
  interface?: string;
  mac?: string;
  description?: string;
  ip?: string;
  raw?: Record<string, any>;
  tags?: string[];
}

export function asRecord(value: any): AnyRecord | undefined {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as AnyRecord)
    : undefined;
}

export function pick(source: any, paths: string[]): any {
  for (const path of paths) {
    const value = path
      .split(".")
      .reduce<any>(
        (acc, key) =>
          acc !== undefined && acc !== null ? acc[key] : undefined,
        source
      );
    if (value !== undefined && value !== null && value !== "") {
      return value;
    }
  }
  return undefined;
}

export function safeString(value: any): string | undefined {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return undefined;
}

export function safeNumber(value: any): number | undefined {
  if (typeof value === "number" && !Number.isNaN(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value.trim());
    return Number.isNaN(parsed) ? undefined : parsed;
  }
  return undefined;
}

export function safeSeverity(value: any): number | undefined {
  const numeric = safeNumber(value);
  if (numeric !== undefined) {
    return Math.max(0, Math.min(10, numeric));
  }

  const key = safeString(value)?.toLowerCase();
  if (!key) return undefined;

  switch (key) {
    case "info":
    case "informational":
    case "low":
      return 2;
    case "medium":
    case "moderate":
    case "warning":
      return 5;
    case "high":
    case "error":
      return 8;
    case "critical":
    case "fatal":
      return 10;
    default:
      return undefined;
  }
}

export function safeTimestamp(value: any): string {
  if (value) {
    if (typeof value === "number") {
      const millis = value < 1e12 ? value * 1000 : value;
      const date = new Date(millis);
      if (!Number.isNaN(date.getTime())) return date.toISOString();
    }

    const date = new Date(value);
    if (!Number.isNaN(date.getTime())) {
      return date.toISOString();
    }
  }
  return new Date().toISOString();
}

export function safeTags(value: any): string[] {
  return Array.isArray(value) ? value.map((tag) => String(tag)) : [];
}

export function getFirewallEventType(action: any): string {
  const actionStr = safeString(action)?.toUpperCase();
  switch (actionStr) {
    case "DENY":
    case "BLOCK":
    case "DROP":
      return "firewall_deny";
    case "ALLOW":
    case "PERMIT":
    case "ACCEPT":
      return "firewall_allow";
    default:
      return "network_traffic";
  }
}

export function mapAWSVerb(eventName?: string): string | undefined {
  if (!eventName) return undefined;
  if (/^Create/i.test(eventName)) return "CREATEUSER";
  if (/^Delete/i.test(eventName)) return "DELETE";
  if (/Login|SignIn/i.test(eventName)) return "LOGIN";
  if (/Logout|SignOut/i.test(eventName)) return "LOGOUT";
  return "ALERT";
}

export function mapM365Action(operation?: string): string | undefined {
  if (!operation) return undefined;
  if (/LogIn|SignIn|LoggedIn/i.test(operation)) return "LOGIN";
  if (/LogOut|SignOut|LoggedOut/i.test(operation)) return "LOGOUT";
  if (/Delete/i.test(operation)) return "DELETE";
  if (/Create|Add/i.test(operation)) return "CREATE";
  return "ALERT";
}

export function mapADEventType(eventId?: number): string | undefined {
  switch (eventId) {
    case 4624:
      return "ad_logon_success";
    case 4625:
      return "ad_logon_failed";
    case 4634:
      return "ad_logoff";
    case 4720:
      return "ad_user_created";
    case 4726:
      return "ad_user_deleted";
    default:
      return undefined;
  }
}

export function mapADAction(eventId?: number): string | undefined {
  switch (eventId) {
    case 4624:
    case 4625:
      return "LOGIN";
    case 4634:
      return "LOGOUT";
    case 4720:
      return "CREATEUSER";
    case 4726:
      return "DELETE";
    default:
      return undefined;
  }
}
