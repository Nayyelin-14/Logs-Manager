"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.IngestService = void 0;
const prisma_1 = require("../generated/prisma");
const PrismaClient_1 = require("../config/PrismaClient");
const normalize_1 = require("../utils/normalize");
const alertService_1 = require("../utils/alertService");
const errorHandeling_1 = require("../utils/errorHandeling");
const errrorcode_1 = require("../config/errrorcode");
const cacheQueue_1 = __importDefault(require("../jobs/queues/cacheQueue"));
const source_1 = require("../ingest/source");
class IngestService {
    alertService = new alertService_1.AlertService();
    normalizeSourceInput(value) {
        return (0, source_1.normalizeSourceInput)(value);
    }
    normalizeAction(value) {
        if (value === null || value === undefined)
            return null;
        const key = String(value)
            .trim()
            .toUpperCase()
            .replace(/[^A-Z]/g, "");
        switch (key) {
            case "ALLOW":
            case "PERMIT":
            case "ACCEPT":
            case "PASS":
                return prisma_1.Action.ALLOW;
            case "DENY":
            case "BLOCK":
            case "DROP":
            case "REJECT":
                return prisma_1.Action.DENY;
            case "CREATE":
            case "ADD":
                return prisma_1.Action.CREATE;
            case "DELETE":
            case "REMOVE":
                return prisma_1.Action.DELETE;
            case "LOGIN":
            case "SIGNIN":
            case "LOGON":
                return prisma_1.Action.LOGIN;
            case "LOGOUT":
            case "SIGNOUT":
            case "LOGOFF":
                return prisma_1.Action.LOGOUT;
            case "ALERT":
            case "DETECT":
            case "MALWARE":
                return prisma_1.Action.ALERT;
            case "QUARANTINE":
            case "ISOLATE":
                return prisma_1.Action.QUARANTINE;
            case "CREATEUSER":
            case "USERCREATED":
                return prisma_1.Action.CREATEUSER;
            default:
                return null;
        }
    }
    async ingest(rawEvent, sourceInput, context = {}) {
        if (!rawEvent || typeof rawEvent !== "object" || Array.isArray(rawEvent)) {
            throw (0, errorHandeling_1.handleError)("Each event must be a JSON object.", 400, errrorcode_1.errorCode.invalid);
        }
        const source = this.normalizeSourceInput(rawEvent.source) ??
            this.normalizeSourceInput(sourceInput) ??
            (0, source_1.inferSourceFromEvent)(rawEvent);
        const normalizedEvent = normalize_1.NormalizationService.normalizeEvent(rawEvent, source);
        const tenant = this.resolveTenant(rawEvent, context);
        const action = this.normalizeAction(normalizedEvent.action ?? rawEvent.action);
        const data = {
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
            loginType: normalizedEvent.loginType ??
                normalizedEvent.login_type ??
                null,
            interface: normalizedEvent.interface || null,
            mac: normalizedEvent.mac || null,
            description: normalizedEvent.description || null,
            ip: normalizedEvent.ip || normalizedEvent.srcIp || null,
            raw: (normalizedEvent.raw ?? rawEvent),
            tags: normalizedEvent.tags || [],
        };
        const event = await PrismaClient_1.prisma.securityEvent.create({ data });
        let alerts = [];
        try {
            alerts = (await this.alertService.checkAlerts(event)) || [];
        }
        catch (error) {
            console.error("Error evaluating alert rules:", error);
        }
        this.invalidateLogCache();
        return { event, alerts };
    }
    async ingestBatch(events, sourceInput, context = {}) {
        const results = [];
        let ingested = 0;
        for (let index = 0; index < events.length; index += 1) {
            try {
                const result = await this.ingest(events[index], sourceInput, context);
                ingested += 1;
                results.push({ index, success: true, eventId: result.event.id });
            }
            catch (error) {
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
    resolveTenant(rawEvent, context) {
        const requested = typeof rawEvent.tenant === "string" && rawEvent.tenant.trim() !== ""
            ? rawEvent.tenant.trim()
            : undefined;
        const bound = context.tenant?.trim() || undefined;
        if (bound) {
            if (requested && requested !== bound) {
                throw (0, errorHandeling_1.handleError)("Tenant does not match the authenticated identity.", 403, errrorcode_1.errorCode.unauthorized);
            }
            return bound;
        }
        return (requested ||
            process.env.INGEST_DEFAULT_TENANT ||
            process.env.SYSLOG_TENANT ||
            "demoA");
    }
    invalidateLogCache() {
        try {
            void cacheQueue_1.default
                .add("invalidate-log-cache", { pattern: "logs:*" }, { priority: 1 })
                .catch((error) => {
                console.warn("Unable to queue log cache invalidation:", error.message);
            });
        }
        catch (error) {
            console.warn("Unable to queue log cache invalidation:", error);
        }
    }
    stringOrNull(value) {
        return value === undefined || value === null ? null : String(value);
    }
}
exports.IngestService = IngestService;
//# sourceMappingURL=ingest.service.js.map