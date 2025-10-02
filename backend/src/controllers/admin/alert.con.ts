import { NextFunction, Response } from "express";
import { CustomRequest } from "../../utils/refreshToken";
import {
  CreateAlertRuleInput,
  createNewAlertRule,
  deleteExistedAlert,
  duplicate,
  getAllRules,
  getExistedAlertRule,
  updateAlertRuleById,
} from "../../services/alert.service";
import { body, param, query, validationResult } from "express-validator";
import { getUserById } from "../../services/auth.service";
import { checkUserIfNotExist } from "../../utils/auth.utils";
import { checkExistedAlertRule } from "../../utils/alert.util";
import { handleError } from "../../utils/errorHandeling";
import { errorCode } from "../../config/errrorcode";
import { getOrSetCache } from "../../utils/cacheHelper";

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
    .isString()
    .withMessage("Condition type must be a string"),
  body("conditions.*.field")
    .optional()
    .isString()
    .withMessage("Field must be a string"),
  body("conditions.*.value").optional(),
  body("conditions.*.threshold")
    .optional()
    .isInt({ min: 0 })
    .withMessage("Threshold must be a non-negative integer"),
  body("conditions.*.windowSeconds")
    .optional()
    .isInt({ min: 0 })
    .withMessage("WindowSeconds must be a non-negative integer"),

  // Controller
  async (req: CustomRequest, res: Response) => {
    try {
      const { name, description, tenant, conditions } = req.body;

      if (!req.user) {
        return res.status(401).json({ message: "Unauthenticated User" });
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
      console.error("Error creating AlertRule:", error);
      return res.status(500).json({ message: "Internal server error" });
    }
  },
];

// DELETE ALERT RULE
export const deleteAlertRule = [
  param("id", "Rule Id is required.").trim().notEmpty().escape(),
  async (req: CustomRequest, res: Response) => {
    try {
      const { id } = req.params;

      if (!id) {
        return res.status(400).json({ message: "Missing AlertRule ID" });
      }

      if (!req.user || req.user.role !== "ADMIN") {
        return res.status(403).json({ message: "Forbidden: Admins only" });
      }

      const { userId } = req.user;
      const user = await getUserById(userId!);
      await checkUserIfNotExist(user);

      console.log(id);
      const existedRules = await getExistedAlertRule({ id });
      const existedRule = existedRules[0];

      if (!existedRule) {
        return res.status(404).json({ message: "AlertRule not found" });
      }

      // Delete the alert rule
      await deleteExistedAlert(existedRule.id);

      await cacheQueue.add(
        "invalidate-rule-cache",
        {
          pattern: "rules:*",
        },
        {
          jobId: `invalidate-${Date.now()}`,
          priority: 1,
        }
      );

      return res
        .status(200)
        .json({ message: "AlertRule deleted successfully" });
    } catch (error) {
      console.error("Error deleting AlertRule:", error);
      return res.status(500).json({ message: "Internal server error" });
    }
  },
];

// export const updateAlertRule = [
//   body("id").notEmpty().withMessage("AlertRule ID is required").isString(),
//   body("name").notEmpty().withMessage("Name is required").isString(),
//   body("tenant").notEmpty().withMessage("Tenant is required").isString(),
//   body("condition")
//     .notEmpty()
//     .withMessage("Condition is required")
//     .isString()
//     .isLength({ max: 52 })
//     .withMessage("Condition must be at most 52 characters"),
//   body("threshold")
//     .notEmpty()
//     .withMessage("Threshold is required")
//     .isInt({ min: 0 })
//     .withMessage("Threshold must be a positive integer"),
//   body("windowSeconds")
//     .optional()
//     .isInt({ min: 0 })
//     .withMessage("windowSeconds must be a positive integer"),
//   body("enabled").optional().isBoolean().withMessage("Enabled must be boolean"),
//   body("description").optional().isString(),
//   async (req: CustomRequest, res: Response, next: NextFunction) => {
//     try {
//       const {
//         id,
//         name,
//         description,
//         tenant,
//         enabled,
//         condition,
//         threshold,
//         windowSeconds,
//       } = req.body;

//       if (!id) {
//         return res.status(400).json({ message: "Missing AlertRule ID" });
//       }

//       // Auth check
//       if (!req.user) {
//         return res.status(401).json({ message: "Unauthenticated User" });
//       }

//       // Check if the rule exists
//       const existedRule = await getExistedAlertRule(undefined, undefined, id);
//       if (!existedRule) {
//         return res.status(404).json({ message: "AlertRule not found" });
//       }

//       // If updating tenant + name, check for duplicate
//       if (tenant && name) {
//         const checkDuplicate = await duplicate(tenant, name);

//         if (checkDuplicate) {
//           return res.status(400).json({
//             message:
//               "Another rule with this name already exists for this tenant.",
//           });
//         }
//       }

//       // Update the alert rule

//       const updateData = {
//         name: name ?? existedRule.name,
//         description: description ?? existedRule.description,
//         tenant: tenant ?? existedRule.tenant,
//         enabled: enabled !== undefined ? enabled : existedRule.enabled,
//         condition: condition ?? existedRule.condition,
//         threshold: threshold ?? existedRule.threshold,
//         windowSeconds:
//           windowSeconds !== undefined
//             ? windowSeconds
//             : existedRule.windowSeconds,
//       };

//       const updatedRule = await updateAlertRuleById(updateData, id);

//       return res.status(200).json({
//         message: "Updated the selected rule successfully.",
//         ruleId: updatedRule.id,
//       });
//     } catch (error) {
//       console.error("Error updating AlertRule:", error);
//       return res.status(500).json({ message: "Internal server error" });
//     }
//   },
// ];

export const getAllAlertRule = [
  query("date", "Invalid date").isISO8601().toDate().optional(),
  query("search")
    .optional()
    .isString()
    .withMessage("Search must be a string")
    .isLength({ min: 1, max: 100 })
    .withMessage("Search must be between 1 and 100 characters"),
  query("limit")
    .optional()
    .isInt({ min: 1 })
    .withMessage("Limit must be a positive integer"),
  query("tenant").optional().isString().withMessage("Tenant must be a string"),
  query("cursor").optional().isString().withMessage("Cursor must be a string"),

  async (req: CustomRequest, res: Response, next: NextFunction) => {
    const errors: any = validationResult(req).array({ onlyFirstError: true });
    if (errors.length > 0) {
      return next(handleError(errors[0].msg, 400, errorCode.invalid));
    }

    const { date, search, tenant } = req.query;
    const userId = req.user?.userId;
    const user = await getUserById(Number(userId!));
    await checkUserIfNotExist(user);

    const lastCursor = req.query.cursor ? req.query.cursor : undefined;
    const limit = req.query.limit ? Number(req.query.limit) : 5;

    const filters: any = {};
    if (tenant && tenant !== "all") {
      filters.tenant = { contains: tenant as string, mode: "insensitive" };
    }

    if (date) {
      const targetDate = new Date(date as string);
      const nextDay = new Date(targetDate);
      nextDay.setDate(targetDate.getDate() + 1);
      filters.createdAt = { gte: targetDate, lt: nextDay };
    }

    if (search) {
      filters.OR = [
        { name: { contains: search as string, mode: "insensitive" } },
        { tenant: { contains: search as string, mode: "insensitive" } },
      ];
    }

    const options = {
      where: filters,
      skip: lastCursor ? 1 : 0,
      cursor: lastCursor ? { id: lastCursor } : undefined,
      take: limit + 1,
      orderBy: { id: "desc" },
      select: {
        id: true,
        name: true,
        description: true,
        tenant: true,

        conditions: true,

        createdAt: true,
        updatedAt: true,
        alerts: {
          orderBy: { triggeredAt: "desc" },
        },
      },
    };

    const cacheKey = `rules:${JSON.stringify(req.query)}`;
    const rules = await getOrSetCache(cacheKey, async () => {
      return await getAllRules(options);
    });

    const hasNextPage = rules.length > limit;
    if (hasNextPage) rules.pop();

    const newCursor = hasNextPage ? rules[rules.length - 1].id : null;

    res.status(200).json({
      rules,
      hasNextPage,
      newCursor,
    });
  },
];
