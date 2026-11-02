"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.listAlerts = void 0;
const express_validator_1 = require("express-validator");
const PrismaClient_1 = require("../../config/PrismaClient");
const auth_service_1 = require("../../services/auth.service");
exports.listAlerts = [
    (0, express_validator_1.query)("tenant").optional().isString().isLength({ max: 100 }),
    (0, express_validator_1.query)("status").optional().isString().isLength({ max: 30 }),
    (0, express_validator_1.query)("severity").optional().isString().isLength({ max: 30 }),
    (0, express_validator_1.query)("search").optional().isString().isLength({ min: 1, max: 100 }),
    (0, express_validator_1.query)("limit").optional().isInt({ min: 1, max: 100 }),
    (0, express_validator_1.query)("cursor").optional().isString().isLength({ min: 1, max: 100 }),
    async (req, res, next) => {
        const errors = (0, express_validator_1.validationResult)(req).array({ onlyFirstError: true });
        if (errors.length)
            return res.status(400).json({ message: errors[0].msg });
        try {
            const user = await (0, auth_service_1.getUserById)(Number(req.user?.userId));
            if (!user)
                return res.status(401).json({ message: "Unauthorized." });
            const where = {};
            if (user.role === "USER")
                where.tenant = user.tenant;
            else if (req.query.tenant && req.query.tenant !== "all")
                where.tenant = String(req.query.tenant);
            if (req.query.status)
                where.status = String(req.query.status).toLowerCase();
            if (req.query.severity)
                where.severity = String(req.query.severity).toLowerCase();
            if (req.query.search)
                where.OR = [
                    { title: { contains: String(req.query.search), mode: "insensitive" } },
                    { description: { contains: String(req.query.search), mode: "insensitive" } },
                    { tenant: { contains: String(req.query.search), mode: "insensitive" } },
                ];
            const limit = Number(req.query.limit ?? 25);
            const rows = await PrismaClient_1.prisma.alert.findMany({
                where,
                take: limit + 1,
                skip: req.query.cursor ? 1 : 0,
                cursor: req.query.cursor ? { id: String(req.query.cursor) } : undefined,
                orderBy: [{ triggeredAt: "desc" }, { id: "desc" }],
                include: { rule: { select: { name: true, description: true } } },
            });
            const hasNextPage = rows.length > limit;
            if (hasNextPage)
                rows.pop();
            return res.status(200).json({ alerts: rows, hasNextPage, newCursor: hasNextPage ? rows.at(-1)?.id ?? null : null });
        }
        catch (error) {
            return next(error);
        }
    },
];
//# sourceMappingURL=alert.query.js.map