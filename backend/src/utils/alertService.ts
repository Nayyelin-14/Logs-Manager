import {
  PrismaClient,
  SecurityEvent,
  AlertRule,
  Prisma,
} from "../generated/prisma";
import { AlertEmailQueue } from "./queueHelper";

const prisma = new PrismaClient();

export class AlertService {
  async checkAlerts(event: SecurityEvent) {
    console.log("incoming", event);
    const rules = await prisma.alertRule.findMany({
      where: {
        tenant: event.tenant,
      },
    });

    const triggeredAlerts: any[] = [];

    for (const rule of rules) {
      console.log(rule, "rule");
      if (await this.evaluateRule(rule, event)) {
        const alert = await this.triggerAlert(rule, event);
        if (alert?.success) {
          triggeredAlerts.push(alert.alert);
        }
      }
    }

    return triggeredAlerts;
  }

  private async evaluateRule(
    rule: AlertRule,
    event: SecurityEvent & Record<string, any>
  ): Promise<boolean> {
    // Only one condition per rule
    const condition = (
      rule.conditions as Prisma.JsonValue[] | undefined
    )?.[0] as Record<string, any> | undefined;

    console.log("condition", condition);
    if (!condition) return false;

    switch (condition.type) {
      case "event_type":
        return event.eventType === condition.value;

      case "severity_min":
        return (event.severity ?? 0) >= condition.value;

      case "field_value":
        return event[condition.field] === condition.value;

      case "repeated_failures":
        const threshold = parseInt(condition.threshold, 10) || 1;
        const windowSeconds = parseInt(condition.windowSeconds, 10) || 300;

        const windowStart = new Date(Date.now() - windowSeconds * 1000);

        const count = await prisma.securityEvent.count({
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

  private async triggerAlert(rule: AlertRule, event: SecurityEvent) {
    try {
      const condition = (
        rule.conditions as Prisma.JsonValue[] | undefined
      )?.[0] as Record<string, any> | undefined;
      const severity = condition?.severity ?? "medium";

      const createdAlert = await prisma.alert.create({
        data: {
          ruleId: rule.id,
          tenant: rule.tenant,
          title: `Alert: ${rule.name}`,
          description: `Alert triggered by rule: ${rule.name}`,
          severity: severity,
          eventIds: [event.id],
        },
      });

      if (!event.user) {
        throw new Error("Event has no associated user");
      }

      const user = await prisma.user.findFirst({
        where: { username: event.user },
        select: { email: true },
      });

      if (!user || !user.email) {
        throw new Error(`No email found for user: ${event.user}`);
      }

      await AlertEmailQueue({
        email: user.email,
        username: event.user,
        tenant: createdAlert.tenant,
        title: createdAlert.title,
        description: createdAlert.description,
        severity: createdAlert.severity,
      });

      return {
        success: true,
        message: "Alert created successfully.",
        alert: createdAlert,
      };
    } catch (error: any) {
      console.error("Error triggering alert:", error);
      return {
        success: false,
        message: error.message || "Failed to trigger alert.",
      };
    }
  }
}
