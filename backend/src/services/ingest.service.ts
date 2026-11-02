import { Action, Prisma, SecurityEvent, Source } from "../generated/prisma";
import { prisma } from "../config/PrismaClient";
import { NormalizationService } from "../utils/normalize";
import { AlertService } from "../utils/alertService";
import { handleError } from "../utils/errorHandeling";
import { errorCode } from "../config/errrorcode";
import cacheQueue from "../jobs/queues/cacheQueue";
import {
  inferSourceFromEvent,
  normalizeSourceInput as resolveSourceAlias,
} from "../ingest/source";

export interface IngestContext {
  tenant?: string;
  username?: string;
  email?: string;
}

export interface IngestResult {
  event: SecurityEvent;
  alerts: any[];
}

export interface BatchIngestResult {
  total: number;
  ingested: number;
  failed: number;
  results: Array<{
    index: number;
    success: boolean;
    eventId?: string;
    error?: string;
  }>;
}

export class IngestService {
  private readonly alertService = new AlertService();

  normalizeSourceInput(value: unknown): Source | undefined {
    return resolveSourceAlias(value);
  }

  normalizeAction(value: unknown): Action | null {
    if (value === null || value === undefined) return null;

    const key = String(value)
      .trim()
      .toUpperCase()
      .replace(/[^A-Z]/g, "");

    switch (key) {
      case "ALLOW":
      case "PERMIT":
      case "ACCEPT":
      case "PASS":
        return Action.ALLOW;
      case "DENY":
      case "BLOCK":
      case "DROP":
      case "REJECT":
        return Action.DENY;
      case "CREATE":
      case "ADD":
        return Action.CREATE;
      case "DELETE":
      case "REMOVE":
        return Action.DELETE;
      case "LOGIN":
      case "SIGNIN":
      case "LOGON":
        return Action.LOGIN;
      case "LOGOUT":
      case "SIGNOUT":
      case "LOGOFF":
        return Action.LOGOUT;
      case "ALERT":
      case "DETECT":
      case "MALWARE":
        return Action.ALERT;
      case "QUARANTINE":
      case "ISOLATE":
        return Action.QUARANTINE;
      case "CREATEUSER":
      case "USERCREATED":
        return Action.CREATEUSER;
      default:
        return null;
    }
  }

  async ingest(
    rawEvent: any,
    sourceInput?: unknown,
    context: IngestContext = {}
  ): Promise<IngestResult> {
    if (!rawEvent || typeof rawEvent !== "object" || Array.isArray(rawEvent)) {
      throw handleError(
        "Each event must be a JSON object.",
        400,
        errorCode.invalid
      );
    }

    const source =
      this.normalizeSourceInput(rawEvent.source) ??
      this.normalizeSourceInput(sourceInput) ??
      inferSourceFromEvent(rawEvent);

    const normalizedEvent = NormalizationService.normalizeEvent(
      rawEvent,
      source
    );
    const tenant = this.resolveTenant(rawEvent, context);
    const action = this.normalizeAction(
      normalizedEvent.action ?? rawEvent.action
    );

    const data: Prisma.SecurityEventUncheckedCreateInput = {
      timestamp: normalizedEvent.timestamp
        ? new Date(normalizedEvent.timestamp)
        : new Date(),
      tenant,
      source,
      priority: normalizedEvent.priority ?? null,
      vendor: normalizedEvent.vendor || null,
      product: normalizedEvent.product || null,
      eventType: normalizedEvent.eventType || "unknown",
      eventSubtype: normalizedEvent.eventSubtype || null,
      severity: normalizedEvent.severity ?? 0,
      action,
      srcIp: normalizedEvent.srcIp || null,
      srcPort: this.stringOrNull(normalizedEvent.srcPort),
      dstIp: normalizedEvent.dstIp || null,
      dstPort: this.stringOrNull(normalizedEvent.dstPort),
      protocol: normalizedEvent.protocol || null,
      user: normalizedEvent.user || context.username || context.email || null,
      host: normalizedEvent.host || null,
      process: normalizedEvent.process || null,
      eventId: normalizedEvent.eventId ?? null,
      url: normalizedEvent.url || null,
      httpMethod: normalizedEvent.httpMethod || null,
      statusCode: normalizedEvent.statusCode ?? null,
      ruleName: normalizedEvent.ruleName || null,
      ruleId: normalizedEvent.ruleId || null,
      cloudAccountId: normalizedEvent.cloudAccountId || null,
      cloudRegion: normalizedEvent.cloudRegion || null,
      cloudService: normalizedEvent.cloudService || null,
      sha256: normalizedEvent.sha256 || null,
      status: normalizedEvent.status || null,
      loginType:
        normalizedEvent.loginType ??
        normalizedEvent.login_type ??
        null,
      interface: normalizedEvent.interface || null,
      mac: normalizedEvent.mac || null,
      description: normalizedEvent.description || null,
      ip: normalizedEvent.ip || normalizedEvent.srcIp || null,
      raw: (normalizedEvent.raw ?? rawEvent) as Prisma.InputJsonValue,
      tags: normalizedEvent.tags || [],
    };

    const event = await prisma.securityEvent.create({ data });

    let alerts: any[] = [];
    try {
      alerts = (await this.alertService.checkAlerts(event)) || [];
    } catch (error) {
      console.error("Error evaluating alert rules:", error);
    }

    this.invalidateLogCache();

    return { event, alerts };
  }

  async ingestBatch(
    events: any[],
    sourceInput: unknown,
    context: IngestContext = {}
  ): Promise<BatchIngestResult> {
    const results: BatchIngestResult["results"] = [];
    let ingested = 0;

    for (let index = 0; index < events.length; index += 1) {
      try {
        const result = await this.ingest(events[index], sourceInput, context);
        ingested += 1;
        results.push({ index, success: true, eventId: result.event.id });
      } catch (error) {
        results.push({
          index,
          success: false,
          error: error instanceof Error ? error.message : "Unknown error",
        });
      }
    }

    return {
      total: events.length,
      ingested,
      failed: events.length - ingested,
      results,
    };
  }

  private resolveTenant(rawEvent: any, context: IngestContext): string {
    const requested =
      typeof rawEvent.tenant === "string" && rawEvent.tenant.trim() !== ""
        ? rawEvent.tenant.trim()
        : undefined;

    const bound = context.tenant?.trim() || undefined;

    if (bound) {
      if (requested && requested !== bound) {
        throw handleError(
          "Tenant does not match the authenticated identity.",
          403,
          errorCode.unauthorized
        );
      }
      return bound;
    }

    return (
      requested ||
      process.env.INGEST_DEFAULT_TENANT ||
      process.env.SYSLOG_TENANT ||
      "demoA"
    );
  }

  private invalidateLogCache() {
    try {
      void cacheQueue
        .add(
          "invalidate-log-cache",
          { pattern: "logs:*" },
          { priority: 1 }
        )
        .catch((error) => {
          console.warn("Unable to queue log cache invalidation:", error.message);
        });
    } catch (error) {
      console.warn("Unable to queue log cache invalidation:", error);
    }
  }

  private stringOrNull(value: number | string | undefined): string | null {
    return value === undefined || value === null ? null : String(value);
  }
}
