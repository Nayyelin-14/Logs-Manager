import { Response } from "express";
import { body, validationResult } from "express-validator";
import { CustomRequest } from "../../utils/refreshToken";
import {
  createNewAlertRule,
  getExistedAlertRule,
} from "../../services/alert.service";
import { getUserById } from "../../services/auth.service";
import { checkUserIfNotExist } from "../../utils/auth.utils";
import { checkExistedAlertRule } from "../../utils/alert.util";
import cacheQueue from "../../jobs/queues/cacheQueue";

export const createAlertRule = [
  // Basic info
  body("name").notEmpty().withMessage("Name is required").isString(),
  body("tenant").notEmpty().withMessage("Tenant is required").isString(),
  body("description").optional().isString(),

  // Conditions array
  body("conditions")
    .isArray({ min: 1, max: 1 })
    .withMessage("Conditions must be an array with exactly 1 condition"),

  // Condition fields
  body("conditions.*.type")
    .notEmpty()
    .withMessage("Condition type is required")
    .isIn(["event_type", "severity_min", "field_value", "repeated_failures"])
    .withMessage("Unsupported condition type"),
  body("conditions.*.field")
    .optional()
    .isIn(["action", "eventType", "severity", "srcIp", "dstIp", "user", "host", "process", "status"])
    .withMessage("Choose a supported event field"),
  body("conditions.*.value").optional(),
  body("conditions.*.threshold")
    .optional()
    .isInt({ min: 1 })
    .withMessage("Threshold must be a positive integer"),
  body("conditions.*.windowSeconds")
    .optional()
    .isInt({ min: 1 })
    .withMessage("WindowSeconds must be a positive integer"),

  // Controller
  async (req: CustomRequest, res: Response) => {
    try {
      const errors = validationResult(req).array({ onlyFirstError: true });
      if (errors.length) {
        return res.status(400).json({ message: errors[0].msg });
      }
      const { name, description, tenant, conditions } = req.body;

      if (!req.user) {
        return res.status(401).json({ message: "Unauthenticated User" });
      }
      const condition = conditions[0];
      if (
        ((condition.type === "event_type" || condition.type === "severity_min") &&
          (condition.value === undefined || String(condition.value).trim() === "")) ||
        (condition.type === "field_value" &&
          (!condition.field || condition.value === undefined || String(condition.value).trim() === "")) ||
        (condition.type === "repeated_failures" &&
          (condition.threshold === undefined ||
            condition.windowSeconds === undefined))
      ) {
        return res.status(400).json({
          message: "The selected condition is missing required values.",
        });
      }
      if (
        condition.type === "severity_min" &&
        (!Number.isInteger(Number(condition.value)) ||
          Number(condition.value) < 0 ||
          Number(condition.value) > 10)
      ) {
        return res.status(400).json({ message: "Severity must be between 0 and 10." });
      }

      const { userId } = req.user;
      const user = await getUserById(userId!);
      await checkUserIfNotExist(user);

      // Check if a rule already exists for this tenant and name
      const existedRule = await getExistedAlertRule({ tenant, name });
      await checkExistedAlertRule(existedRule);

      const newAlertRule = {
        name,
        description,
        tenant,
        conditions, // exactly one condition
      };

      const createdRule = await createNewAlertRule(newAlertRule);

      // Invalidate cache
      await cacheQueue.add(
        "invalidate-rule-cache",
        { pattern: "rules:*" },
        { jobId: `invalidate-${Date.now()}`, priority: 1 }
      );

      return res
        .status(201)
        .json({ message: "Alert rule is created", createdRule });
    } catch (error) {
      const status = (error as any)?.status;
      if (status) {
        return res.status(status).json({ message: (error as Error).message });
      }
      return res.status(500).json({ message: "Internal server error" });
    }
  },
];

// DELETE ALERT RULE
