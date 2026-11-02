import { NextFunction, Response } from "express";
import { query, validationResult } from "express-validator";
import { CustomRequest } from "../../utils/refreshToken";
import { getAllUserListByPagi, getUserById } from "../../services/auth.service";
import { checkUserIfNotExist } from "../../utils/auth.utils";
import { errorCode } from "../../config/errrorcode";
import { handleError } from "../../utils/errorHandeling";
import { prisma } from "../../config/PrismaClient";
import { getOrSetCache } from "../../utils/cacheHelper";

export const getAllUsers = [
  query("cursor", "Cursor number must be post id").isInt({ gt: 0 }).optional(),
  query("limit", "Limit number must be unsigned integer"),
  // 🔹 Role filter
  query("role", "Invalid role").isIn(["ADMIN", "USER"]).optional(),
  query("search")
    .optional() // search is optional
    .isString()
    .withMessage("Search must be a string")
    .isLength({ min: 1, max: 100 })
    .withMessage("Search must be between 1 and 100 characters"),
  // 🔹 Status filter
  query("status", "Invalid status")
    .isIn(["ACTIVE", "INACTIVE", "FREEZE", "all"])
    .optional(),
  query("tenant").optional().isString().withMessage("Tenant must be a string"),
  // 🔹 Date filter (ISO string)
  query("date", "Invalid  date").isISO8601().toDate().optional(),

  async (req: CustomRequest, res: Response, next: NextFunction) => {
    const errors: any = validationResult(req).array({ onlyFirstError: true });

    if (errors.length > 0) {
      return next(handleError(errors[0].msg, 400, errorCode.invalid)); //This next(error) skips all other routes/middlewares and jumps directly to your error-handling middleware:
    }
    const { role, status, date, search, tenant } = req.query;
    const userId = req.user?.userId;

    const user = await getUserById(Number(userId!));
    await checkUserIfNotExist(user);

    const lastCursor = req.query.cursor ? Number(req.query.cursor) : undefined;
    const limit = req.query.limit ? Number(req.query.limit) : 5;

    const filters: any = {};
    if (role) {
      filters.role = role;
    }
    if (tenant && tenant !== "all") {
      filters.tenant = tenant as string;
    }
    if (status) {
      filters.status = status;
    }

    if (date) {
      const targetDate = new Date(date as string);
      const nextDay = new Date(targetDate);
      nextDay.setDate(targetDate.getDate() + 1);

      filters.createAt = {
        gte: targetDate,
        lt: nextDay, // strictly less than next day = exact date
      };
    }
    if (search) {
      filters.OR = [
        { username: { contains: search as string, mode: "insensitive" } },
        { email: { contains: search as string, mode: "insensitive" } },
      ];
    }

    const options = {
      where: filters,
      skip: lastCursor ? 1 : 0, //	cursor ကို exclude (မထည့်) လုပ်ဖို့
      cursor: lastCursor ? { id: Number(lastCursor) } : undefined,
      take: Number(limit) + 1, // get 1 extra to check if there's a next page
      orderBy: [{ createAt: "desc" }, { id: "desc" }],
      select: {
        id: true,
        username: true,
        email: true,
        role: true,
        tenant: true,
        status: true,
        createAt: true,
      },
    };
    const cacheKey = `users:${JSON.stringify(req.query)}`;
    const usersList = await getOrSetCache(cacheKey, async () => {
      return await getAllUserListByPagi(options);
    });

    const hasNextPage = usersList.length > limit;
    if (hasNextPage) {
      usersList.pop();
    }
    const newCursor =
      usersList.length > 0 ? usersList[usersList.length - 1].id : null;

    res.status(200).json({
      usersList,
      hasNextPage,
      newCursor,
    });
  },
];
export const getAllDataCount = [
  query("tenant", "Invalid Tenant.").trim().escape().optional(),
  async (req: CustomRequest, res: Response, next: NextFunction) => {
    const errors = validationResult(req).array({ onlyFirstError: true });
    if (errors.length > 0) {
      return next(handleError(errors[0].msg, 400, errorCode.invalid));
    }
    const { tenant } = req.query;

    // Build filter only if tenant exists and is not "all"
    const tenantFilter =
      tenant && tenant !== "all"
        ? {
            tenant: tenant as string,
          }
        : {};

    // Get counts for multiple tables
    const [allLogs, allUsers, allAlerts, allRules] = await Promise.all([
      prisma.securityEvent.count({ where: tenantFilter }),
      prisma.user.count({ where: tenantFilter }),
      prisma.alert.count({ where: tenantFilter }),
      prisma.alertRule.count({ where: tenantFilter }),
    ]);

    const tenants = await prisma.user.findMany({
      select: { tenant: true },
      distinct: ["tenant"], // ensures each tenant appears only once
    });
    res.status(200).json({
      message: "All data count",
      data: {
        allLogs,
        allUsers,
        allAlerts,
        allRules,
        tenants,
      },
    });
  },
];
