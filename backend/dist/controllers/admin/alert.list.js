"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.getAllAlertRule = void 0;
const express_validator_1 = require("express-validator");
const alert_service_1 = require("../../services/alert.service");
const auth_service_1 = require("../../services/auth.service");
const auth_utils_1 = require("../../utils/auth.utils");
const errorHandeling_1 = require("../../utils/errorHandeling");
const errrorcode_1 = require("../../config/errrorcode");
const cacheHelper_1 = require("../../utils/cacheHelper");
exports.getAllAlertRule = [
    (0, express_validator_1.query)("date", "Invalid date").isISO8601().toDate().optional(),
    (0, express_validator_1.query)("search")
        .optional()
        .isString()
        .withMessage("Search must be a string")
        .isLength({ min: 1, max: 100 })
        .withMessage("Search must be between 1 and 100 characters"),
    (0, express_validator_1.query)("limit")
        .optional()
        .isInt({ min: 1 })
        .withMessage("Limit must be a positive integer"),
    (0, express_validator_1.query)("tenant").optional().isString().withMessage("Tenant must be a string"),
    (0, express_validator_1.query)("cursor").optional().isString().withMessage("Cursor must be a string"),
    async (req, res, next) => {
        const errors = (0, express_validator_1.validationResult)(req).array({ onlyFirstError: true });
        if (errors.length > 0) {
            return next((0, errorHandeling_1.handleError)(errors[0].msg, 400, errrorcode_1.errorCode.invalid));
        }
        const { date, search, tenant } = req.query;
        const userId = req.user?.userId;
        const user = await (0, auth_service_1.getUserById)(Number(userId));
        await (0, auth_utils_1.checkUserIfNotExist)(user);
        const lastCursor = req.query.cursor ? req.query.cursor : undefined;
        const limit = req.query.limit ? Number(req.query.limit) : 5;
        const filters = {};
        if (tenant && tenant !== "all") {
            filters.tenant = { equals: tenant };
        }
        if (date) {
            const targetDate = new Date(date);
            const nextDay = new Date(targetDate);
            nextDay.setDate(targetDate.getDate() + 1);
            filters.createdAt = { gte: targetDate, lt: nextDay };
        }
        if (search) {
            filters.OR = [
                { name: { contains: search, mode: "insensitive" } },
                { description: { contains: search, mode: "insensitive" } },
                { tenant: { contains: search, mode: "insensitive" } },
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
        const rules = await (0, cacheHelper_1.getOrSetCache)(cacheKey, async () => {
            return await (0, alert_service_1.getAllRules)(options);
        });
        const hasNextPage = rules.length > limit;
        if (hasNextPage)
            rules.pop();
        const newCursor = hasNextPage ? rules[rules.length - 1].id : null;
        res.status(200).json({
            rules,
            hasNextPage,
            newCursor,
        });
    },
];
//# sourceMappingURL=alert.list.js.map