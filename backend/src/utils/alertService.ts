import {
  PrismaClient,
  SecurityEvent,
  AlertRule,
  Prisma,
} from "../generated/prisma";

const prisma = new PrismaClient();

export class AlertService {
  async checkAlerts(event: SecurityEvent) {
    console.log("incoming", event);
    const rules = await prisma.alertRule.findMany({
      where: {
        tenant: event.tenant,
      },
    });

    for (const rule of rules) {
      console.log(rule, "rule");
      if (await this.evaluateRule(rule, event)) {
        await this.triggerAlert(rule, event);
      }
    }
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
    await prisma.alert.create({
      data: {
        ruleId: rule.id,
        tenant: rule.tenant,
        title: `Alert: ${rule.name}`,
        description: `Alert triggered by rule: ${rule.name}`,
        severity: "medium",
        eventIds: [event.id],
      },
    });
  }
}
