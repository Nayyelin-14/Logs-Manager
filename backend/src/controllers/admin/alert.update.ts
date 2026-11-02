import { Response } from "express";
import { body, param, validationResult } from "express-validator";
import { prisma } from "../../config/PrismaClient";
import cacheQueue from "../../jobs/queues/cacheQueue";
import { duplicate, updateAlertRuleById } from "../../services/alert.service";
import { CustomRequest } from "../../utils/refreshToken";

const invalidateRules = async () => {
  await cacheQueue.add(
    "invalidate-rule-cache",
    { pattern: "rules:*" },
    { jobId: `invalidate-${Date.now()}`, priority: 1 }
  );
};

const validateRuleFields = [
  body("name").trim().notEmpty().isLength({ max: 100 }),
  body("tenant").trim().notEmpty().isLength({ min: 2, max: 50 }),
  body("description").optional().isString(),
  body("conditions").isArray({ min: 1, max: 1 }),
  body("conditions.*.type").isIn([
    "event_type",
    "severity_min",
    "field_value",
    "repeated_failures",
  ]),
  body("conditions.*.field")
    .optional()
    .isIn(["action", "eventType", "severity", "srcIp", "dstIp", "user", "host", "process", "status"]),
  body("conditions.*.value").optional(),
  body("conditions.*.threshold").optional().isInt({ min: 1 }),
  body("conditions.*.windowSeconds").optional().isInt({ min: 1 }),
];

export const updateAlertRule = [
  param("id").isString().notEmpty(),
  ...validateRuleFields,
  async (req: CustomRequest, res: Response) => {
    const errors = validationResult(req).array({ onlyFirstError: true });
    if (errors.length) {
      return res.status(400).json({ message: errors[0].msg });
    }

    const existing = await prisma.alertRule.findUnique({
      where: { id: req.params.id },
    });
    if (!existing) return res.status(404).json({ message: "Rule not found." });

    const { name, description, tenant, conditions } = req.body;
    const duplicateRule = await duplicate(tenant, name, req.params.id);
    if (duplicateRule) {
      return res.status(409).json({ message: "A rule with this name already exists in that tenant." });
    }

    const condition = conditions[0];
    if (
      ((condition.type === "event_type" || condition.type === "severity_min") &&
        (condition.value === undefined || String(condition.value).trim() === "")) ||
      (condition.type === "field_value" &&
        (!condition.field || condition.value === undefined || String(condition.value).trim() === "")) ||
      (condition.type === "repeated_failures" &&
        (condition.threshold === undefined || condition.windowSeconds === undefined))
    ) {
      return res.status(400).json({ message: "The selected condition is missing required values." });
    }
    if (
      condition.type === "severity_min" &&
      (!Number.isInteger(Number(condition.value)) ||
        Number(condition.value) < 0 ||
        Number(condition.value) > 10)
    ) {
      return res.status(400).json({ message: "Severity must be between 0 and 10." });
    }

    const rule = await updateAlertRuleById(
      { name, description, tenant, conditions },
      req.params.id
    );
    await invalidateRules();
    return res.status(200).json({ message: "Alert rule updated.", rule });
  },
];

export const setAlertRuleEnabled = [
  param("id").isString().notEmpty(),
  body("enabled").isBoolean(),
  async (req: CustomRequest, res: Response) => {
    const errors = validationResult(req).array({ onlyFirstError: true });
    if (errors.length) {
      return res.status(400).json({ message: errors[0].msg });
    }

    const exists = await prisma.alertRule.findUnique({
      where: { id: req.params.id },
      select: { id: true },
    });
    if (!exists) return res.status(404).json({ message: "Rule not found." });

    const rule = await prisma.alertRule.update({
      where: { id: req.params.id },
      data: { enabled: req.body.enabled },
    });
    await invalidateRules();
    return res.status(200).json({
      message: `Rule ${rule.enabled ? "enabled" : "disabled"}.`,
      rule,
    });
  },
];
