"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.updateAlertStatus = void 0;
const express_validator_1 = require("express-validator");
const PrismaClient_1 = require("../../config/PrismaClient");
exports.updateAlertStatus = [
    (0, express_validator_1.param)("id").isString().notEmpty(),
    (0, express_validator_1.body)("status").isIn(["open", "resolved"]),
    async (req, res) => {
        const errors = (0, express_validator_1.validationResult)(req).array({ onlyFirstError: true });
        if (errors.length) {
            return res.status(400).json({ message: errors[0].msg });
        }
        try {
            const existing = await PrismaClient_1.prisma.alert.findUnique({
                where: { id: req.params.id },
                select: { id: true },
            });
            if (!existing) {
                return res.status(404).json({ message: "Alert not found." });
            }
            const alert = await PrismaClient_1.prisma.alert.update({
                where: { id: req.params.id },
                data: { status: req.body.status },
            });
            return res.status(200).json({ message: "Alert status updated.", alert });
        }
        catch (error) {
            return res.status(500).json({ message: "Could not update alert status." });
        }
    },
];
//# sourceMappingURL=alert.status.js.map