"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.createAlertRule = void 0;
const express_validator_1 = require("express-validator");
const alert_service_1 = require("../../services/alert.service");
const auth_service_1 = require("../../services/auth.service");
const auth_utils_1 = require("../../utils/auth.utils");
const alert_util_1 = require("../../utils/alert.util");
const cacheQueue_1 = __importDefault(require("../../jobs/queues/cacheQueue"));
exports.createAlertRule = [
    // Basic info
    (0, express_validator_1.body)("name").notEmpty().withMessage("Name is required").isString(),
    (0, express_validator_1.body)("tenant").notEmpty().withMessage("Tenant is required").isString(),
    (0, express_validator_1.body)("description").optional().isString(),
    // Conditions array
    (0, express_validator_1.body)("conditions")
        .isArray({ min: 1, max: 1 })
        .withMessage("Conditions must be an array with exactly 1 condition"),
    // Condition fields
    (0, express_validator_1.body)("conditions.*.type")
        .notEmpty()
        .withMessage("Condition type is required")
        .isIn(["event_type", "severity_min", "field_value", "repeated_failures"])
        .withMessage("Unsupported condition type"),
    (0, express_validator_1.body)("conditions.*.field")
        .optional()
        .isIn(["action", "eventType", "severity", "srcIp", "dstIp", "user", "host", "process", "status"])
        .withMessage("Choose a supported event field"),
    (0, express_validator_1.body)("conditions.*.value").optional(),
    (0, express_validator_1.body)("conditions.*.threshold")
        .optional()
        .isInt({ min: 1 })
        .withMessage("Threshold must be a positive integer"),
    (0, express_validator_1.body)("conditions.*.windowSeconds")
        .optional()
        .isInt({ min: 1 })
        .withMessage("WindowSeconds must be a positive integer"),
    // Controller
    async (req, res) => {
        try {
            const errors = (0, express_validator_1.validationResult)(req).array({ onlyFirstError: true });
            if (errors.length) {
                return res.status(400).json({ message: errors[0].msg });
            }
            const { name, description, tenant, conditions } = req.body;
            if (!req.user) {
                return res.status(401).json({ message: "Unauthenticated User" });
            }
            const condition = conditions[0];
            if (((condition.type === "event_type" || condition.type === "severity_min") &&
                (condition.value === undefined || String(condition.value).trim() === "")) ||
                (condition.type === "field_value" &&
                    (!condition.field || condition.value === undefined || String(condition.value).trim() === "")) ||
                (condition.type === "repeated_failures" &&
                    (condition.threshold === undefined ||
                        condition.windowSeconds === undefined))) {
                return res.status(400).json({
                    message: "The selected condition is missing required values.",
                });
            }
            if (condition.type === "severity_min" &&
                (!Number.isInteger(Number(condition.value)) ||
                    Number(condition.value) < 0 ||
                    Number(condition.value) > 10)) {
                return res.status(400).json({ message: "Severity must be between 0 and 10." });
            }
            const { userId } = req.user;
            const user = await (0, auth_service_1.getUserById)(userId);
            await (0, auth_utils_1.checkUserIfNotExist)(user);
            // Check if a rule already exists for this tenant and name
            const existedRule = await (0, alert_service_1.getExistedAlertRule)({ tenant, name });
            await (0, alert_util_1.checkExistedAlertRule)(existedRule);
            const newAlertRule = {
                name,
                description,
                tenant,
                conditions, // exactly one condition
            };
            const createdRule = await (0, alert_service_1.createNewAlertRule)(newAlertRule);
            // Invalidate cache
            await cacheQueue_1.default.add("invalidate-rule-cache", { pattern: "rules:*" }, { jobId: `invalidate-${Date.now()}`, priority: 1 });
            return res
                .status(201)
                .json({ message: "Alert rule is created", createdRule });
        }
        catch (error) {
            const status = error?.status;
            if (status) {
                return res.status(status).json({ message: error.message });
            }
            return res.status(500).json({ message: "Internal server error" });
        }
    },
];
// DELETE ALERT RULE
//# sourceMappingURL=alert.create.js.map