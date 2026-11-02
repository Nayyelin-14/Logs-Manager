"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.deleteLog = void 0;
const express_validator_1 = require("express-validator");
const auth_service_1 = require("../../services/auth.service");
const auth_utils_1 = require("../../utils/auth.utils");
const logs_service_1 = require("../../services/logs.service");
const cacheQueue_1 = __importDefault(require("../../jobs/queues/cacheQueue"));
exports.deleteLog = [
    (0, express_validator_1.param)("logId").notEmpty().withMessage("Log ID is required"),
    async (req, res, next) => {
        try {
            // Validate request body
            const errors = (0, express_validator_1.validationResult)(req);
            if (!errors.isEmpty()) {
                return res.status(400).json({ errors: errors.array() });
            }
            const { logId } = req.params;
            // Check if user exists
            const existedLog = await (0, logs_service_1.getLogById)(logId);
            await (0, auth_utils_1.checkLogIfNotExist)(existedLog);
            const existedUser = await (0, auth_service_1.getUserById)(Number(req.user?.userId));
            await (0, auth_utils_1.checkUserIfNotExist)(existedUser);
            const ownIdentity = existedUser?.username ?? existedUser?.email ?? "";
            const ownsLog = existedLog?.tenant === existedUser?.tenant &&
                existedLog?.user?.toLowerCase() === ownIdentity.toLowerCase();
            if (req.user?.role !== "ADMIN" && !ownsLog) {
                return res.status(403).json({ message: "Forbidden: Not authorized" });
            }
            // Delete user
            const logdeletion = await (0, logs_service_1.deleteLogById)(logId);
            await cacheQueue_1.default.add("invalidate-log-cache", {
                pattern: "logs:*",
            }, {
                jobId: `invalidate-${Date.now()}`,
                priority: 1,
            });
            return res.status(200).json({
                success: true,
                message: "Selected log is deleted",
                data: logdeletion,
            });
        }
        catch (error) {
            console.error("Error deleting log:", error);
            return res.status(500).json({ message: "Internal server error" });
        }
    },
];
//# sourceMappingURL=logs.delete.js.map