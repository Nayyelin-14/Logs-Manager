"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.deleteAlertRule = void 0;
const express_validator_1 = require("express-validator");
const alert_service_1 = require("../../services/alert.service");
const auth_service_1 = require("../../services/auth.service");
const auth_utils_1 = require("../../utils/auth.utils");
const cacheQueue_1 = __importDefault(require("../../jobs/queues/cacheQueue"));
const PrismaClient_1 = require("../../config/PrismaClient");
exports.deleteAlertRule = [
    (0, express_validator_1.param)("id", "Rule Id is required.").trim().notEmpty().escape(),
    async (req, res) => {
        try {
            const { id } = req.params;
            if (!id) {
                return res.status(400).json({ message: "Missing AlertRule ID" });
            }
            if (!req.user || req.user.role !== "ADMIN") {
                return res.status(403).json({ message: "Forbidden: Admins only" });
            }
            const { userId } = req.user;
            const user = await (0, auth_service_1.getUserById)(userId);
            await (0, auth_utils_1.checkUserIfNotExist)(user);
            console.log(id);
            const existedRules = await (0, alert_service_1.getExistedAlertRule)({ id });
            const existedRule = existedRules[0];
            if (!existedRule) {
                return res.status(404).json({ message: "AlertRule not found" });
            }
            const alertHistoryCount = await PrismaClient_1.prisma.alert.count({
                where: { ruleId: existedRule.id },
            });
            if (alertHistoryCount > 0) {
                return res.status(409).json({
                    message: "This rule has triggered alerts and cannot be deleted while its alert history is retained.",
                });
            }
            // Delete the alert rule
            await (0, alert_service_1.deleteExistedAlert)(existedRule.id);
            await cacheQueue_1.default.add("invalidate-rule-cache", {
                pattern: "rules:*",
            }, {
                jobId: `invalidate-${Date.now()}`,
                priority: 1,
            });
            return res
                .status(200)
                .json({ message: "AlertRule deleted successfully" });
        }
        catch (error) {
            console.error("Error deleting AlertRule:", error);
            return res.status(500).json({ message: "Internal server error" });
        }
    },
];
//# sourceMappingURL=alert.delete.js.map