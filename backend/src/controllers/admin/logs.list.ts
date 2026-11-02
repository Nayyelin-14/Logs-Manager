import { NextFunction, Response } from "express";
import { query, validationResult } from "express-validator";
import { Action, Source } from "../../generated/prisma";
import { CustomRequest } from "../../utils/refreshToken";
import { getUserById } from "../../services/auth.service";
import { checkUserIfNotExist } from "../../utils/auth.utils";
import { handleError } from "../../utils/errorHandeling";
import { errorCode } from "../../config/errrorcode";
import { getAllLogsListByPagi } from "../../services/logs.service";
import { severityLevelMap } from "../../types/index.types";
import { getOrSetCache } from "../../utils/cacheHelper";

export const getAllLogs = [
  query("tenant").optional().isString().withMessage("Tenant must be a string"),

  query("source")
    .optional()
    .isIn(Object.values(Source))
    .withMessage(`Source must be one of: ${Object.values(Source).join(", ")}`),

  query("action")
    .optional()
    .isIn(Object.values(Action))
    .withMessage(`Action must be one of: ${Object.values(Action).join(", ")}`),
  query("severity")
    .optional()
    .isString() // allow "Low", "Medium", "High" from frontend
    .withMessage("Severity must be Low, Medium, or High"),
  query("search")
    .optional() // search is optional
    .isString()
    .withMessage("Search must be a string")
    .isLength({ min: 1, max: 100 })
    .withMessage("Search must be between 1 and 100 characters"),
  query("limit")
    .optional()
    .isInt({ min: 1 })
    .withMessage("Limit must be a positive integer"),
  query("cursor").optional().isString().withMessage("Cursor must be a string"),

  async (req: CustomRequest, res: Response, next: NextFunction) => {
    const errors: any = validationResult(req).array({ onlyFirstError: true });

    if (errors.length > 0) {
      return next(handleError(errors[0].msg, 400, errorCode.invalid)); //This next(error) skips all other routes/middlewares and jumps directly to your error-handling middleware:
    }
    const { tenant, source, action, severity, date, search } = req.query;
    console.log(tenant, source, action, severity, date, search);
    const userId = req.user?.userId;

    const user = await getUserById(Number(userId!));
    await checkUserIfNotExist(user);

    const lastCursor = req.query.cursor ? req.query.cursor : undefined;
    const limit = req.query.limit ? Number(req.query.limit) : 5;

    const filters: any = {};
    if (user?.role === "USER") {
      filters.tenant = user.tenant;
      filters.user = {
        equals: user.username ?? user.email,
        mode: "insensitive",
      };
    } else if (tenant && tenant !== "all") {
      filters.tenant = {
        equals: tenant as string,
      };
    }
    if (source) {
      filters.source = source;
    }
    if (action) {
      filters.action = action;
    }
    if (severity && typeof severity === "string") {
      const key = severity.toLowerCase(); // lowercase to match map
      const level = severityLevelMap[key];
      console.log(level);
      if (level) {
        filters.severity = { gte: level.min, lte: level.max };
      }
    }

    if (date) {
      const targetDate = new Date(date as string);
      const nextDay = new Date(targetDate);
      nextDay.setDate(targetDate.getDate() + 1);

      filters.timestamp = {
        gte: targetDate,
        lt: nextDay, // all rows where timestamp falls within that day
      };
    }
    if (search) {
      filters.OR = [
        { user: { contains: search as string, mode: "insensitive" } },
        { description: { contains: search as string, mode: "insensitive" } },
        { srcIp: { contains: search as string, mode: "insensitive" } },
        { eventType: { contains: search as string, mode: "insensitive" } },
      ];
    }

    const options = {
      where: filters,
      skip: lastCursor ? 1 : 0, //	cursor ကို exclude (မထည့်) လုပ်ဖို့
      cursor: lastCursor ? { id: lastCursor } : undefined,
      take: Number(limit) + 1, // get 1 extra to check if there's a next page
      orderBy: [{ timestamp: "desc" }, { id: "desc" }],
      select: {
        id: true,
        action: true,
        user: true,
        srcIp: true,
        source: true,
        tenant: true,
        eventType: true, // <-- use model field name, NOT column name
        severity: true,
        timestamp: true,
      },
    };
    const cacheKey = `logs:${req.user?.userId}:${JSON.stringify(req.query)}`;
    const logs = await getOrSetCache(cacheKey, async () => {
      return await getAllLogsListByPagi(options);
    });

    const hasNextPage = logs.length > limit;
    if (hasNextPage) {
      logs.pop();
    }

    const newCursor = hasNextPage ? logs[logs.length - 1].id : null;

    res.status(200).json({
      logs,
      hasNextPage,
      newCursor,
    });
  },
];
