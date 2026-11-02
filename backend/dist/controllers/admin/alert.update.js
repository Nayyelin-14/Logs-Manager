"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.setAlertRuleEnabled = exports.updateAlertRule = void 0;
const express_validator_1 = require("express-validator");
const PrismaClient_1 = require("../../config/PrismaClient");
const cacheQueue_1 = __importDefault(require("../../jobs/queues/cacheQueue"));
const alert_service_1 = require("../../services/alert.service");
const invalidateRules = async () => {
    await cacheQueue_1.default.add("invalidate-rule-cache", { pattern: "rules:*" }, { jobId: `invalidate-${Date.now()}`, priority: 1 });
};
const validateRuleFields = [
    (0, express_validator_1.body)("name").trim().notEmpty().isLength({ max: 100 }),
    (0, express_validator_1.body)("tenant").trim().notEmpty().isLength({ min: 2, max: 50 }),
    (0, express_validator_1.body)("description").optional().isString(),
    (0, express_validator_1.body)("conditions").isArray({ min: 1, max: 1 }),
    (0, express_validator_1.body)("conditions.*.type").isIn([
        "event_type",
        "severity_min",
        "field_value",
        "repeated_failures",
    ]),
    (0, express_validator_1.body)("conditions.*.field")
        .optional()
        .isIn(["action", "eventType", "severity", "srcIp", "dstIp", "user", "host", "process", "status"]),
    (0, express_validator_1.body)("conditions.*.value").optional(),
    (0, express_validator_1.body)("conditions.*.threshold").optional().isInt({ min: 1 }),
    (0, express_validator_1.body)("conditions.*.windowSeconds").optional().isInt({ min: 1 }),
];
exports.updateAlertRule = [
    (0, express_validator_1.param)("id").isString().notEmpty(),
    ...validateRuleFields,
    async (req, res) => {
        const errors = (0, express_validator_1.validationResult)(req).array({ onlyFirstError: true });
        if (errors.length) {
            return res.status(400).json({ message: errors[0].msg });
        }
        const existing = await PrismaClient_1.prisma.alertRule.findUnique({
            where: { id: req.params.id },
        });
        if (!existing)
            return res.status(404).json({ message: "Rule not found." });
        const { name, description, tenant, conditions } = req.body;
        const duplicateRule = await (0, alert_service_1.duplicate)(tenant, name, req.params.id);
        if (duplicateRule) {
            return res.status(409).json({ message: "A rule with this name already exists in that tenant." });
        }
        const condition = conditions[0];
        if (((condition.type === "event_type" || condition.type === "severity_min") &&
            (condition.value === undefined || String(condition.value).trim() === "")) ||
            (condition.type === "field_value" &&
                (!condition.field || condition.value === undefined || String(condition.value).trim() === "")) ||
            (condition.type === "repeated_failures" &&
                (condition.threshold === undefined || condition.windowSeconds === undefined))) {
            return res.status(400).json({ message: "The selected condition is missing required values." });
        }
        if (condition.type === "severity_min" &&
            (!Number.isInteger(Number(condition.value)) ||
                Number(condition.value) < 0 ||
                Number(condition.value) > 10)) {
            return res.status(400).json({ message: "Severity must be between 0 and 10." });
        }
        const rule = await (0, alert_service_1.updateAlertRuleById)({ name, description, tenant, conditions }, req.params.id);
        await invalidateRules();
        return res.status(200).json({ message: "Alert rule updated.", rule });
    },
];
exports.setAlertRuleEnabled = [
    (0, express_validator_1.param)("id").isString().notEmpty(),
    (0, express_validator_1.body)("enabled").isBoolean(),
    async (req, res) => {
        const errors = (0, express_validator_1.validationResult)(req).array({ onlyFirstError: true });
        if (errors.length) {
            return res.status(400).json({ message: errors[0].msg });
        }
        const exists = await PrismaClient_1.prisma.alertRule.findUnique({
            where: { id: req.params.id },
            select: { id: true },
        });
        if (!exists)
            return res.status(404).json({ message: "Rule not found." });
        const rule = await PrismaClient_1.prisma.alertRule.update({
            where: { id: req.params.id },
            data: { enabled: req.body.enabled },
        });
        await invalidateRules();
        return res.status(200).json({
            message: `Rule ${rule.enabled ? "enabled" : "disabled"}.`,
            rule,
        });
    },
];
//# sourceMappingURL=alert.update.js.map