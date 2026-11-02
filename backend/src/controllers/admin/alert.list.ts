import { NextFunction, Response } from "express";
import { query, validationResult } from "express-validator";
import { CustomRequest } from "../../utils/refreshToken";
import { getAllRules } from "../../services/alert.service";
import { getUserById } from "../../services/auth.service";
import { checkUserIfNotExist } from "../../utils/auth.utils";
import { handleError } from "../../utils/errorHandeling";
import { errorCode } from "../../config/errrorcode";
import { getOrSetCache } from "../../utils/cacheHelper";

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
      filters.tenant = { equals: tenant as string };
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
        { description: { contains: search as string, mode: "insensitive" } },
        { tenant: { contains: search as string, mode: "insensitive" } },
      ];
    }

    const options = {
      where: filters,
      skip: lastCursor ? 1 : 0,
      cursor: lastCursor ? { id: lastCursor } : undefined,
      take: limit + 1,
      orderBy: [{ createdAt: "desc" }, { id: "desc" }],
      select: {
        id: true,
        name: true,
        description: true,
        tenant: true,
        enabled: true,

        conditions: true,

        createdAt: true,
        updatedAt: true,
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
