"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.AlertService = void 0;
const queueHelper_1 = require("./queueHelper");
const PrismaClient_1 = require("../config/PrismaClient");
class AlertService {
    async checkAlerts(event) {
        const rules = await PrismaClient_1.prisma.alertRule.findMany({
            where: {
                tenant: event.tenant,
                enabled: true,
            },
        });
        const triggeredAlerts = [];
        for (const rule of rules) {
            if (await this.evaluateRule(rule, event)) {
                const alert = await this.triggerAlert(rule, event);
                if (alert?.success) {
                    triggeredAlerts.push(alert.alert);
                }
            }
        }
        return triggeredAlerts;
    }
    async evaluateRule(rule, event) {
        // Only one condition per rule
        const condition = rule.conditions?.[0];
        if (!condition)
            return false;
        switch (condition.type) {
            case "event_type":
                return event.eventType === condition.value;
            case "severity_min":
                return (event.severity ?? 0) >= condition.value;
            case "field_value":
                return event[condition.field] === condition.value;
            case "threshold_count":
            case "repeated_failures":
                const threshold = parseInt(condition.threshold, 10) || 1;
                const windowSeconds = parseInt(condition.windowSeconds, 10) || 300;
                const windowStart = new Date(Date.now() - windowSeconds * 1000);
                const count = await PrismaClient_1.prisma.securityEvent.count({
                    where: {
                        tenant: event.tenant,
                        eventType: event.eventType,
                        user: event.user,
                        timestamp: { gte: windowStart },
                    },
                });
                return count >= threshold;
            default:
                console.warn("Unknown condition type:", condition.type);
                return false;
        }
    }
    async triggerAlert(rule, event) {
        try {
            const condition = rule.conditions?.[0];
            const severity = condition?.severity ?? "medium";
            const createdAlert = await PrismaClient_1.prisma.alert.create({
                data: {
                    ruleId: rule.id,
                    tenant: rule.tenant,
                    title: `Alert: ${rule.name}`,
                    description: `Alert triggered by rule: ${rule.name}`,
                    severity: severity,
                    eventIds: [event.id],
                },
            });
            if (event.user) {
                const user = await PrismaClient_1.prisma.user.findFirst({
                    where: { username: event.user, tenant: createdAlert.tenant },
                    select: { email: true },
                });
                if (user?.email) {
                    try {
                        await (0, queueHelper_1.AlertEmailQueue)({
                            email: user.email,
                            username: event.user,
                            tenant: createdAlert.tenant,
                            title: createdAlert.title,
                            description: createdAlert.description,
                            severity: createdAlert.severity,
                        });
                    }
                    catch (emailError) {
                        console.error("Could not queue alert notification:", emailError);
                    }
                }
            }
            return {
                success: true,
                message: "Alert created successfully.",
                alert: createdAlert,
            };
        }
        catch (error) {
            console.error("Error triggering alert:", error);
            return {
                success: false,
                message: error.message || "Failed to trigger alert.",
            };
        }
    }
}
exports.AlertService = AlertService;
//# sourceMappingURL=alertService.js.map