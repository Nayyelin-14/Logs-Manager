"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.getAllDataCount = exports.getAllUsers = void 0;
const express_validator_1 = require("express-validator");
const auth_service_1 = require("../../services/auth.service");
const auth_utils_1 = require("../../utils/auth.utils");
const errrorcode_1 = require("../../config/errrorcode");
const errorHandeling_1 = require("../../utils/errorHandeling");
const PrismaClient_1 = require("../../config/PrismaClient");
const cacheHelper_1 = require("../../utils/cacheHelper");
exports.getAllUsers = [
    (0, express_validator_1.query)("cursor", "Cursor number must be post id").isInt({ gt: 0 }).optional(),
    (0, express_validator_1.query)("limit", "Limit number must be unsigned integer"),
    // 🔹 Role filter
    (0, express_validator_1.query)("role", "Invalid role").isIn(["ADMIN", "USER"]).optional(),
    (0, express_validator_1.query)("search")
        .optional() // search is optional
        .isString()
        .withMessage("Search must be a string")
        .isLength({ min: 1, max: 100 })
        .withMessage("Search must be between 1 and 100 characters"),
    // 🔹 Status filter
    (0, express_validator_1.query)("status", "Invalid status")
        .isIn(["ACTIVE", "INACTIVE", "FREEZE", "all"])
        .optional(),
    (0, express_validator_1.query)("tenant").optional().isString().withMessage("Tenant must be a string"),
    // 🔹 Date filter (ISO string)
    (0, express_validator_1.query)("date", "Invalid  date").isISO8601().toDate().optional(),
    async (req, res, next) => {
        const errors = (0, express_validator_1.validationResult)(req).array({ onlyFirstError: true });
        if (errors.length > 0) {
            return next((0, errorHandeling_1.handleError)(errors[0].msg, 400, errrorcode_1.errorCode.invalid)); //This next(error) skips all other routes/middlewares and jumps directly to your error-handling middleware:
        }
        const { role, status, date, search, tenant } = req.query;
        const userId = req.user?.userId;
        const user = await (0, auth_service_1.getUserById)(Number(userId));
        await (0, auth_utils_1.checkUserIfNotExist)(user);
        const lastCursor = req.query.cursor ? Number(req.query.cursor) : undefined;
        const limit = req.query.limit ? Number(req.query.limit) : 5;
        const filters = {};
        if (role) {
            filters.role = role;
        }
        if (tenant && tenant !== "all") {
            filters.tenant = tenant;
        }
        if (status) {
            filters.status = status;
        }
        if (date) {
            const targetDate = new Date(date);
            const nextDay = new Date(targetDate);
            nextDay.setDate(targetDate.getDate() + 1);
            filters.createAt = {
                gte: targetDate,
                lt: nextDay, // strictly less than next day = exact date
            };
        }
        if (search) {
            filters.OR = [
                { username: { contains: search, mode: "insensitive" } },
                { email: { contains: search, mode: "insensitive" } },
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
        const usersList = await (0, cacheHelper_1.getOrSetCache)(cacheKey, async () => {
            return await (0, auth_service_1.getAllUserListByPagi)(options);
        });
        const hasNextPage = usersList.length > limit;
        if (hasNextPage) {
            usersList.pop();
        }
        const newCursor = usersList.length > 0 ? usersList[usersList.length - 1].id : null;
        res.status(200).json({
            usersList,
            hasNextPage,
            newCursor,
        });
    },
];
exports.getAllDataCount = [
    (0, express_validator_1.query)("tenant", "Invalid Tenant.").trim().escape().optional(),
    async (req, res, next) => {
        const errors = (0, express_validator_1.validationResult)(req).array({ onlyFirstError: true });
        if (errors.length > 0) {
            return next((0, errorHandeling_1.handleError)(errors[0].msg, 400, errrorcode_1.errorCode.invalid));
        }
        const { tenant } = req.query;
        // Build filter only if tenant exists and is not "all"
        const tenantFilter = tenant && tenant !== "all"
            ? {
                tenant: tenant,
            }
            : {};
        // Get counts for multiple tables
        const [allLogs, allUsers, allAlerts, allRules] = await Promise.all([
            PrismaClient_1.prisma.securityEvent.count({ where: tenantFilter }),
            PrismaClient_1.prisma.user.count({ where: tenantFilter }),
            PrismaClient_1.prisma.alert.count({ where: tenantFilter }),
            PrismaClient_1.prisma.alertRule.count({ where: tenantFilter }),
        ]);
        const tenants = await PrismaClient_1.prisma.user.findMany({
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
//# sourceMappingURL=manage.user.query.js.map