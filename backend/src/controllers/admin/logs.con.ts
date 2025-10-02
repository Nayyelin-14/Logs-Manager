import { NextFunction, Response } from "express";
import { AlertService } from "../../utils/alertService";
import { CustomRequest } from "../../utils/refreshToken";
import { NormalizationService } from "../../utils/normalize";
import { Action, PrismaClient, Source } from "../../generated/prisma";
import { getUserByEmail, getUserById } from "../../services/auth.service";
import {
  checkLogIfNotExist,
  checkUserIfNotExist,
} from "../../utils/auth.utils";
import { body, param, query, validationResult } from "express-validator";
import { handleError } from "../../utils/errorHandeling";
import { errorCode } from "../../config/errrorcode";

import {
  deleteLogById,
  getAllLogsListByPagi,
  getLogById,
} from "../../services/logs.service";
import { RawEvent, severityLevelMap } from "../../types/index.types";
import { getOrSetCache } from "../../utils/cacheHelper";
import cacheQueue from "../../jobs/queues/cacheQueue";

const prisma = new PrismaClient();

export const ingestEvent = [
  // Validation middleware
  body("tenant")
    .notEmpty()
    .withMessage("Tenant is required.")
    .isString()
    .withMessage("Tenant must be a string."),

  body("timestamp")
    .optional()
    .isISO8601()
    .withMessage("Timestamp must be a valid ISO8601 date."),

  body("source")
    .notEmpty()
    .withMessage("Source is required.")
    .isIn(Object.values(Source))
    .withMessage(`Source must be one of: ${Object.values(Source).join(", ")}`),

  body("priority").optional().isInt(),
  body("vendor")
    .optional()
    .isString()
    .trim()
    .notEmpty()
    .withMessage("Vendor must be non-empty string if provided"),
  body("product").optional().isString().trim(),
  body("eventType").optional().isString(),
  body("eventSubtype").optional().isString(),

  body("severity")
    .optional()
    .isInt({ min: 0, max: 10 })
    .withMessage("Severity must be between 0–10."),

  body("action")
    .optional()
    .isIn(Object.values(Action))
    .withMessage(`Action must be one of: ${Object.values(Action).join(", ")}`),

  body("srcIp").optional({ checkFalsy: true }),
  body("dstIp").optional({ checkFalsy: true }),
  body("url")
    .optional({ checkFalsy: true })
    .isURL()
    .withMessage("url must be a valid URL."),

  body("srcPort").optional().isInt({ min: 1, max: 65535 }),

  body("dstPort").optional().isInt({ min: 1, max: 65535 }),

  body("protocol").optional().isString(),
  body("host").optional().isString(),
  body("process").optional().isString(),
  body("eventId").optional().isInt(),

  body("httpMethod").optional().isString(),
  body("statusCode").optional().isInt(),
  body("ruleName").optional().isString(),
  body("ruleId").optional().isString(),
  body("cloudAccountId").optional().isString(),
  body("cloudRegion").optional().isString(),
  body("cloudService").optional().isString(),
  body("sha256").optional().isString(),
  body("status").optional().isString(),
  body("loginType").optional().isInt(),
  body("interface").optional().isString(),
  body("mac").optional().isString(),
  body("description").optional().isString(),
  body("ip").optional(),
  body("tags").optional().isArray(),
  body("raw").optional().isObject().withMessage("raw must be an object"),

  // Main handler
  async (req: CustomRequest, res: Response, next: NextFunction) => {
    try {
      const alertService = new AlertService();

      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({
          success: false,
          errors: errors.array(),
        });
      }

      if (!req.user?.userId) {
        return res.status(403).json({
          success: false,
          message: "Unauthenticated user alert",
        });
      }

      const { email, username } = req.user;
      const user = await getUserByEmail(email);
      await checkUserIfNotExist(user);

      const rawEvent: RawEvent = req.body;

      // Type-safe source
      const sourceValue: Source = Array.isArray(rawEvent.source)
        ? (rawEvent.source[0].toUpperCase() as Source)
        : (rawEvent.source?.toUpperCase() as Source);

      if (!Object.values(Source).includes(sourceValue)) {
        return res.status(400).json({
          success: false,
          message: `Invalid source: ${sourceValue}`,
        });
      }

      const normalizedEvent = NormalizationService.normalizeEvent(
        rawEvent,
        sourceValue
      );

      // Type-safe action
      let actionValue: Action | null = null;
      if (normalizedEvent.action) {
        const upperAction = normalizedEvent.action.toUpperCase();
        if (Object.values(Action).includes(upperAction as Action)) {
          actionValue = upperAction as Action;
        }
      }

      const event = await prisma.securityEvent.create({
        data: {
          timestamp: normalizedEvent.timestamp
            ? new Date(normalizedEvent.timestamp)
            : new Date(),
          tenant: normalizedEvent.tenant || user?.tenant || "demoA",
          source: normalizedEvent.source as Source,
          priority: normalizedEvent.priority ?? null,
          vendor: normalizedEvent.vendor || null,
          product: normalizedEvent.product || null,
          eventType: normalizedEvent.eventType || "unknown",
          eventSubtype: normalizedEvent.eventSubtype || null,
          severity: normalizedEvent.severity ?? 0,
          action: actionValue,
          srcIp: normalizedEvent.srcIp || null,
          srcPort: normalizedEvent.srcPort?.toString() || null,
          dstIp: normalizedEvent.dstIp || null,
          dstPort: normalizedEvent.dstPort?.toString() || null,
          protocol: normalizedEvent.protocol || null,
          user: normalizedEvent.user || user?.username || null,
          host: normalizedEvent.host || null,
          process: normalizedEvent.process || null,
          eventId: normalizedEvent.eventId ?? null,
          url: normalizedEvent.url || null,
          httpMethod: normalizedEvent.httpMethod || null,
          statusCode: normalizedEvent.statusCode ?? null,
          ruleName: normalizedEvent.ruleName || null,
          ruleId: normalizedEvent.ruleId || null,
          cloudAccountId: normalizedEvent.cloudAccountId || null,
          cloudRegion: normalizedEvent.cloudRegion || null,
          cloudService: normalizedEvent.cloudService || null,
          sha256: normalizedEvent.sha256 || null,
          status: normalizedEvent.status || null,
          loginType: normalizedEvent.loginType ?? null,
          interface: normalizedEvent.interface || null,
          mac: normalizedEvent.mac || null,
          description: normalizedEvent.description || null,
          ip: normalizedEvent.ip || null,
          raw: normalizedEvent.raw || JSON.parse(JSON.stringify(rawEvent)),
          tags: normalizedEvent.tags || [],
        },
      });

      await alertService.checkAlerts(event);

      await cacheQueue.add(
        "invalidate-log-cache",
        { pattern: "logs:*" },
        { jobId: `invalidate-${Date.now()}`, priority: 1 }
      );

      res.status(201).json({
        success: true,
        eventId: event.id,
      });
    } catch (error) {
      console.error("Error ingesting event:", error);
      res.status(500).json({
        success: false,
        error: "Failed to ingest event",
        message: error instanceof Error ? error.message : "Unknown error",
      });
    }
  },
];

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
    if (tenant && tenant !== "all") {
      filters.tenant = {
        contains: tenant as string,
        mode: "insensitive",
      };
    }
    if (user?.role! === "USER") {
      filters.user = {
        equals: user?.username,
        mode: "insensitive",
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
      orderBy: {
        id: "desc",
      },
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
    const cacheKey = `logs:${JSON.stringify(req.query)}`;
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

export const getDashboardStats = [
  query("tenant")
    .trim()
    .optional()
    .isLength({ min: 2, max: 50 })
    .withMessage("Tenant must be 2-50 characters"),
  query("range")
    .trim()
    .optional()
    .isLength({ min: 2, max: 50 })
    .withMessage("Range must be 2-50 characters"),
  async (req: CustomRequest, res: Response) => {
    try {
      const { tenant, range } = req.query;

      let tenantFilter: any = {};

      if (tenant && tenant !== "all") {
        tenantFilter = tenant;
      } else if (req.user?.role !== "ADMIN") {
        tenantFilter = {
          in: Array.isArray(req?.user?.tenant)
            ? req.user.tenant
            : [req?.user?.tenant],
        };
      } else {
        tenantFilter = undefined;
      }
      console.log(range);

      // Set date range for last 7 days
      const today = new Date();
      const endDate = new Date(
        Date.UTC(
          today.getFullYear(),
          today.getMonth(),
          today.getDate(),
          23,
          59,
          59
        )
      );
      const startDate = new Date(endDate);
      startDate.setDate(
        endDate.getDate() - (range === "1d" ? 1 : range === "3d" ? 3 : 7)
      );
      startDate.setHours(0, 0, 0, 0);

      const dateFilter = {
        gte: startDate,
        lte: endDate,
      };
      const [
        totalEvents,
        topIPs,
        topUsers,
        topEventTypes,
        eventsBySource,
        alertsRuleByDay,
        alertsByDay,
        recentAlert,
      ] = await Promise.all([
        prisma.securityEvent.findMany({
          where: {
            ...(tenantFilter !== undefined ? { tenant: tenantFilter } : {}),
            timestamp: dateFilter,
          },
        }),

        prisma.securityEvent.groupBy({
          by: ["srcIp"],
          where: {
            ...(tenantFilter !== undefined ? { tenant: tenantFilter } : {}),
            timestamp: dateFilter,
            srcIp: { not: null },
          },
          _count: true,
          orderBy: { _count: { srcIp: "desc" } },
        }),

        prisma.securityEvent.groupBy({
          by: ["user"],
          where: {
            ...(tenantFilter !== undefined ? { tenant: tenantFilter } : {}),
            timestamp: dateFilter,
            user: { not: null },
          },
          _count: true,
          orderBy: { _count: { user: "desc" } },
        }),

        prisma.securityEvent.groupBy({
          by: ["eventType"],
          where: {
            ...(tenantFilter !== undefined ? { tenant: tenantFilter } : {}),
            timestamp: dateFilter,
          },
          _count: true,
          orderBy: { _count: { eventType: "desc" } },
        }),

        await prisma.securityEvent.groupBy({
          by: ["tenant", "source", "timestamp"],
          _count: {
            id: true,
          },
          where: {
            ...(tenantFilter !== undefined ? { tenant: tenantFilter } : {}),
            timestamp: dateFilter,
          },
        }),
        await prisma.alertRule.groupBy({
          by: ["tenant", "createdAt"],
          _count: {
            id: true,
          },
          where: {
            ...(tenantFilter !== undefined ? { tenant: tenantFilter } : {}),
            createdAt: dateFilter,
          },
        }),
        await prisma.alert.groupBy({
          by: ["tenant", "triggeredAt"],
          _count: {
            id: true,
          },
          where: {
            ...(tenantFilter !== undefined ? { tenant: tenantFilter } : {}),
            triggeredAt: dateFilter,
          },
        }),
        await prisma.alert.findMany({
          where: {
            ...(tenantFilter !== undefined ? { tenant: tenantFilter } : {}),
          },
          orderBy: { triggeredAt: "desc" },
          take: 5,
        }),
      ]);

      const tenants = await prisma.securityEvent.findMany({
        select: { tenant: true },
        distinct: ["tenant"], // ensures each tenant appears only once
      });
      res.json({
        totalEvents,
        topIPs: topIPs.map((item) => ({ ip: item.srcIp, count: item._count })),
        topUsers: topUsers.map((item) => ({
          user: item.user,
          count: item._count,
        })),
        topEventTypes: topEventTypes.map((item) => ({
          type: item.eventType,
          count: item._count,
        })),
        eventsBySource,
        alertsByDay,
        alertsRuleByDay,
        tenants,
        recentAlert,
      });
    } catch (error) {
      console.error("Error fetching dashboard stats:", error);
      res.status(500).json({ error: "Failed to fetch dashboard stats" });
    }
  },
];

export const deleteLog = [
  param("logId").notEmpty().withMessage("Log ID is required"),
  async (req: CustomRequest, res: Response, next: NextFunction) => {
    try {
      // Validate request body
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
      }

      const { logId } = req.params;

      // Check if user exists
      const existedLog = await getLogById(logId);
      await checkLogIfNotExist(existedLog);

      const existedUser = await getUserById(Number(req.user?.userId));
      await checkUserIfNotExist(existedUser);
      const logOwnerId = existedUser?.id; // or however the log stores the creator
      if (req.user?.role !== "ADMIN" && req.user?.userId !== logOwnerId) {
        return res.status(403).json({ message: "Forbidden: Not authorized" });
      }
      // Delete user
      const logdeletion = await deleteLogById(logId);
      await cacheQueue.add(
        "invalidate-log-cache",
        {
          pattern: "logs:*",
        },
        {
          jobId: `invalidate-${Date.now()}`,
          priority: 1,
        }
      );
      return res.status(200).json({
        success: true,
        message: "Selected log is deleted",
        data: logdeletion,
      });
    } catch (error) {
      console.error("Error deleting log:", error);
      return res.status(500).json({ message: "Internal server error" });
    }
  },
];
