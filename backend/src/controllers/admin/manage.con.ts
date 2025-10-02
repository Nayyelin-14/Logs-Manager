import { NextFunction, Response } from "express";
import { CustomRequest } from "../../utils/refreshToken";
import { body, param, query, validationResult } from "express-validator";
import {
  createNewUser,
  deleteUserById,
  getAllUserListByPagi,
  getUserById,
  updateUser,
} from "../../services/auth.service";
import { checkUserIfNotExist } from "../../utils/auth.utils";
import { errorCode } from "../../config/errrorcode";
import { handleError } from "../../utils/errorHandeling";
import { Prisma, PrismaClient } from "../../generated/prisma";

import bcrypt from "bcryptjs";
import { getOrSetCache } from "../../utils/cacheHelper";
import cacheQueue from "../../jobs/queues/cacheQueue";

const prisma = new PrismaClient();

export const updateUserController = [
  body("userId").notEmpty().withMessage("User ID is required").isInt(),
  body("username")
    .optional()
    .isString()
    .withMessage("Username must be a string"),
  body("email").optional().isEmail().withMessage("Invalid email"),
  body("role")
    .optional()
    .isIn(["USER", "ADMIN"])
    .withMessage("Role must be USER or ADMIN"),
  body("status")
    .optional()
    .isIn(["FREEZE", "INACTIVE", "ACTIVE"])
    .withMessage("Invalid status"),
  body("tenant")
    .trim()
    .notEmpty()
    .withMessage("Tenant is required")
    .isLength({ min: 2, max: 50 })
    .withMessage("Tenant must be 2-50 characters"),
  async (req: CustomRequest, res: Response, next: NextFunction) => {
    try {
      // Validate request body
      const errors = validationResult(req).array({ onlyFirstError: true });

      if (errors.length > 0) {
        const error: any = new Error(errors[0].msg);
        error.status = 400;
        error.code = errorCode.invalid;
        return next(error); //This next(error) skips all other routes/middlewares and jumps directly to your error-handling middleware:
      }
      // Auth check: only admins
      const currentUser = req.user; // assume you attach currentUser in middleware
      if (!currentUser || currentUser.role !== "ADMIN") {
        return res.status(403).json({ message: "Forbidden: Admins only" });
      }

      const { userId, username, email, role, status, tenant } = req.body;

      // Check if user exists
      const existedUser = await getUserById(userId);
      await checkUserIfNotExist(existedUser);

      // Prepare update data
      const updateData: any = {};
      if (username !== undefined) updateData.username = username;
      if (email !== undefined) updateData.email = email;

      if (role !== undefined) updateData.role = role;
      if (tenant !== undefined) updateData.tenant = tenant;
      if (status !== undefined) updateData.status = status;

      // Update user
      const updatedUserData = await updateUser(updateData, userId);

      return res.status(200).json({
        success: true,
        message: "User updated successfully",
        user: updatedUserData,
      });
    } catch (error) {
      console.error("Error updating user:", error);
      return res.status(500).json({ message: "Internal server error" });
    }
  },
];

export const deleteUser = [
  param("userId").notEmpty().withMessage("User ID is required").isInt(),
  async (req: CustomRequest, res: Response, next: NextFunction) => {
    try {
      // Validate request body
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
      }

      // Auth check: only admins
      if (!req.user || req.user.role !== "ADMIN") {
        return res.status(403).json({ message: "Forbidden: Admins only" });
      }

      const { userId } = req.params;

      // Check if user exists
      const existedUser = await getUserById(Number(userId));
      await checkUserIfNotExist(existedUser);

      // Delete user
      const userdeletion = await deleteUserById(Number(userId));
      await cacheQueue.add(
        "invalidate-user-cache",
        {
          pattern: "users:*",
        },
        {
          jobId: `invalidate-${Date.now()}`,
          priority: 1,
        }
      );
      return res
        .status(200)
        .json({ success: true, message: "User deleted", data: userdeletion });
    } catch (error) {
      console.error("Error deleting user:", error);
      return res.status(500).json({ message: "Internal server error" });
    }
  },
];

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
      filters.tenant = {
        contains: tenant as string,
        mode: "insensitive",
      };
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
      orderBy: {
        id: "desc",
      },
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

export const createUser = [
  body("username")
    .trim()
    .notEmpty()
    .withMessage("Name is required")
    .isLength({ min: 2, max: 50 })
    .withMessage("Name must be between 2 and 50 characters"),
  query("role", "Invalid role").isIn(["ADMIN", "USER"]).optional(),
  body("email")
    .trim()
    .notEmpty()
    .withMessage("Email is required")
    .isEmail()
    .withMessage("Invalid email address"),
  body("tenant")
    .trim()
    .notEmpty()
    .withMessage("Tenant is required")
    .isLength({ min: 2, max: 50 })
    .withMessage("Tenant must be 2-50 characters"),
  body("password", "Invalid Credentials")
    .trim()
    .notEmpty()
    .matches(/^[0-9]+$/)
    .isLength({ min: 8, max: 8 }),
  body("confirmPassword", "Invalid Credentials")
    .trim()
    .notEmpty()
    .matches(/^[0-9]+$/)
    .isLength({ min: 8, max: 8 }),
  async (req: CustomRequest, res: Response, next: NextFunction) => {
    const errors: any = validationResult(req).array({ onlyFirstError: true });

    if (errors.length > 0) {
      return next(handleError(errors[0].msg, 400, errorCode.invalid));
    }
    const { email, username, role, tenant, password, confirmPassword } =
      req.body;

    if (!email || !username || !tenant || !password || !confirmPassword) {
      return res.status(400).json({ message: "All field sare required" });
    }
    const userId = req.user?.userId;

    const user = await getUserById(Number(userId!));
    await checkUserIfNotExist(user);

    if (user?.role !== "ADMIN") {
      return next(
        handleError("Unauthorized user detected ", 400, errorCode.unauthorized)
      );
    }
    if (password !== confirmPassword) {
      return res.status(400).json({ message: "Passwords do not  match" });
    }
    const hashedPassword = await bcrypt.hash(password, 10);
    const newUserData = {
      username,
      email,
      password: hashedPassword,
      tenant,
      role,
    };
    const newUser = await createNewUser(newUserData);

    await cacheQueue.add(
      "invalidate-post-cache",
      {
        pattern: "users:*",
      },
      {
        jobId: `invalidate-${Date.now()}`,
        priority: 1,
      }
    );
    return res.status(201).json({
      message: "New user created successfully",
      newUser,
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
            tenant: {
              contains: tenant as string,
              mode: "insensitive" as Prisma.QueryMode,
            },
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
