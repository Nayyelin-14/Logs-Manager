"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.getAllLogs = void 0;
const express_validator_1 = require("express-validator");
const prisma_1 = require("../../generated/prisma");
const auth_service_1 = require("../../services/auth.service");
const auth_utils_1 = require("../../utils/auth.utils");
const errorHandeling_1 = require("../../utils/errorHandeling");
const errrorcode_1 = require("../../config/errrorcode");
const logs_service_1 = require("../../services/logs.service");
const index_types_1 = require("../../types/index.types");
const cacheHelper_1 = require("../../utils/cacheHelper");
exports.getAllLogs = [
    (0, express_validator_1.query)("tenant").optional().isString().withMessage("Tenant must be a string"),
    (0, express_validator_1.query)("source")
        .optional()
        .isIn(Object.values(prisma_1.Source))
        .withMessage(`Source must be one of: ${Object.values(prisma_1.Source).join(", ")}`),
    (0, express_validator_1.query)("action")
        .optional()
        .isIn(Object.values(prisma_1.Action))
        .withMessage(`Action must be one of: ${Object.values(prisma_1.Action).join(", ")}`),
    (0, express_validator_1.query)("severity")
        .optional()
        .isString() // allow "Low", "Medium", "High" from frontend
        .withMessage("Severity must be Low, Medium, or High"),
    (0, express_validator_1.query)("search")
        .optional() // search is optional
        .isString()
        .withMessage("Search must be a string")
        .isLength({ min: 1, max: 100 })
        .withMessage("Search must be between 1 and 100 characters"),
    (0, express_validator_1.query)("limit")
        .optional()
        .isInt({ min: 1 })
        .withMessage("Limit must be a positive integer"),
    (0, express_validator_1.query)("cursor").optional().isString().withMessage("Cursor must be a string"),
    async (req, res, next) => {
        const errors = (0, express_validator_1.validationResult)(req).array({ onlyFirstError: true });
        if (errors.length > 0) {
            return next((0, errorHandeling_1.handleError)(errors[0].msg, 400, errrorcode_1.errorCode.invalid)); //This next(error) skips all other routes/middlewares and jumps directly to your error-handling middleware:
        }
        const { tenant, source, action, severity, date, search } = req.query;
        console.log(tenant, source, action, severity, date, search);
        const userId = req.user?.userId;
        const user = await (0, auth_service_1.getUserById)(Number(userId));
        await (0, auth_utils_1.checkUserIfNotExist)(user);
        const lastCursor = req.query.cursor ? req.query.cursor : undefined;
        const limit = req.query.limit ? Number(req.query.limit) : 5;
        const filters = {};
        if (user?.role === "USER") {
            filters.tenant = user.tenant;
            filters.user = {
                equals: user.username ?? user.email,
                mode: "insensitive",
            };
        }
        else if (tenant && tenant !== "all") {
            filters.tenant = {
                equals: tenant,
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
            const level = index_types_1.severityLevelMap[key];
            console.log(level);
            if (level) {
                filters.severity = { gte: level.min, lte: level.max };
            }
        }
        if (date) {
            const targetDate = new Date(date);
            const nextDay = new Date(targetDate);
            nextDay.setDate(targetDate.getDate() + 1);
            filters.timestamp = {
                gte: targetDate,
                lt: nextDay, // all rows where timestamp falls within that day
            };
        }
        if (search) {
            filters.OR = [
                { user: { contains: search, mode: "insensitive" } },
                { description: { contains: search, mode: "insensitive" } },
                { srcIp: { contains: search, mode: "insensitive" } },
                { eventType: { contains: search, mode: "insensitive" } },
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
        const logs = await (0, cacheHelper_1.getOrSetCache)(cacheKey, async () => {
            return await (0, logs_service_1.getAllLogsListByPagi)(options);
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
//# sourceMappingURL=logs.list.js.map