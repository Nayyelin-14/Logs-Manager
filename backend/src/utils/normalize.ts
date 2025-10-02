import { Source } from "../generated/prisma";
export interface SecurityEventInput {
  loginType?: number;
  tenant: string;
  source: Source | string;
  eventType: string;
  eventSubtype?: string;
  timestamp?: string;
  priority?: number;
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
  login_type?: number; // Note: underscore for normalization
  interface?: string;
  mac?: string;
  description?: string;
  ip?: string;
  severity?: number;
  raw?: Record<string, any>;
  tags?: string[];
}

export class NormalizationService {
  static normalizeEvent(rawEvent: any, source: Source): SecurityEventInput {
    const sourceKey = source.toLowerCase();

    switch (sourceKey) {
      case "firewall":
      case "syslog":
        return this.normalizeSyslog(rawEvent);
      case "api":
        return this.normalizeAPI(rawEvent);
      case "aws":
        return this.normalizeAWS(rawEvent);
      case "crowdstrike":
        return this.normalizeCrowdStrike(rawEvent);
      case "m365":
        return this.normalizeM365(rawEvent);
      case "ad":
        return this.normalizeAD(rawEvent);
      case "network":
        return this.normalizeNetwork(rawEvent);
      default:
        return this.normalizeUnknown(rawEvent);
    }
  }

  private static normalizeSyslog(event: any): SecurityEventInput {
    return {
      tenant: this.safeString(event.tenant) || "demoA",
      source: Source.FIREWALL,
      eventType: this.getFirewallEventType(event.action),
      timestamp: this.safeTimestamp(event.timestamp),
      priority: this.safeNumber(event.priority),
      host: this.safeString(event.hostname),
      vendor: this.safeString(event.vendor),
      product: this.safeString(event.product),
      action: this.safeString(event.action)?.toUpperCase(),
      srcIp: this.safeString(event.srcIp),
      srcPort: this.safeNumber(event.srcPort),
      dstIp: this.safeString(event.dstIp),
      dstPort: this.safeNumber(event.dstPort),
      protocol: this.safeString(event.protocol),
      description: this.safeString(event.description),
      ruleName: this.safeString(event.ruleName),
      raw: event,
    };
  }

  private static normalizeAPI(event: any): SecurityEventInput {
    return {
      tenant: this.safeString(event.tenant) || "default",
      source: Source.API,
      eventType: this.safeString(event.eventType) || "api_event",
      user: this.safeString(event.user),
      srcIp: this.safeString(event.ip),
      ip: this.safeString(event.ip),
      severity: this.safeNumber(event.severity) ?? 0,
      url: this.safeString(event.url),
      httpMethod: this.safeString(event.httpMethod),
      statusCode: this.safeNumber(event.statusCode),
      action: this.safeString(event.action)?.toUpperCase(),
      description: this.safeString(event.reason) || "",
      raw: event,
      timestamp: this.safeTimestamp(event["@timestamp"]),
      tags: Array.isArray(event.tags) ? event.tags : [],
    };
  }

  private static normalizeAWS(event: any): SecurityEventInput {
    return {
      tenant: this.safeString(event.tenant) || "default",
      source: Source.AWS,
      eventType:
        this.safeString(event.eventType) ||
        this.safeString(event.raw?.eventName) ||
        "aws_event",
      user:
        this.safeString(event.user) ||
        this.safeString(event.raw?.requestParameters?.userName),
      cloudAccountId: this.safeString(event.cloud?.account_id),
      cloudRegion: this.safeString(event.cloud?.region),
      cloudService: this.safeString(event.cloud?.service),
      action: this.safeString(event.action)?.toUpperCase(),
      severity: this.safeNumber(event.severity) ?? 0,
      raw: event,
      timestamp: this.safeTimestamp(event["@timestamp"]),
      tags: Array.isArray(event.tags) ? event.tags : [],
    };
  }

  private static normalizeCrowdStrike(event: any): SecurityEventInput {
    return {
      tenant: this.safeString(event.tenant) || "default",
      source: Source.CROWDSTRIKE,
      eventType: this.safeString(event.eventType) || "crowdstrike_event",
      srcIp: this.safeString(event.srcIp),
      host: this.safeString(event.host),
      process: this.safeString(event.process),
      action: this.safeString(event.action)?.toUpperCase(),
      severity: this.safeNumber(event.severity) ?? 0,
      sha256: this.safeString(event.sha256),
      raw: event,
      timestamp: this.safeTimestamp(event["@timestamp"]),
      tags: Array.isArray(event.tags) ? event.tags : [],
    };
  }

  private static normalizeM365(event: any): SecurityEventInput {
    return {
      tenant: this.safeString(event.tenant) || "default",
      source: Source.M365,
      eventType: this.safeString(event.eventType) || "m365_event",
      user: this.safeString(event.user),
      srcIp: this.safeString(event.ip),
      action: this.safeString(event.action)?.toUpperCase() || "LOGIN",
      severity:
        this.safeNumber(event.severity) ?? (event.status === "Failure" ? 5 : 1),
      status: this.safeString(event.status),
      product: this.safeString(event.workload),
      description:
        this.safeString(event.description) ||
        (event.status ? `User login ${event.status}` : undefined),
      raw: event,
      timestamp: this.safeTimestamp(event["@timestamp"]),
      tags: Array.isArray(event.tags) ? event.tags : [],
    };
  }

  private static normalizeAD(event: any): SecurityEventInput {
    return {
      tenant: this.safeString(event.tenant) || "default",
      source: Source.AD,
      eventType: this.safeString(event.eventType) || "ad_event",
      user: this.safeString(event.user),
      host: this.safeString(event.host),
      srcIp: this.safeString(event.ip),
      action: this.safeString(event.action)?.toUpperCase(),
      severity: this.safeNumber(event.severity) ?? 0,
      eventId: this.safeNumber(event.event_id),
      loginType: this.safeNumber(event.login_type), // use camelCase for Prisma
      raw: event,
      timestamp: this.safeTimestamp(event["@timestamp"]),
      tags: Array.isArray(event.tags) ? event.tags : [],
    };
  }

  private static normalizeNetwork(event: any): SecurityEventInput {
    const regex =
      /<(\d+)>(\w+ \d+ \d+:\d+:\d+) (\S+)(?: if=(\S+))?(?: event=(\S+))?(?: mac=(\S+))?(?: reason=(\S+))?/;
    const match = event.message?.match(regex);

    return {
      tenant: this.safeString(event.tenant) || "default",
      source: Source.NETWORK,
      priority: match?.[1] ? parseInt(match[1], 10) : undefined,
      timestamp: match?.[2]
        ? new Date(match[2]).toISOString()
        : new Date().toISOString(),
      host: match?.[3] || "unknown",
      eventType: match?.[5] || "link_event",
      description: match?.[7] || undefined,
      mac: match?.[6] || undefined,
      interface: match?.[4] || undefined,
      raw: event,
    };
  }

  private static normalizeUnknown(event: any): SecurityEventInput {
    return {
      tenant: this.safeString(event.tenant) || "default",
      source: this.safeString(event.source) || "API",
      eventType: this.safeString(event.eventType) || "unknown",
      raw: event,
      timestamp: this.safeTimestamp(event.timestamp),
      tags: Array.isArray(event.tags) ? event.tags : [],
    };
  }

  // Helpers
  private static safeString(value: any): string | undefined {
    return typeof value === "string" ? value : undefined;
  }

  private static safeNumber(value: any): number | undefined {
    if (typeof value === "number") return value;
    if (typeof value === "string") {
      const parsed = parseInt(value, 10);
      return isNaN(parsed) ? undefined : parsed;
    }
    return undefined;
  }

  private static safeTimestamp(value: any): string {
    if (value) {
      const date = new Date(value);
      return isNaN(date.getTime())
        ? new Date().toISOString()
        : date.toISOString();
    }
    return new Date().toISOString();
  }

  private static getFirewallEventType(action: any): string {
    const actionStr = this.safeString(action)?.toUpperCase();
    switch (actionStr) {
      case "DENY":
        return "firewall_deny";
      case "ALLOW":
        return "firewall_allow";
      default:
        return "network_traffic";
    }
  }
}
