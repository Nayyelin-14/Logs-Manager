"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.deleteUser = exports.updateUserController = void 0;
const express_validator_1 = require("express-validator");
const auth_service_1 = require("../../services/auth.service");
const auth_utils_1 = require("../../utils/auth.utils");
const errrorcode_1 = require("../../config/errrorcode");
const cacheQueue_1 = __importDefault(require("../../jobs/queues/cacheQueue"));
exports.updateUserController = [
    (0, express_validator_1.body)("userId").notEmpty().withMessage("User ID is required").isInt(),
    (0, express_validator_1.body)("username")
        .optional()
        .isString()
        .withMessage("Username must be a string"),
    (0, express_validator_1.body)("email").optional().isEmail().withMessage("Invalid email"),
    (0, express_validator_1.body)("role")
        .optional()
        .isIn(["USER", "ADMIN"])
        .withMessage("Role must be USER or ADMIN"),
    (0, express_validator_1.body)("status")
        .optional()
        .isIn(["FREEZE", "INACTIVE", "ACTIVE"])
        .withMessage("Invalid status"),
    (0, express_validator_1.body)("tenant")
        .trim()
        .notEmpty()
        .withMessage("Tenant is required")
        .isLength({ min: 2, max: 50 })
        .withMessage("Tenant must be 2-50 characters"),
    async (req, res, next) => {
        try {
            // Validate request body
            const errors = (0, express_validator_1.validationResult)(req).array({ onlyFirstError: true });
            if (errors.length > 0) {
                const error = new Error(errors[0].msg);
                error.status = 400;
                error.code = errrorcode_1.errorCode.invalid;
                return next(error); //This next(error) skips all other routes/middlewares and jumps directly to your error-handling middleware:
            }
            // Auth check: only admins
            const currentUser = req.user; // assume you attach currentUser in middleware
            if (!currentUser || currentUser.role !== "ADMIN") {
                return res.status(403).json({ message: "Forbidden: Admins only" });
            }
            const { userId, username, email, role, status, tenant } = req.body;
            // Check if user exists
            const existedUser = await (0, auth_service_1.getUserById)(userId);
            await (0, auth_utils_1.checkUserIfNotExist)(existedUser);
            // Prepare update data
            const updateData = {};
            if (username !== undefined)
                updateData.username = username;
            if (email !== undefined)
                updateData.email = email;
            if (role !== undefined)
                updateData.role = role;
            if (tenant !== undefined)
                updateData.tenant = tenant;
            if (status !== undefined)
                updateData.status = status;
            // Update user
            const updatedUserData = await (0, auth_service_1.updateUser)(updateData, userId);
            return res.status(200).json({
                success: true,
                message: "User updated successfully",
                user: updatedUserData,
            });
        }
        catch (error) {
            console.error("Error updating user:", error);
            return res.status(500).json({ message: "Internal server error" });
        }
    },
];
exports.deleteUser = [
    (0, express_validator_1.param)("userId").notEmpty().withMessage("User ID is required").isInt(),
    async (req, res, next) => {
        try {
            // Validate request body
            const errors = (0, express_validator_1.validationResult)(req);
            if (!errors.isEmpty()) {
                return res.status(400).json({ errors: errors.array() });
            }
            // Auth check: only admins
            if (!req.user || req.user.role !== "ADMIN") {
                return res.status(403).json({ message: "Forbidden: Admins only" });
            }
            const { userId } = req.params;
            // Check if user exists
            const existedUser = await (0, auth_service_1.getUserById)(Number(userId));
            await (0, auth_utils_1.checkUserIfNotExist)(existedUser);
            // Delete user
            const userdeletion = await (0, auth_service_1.deleteUserById)(Number(userId));
            await cacheQueue_1.default.add("invalidate-user-cache", {
                pattern: "users:*",
            }, {
                jobId: `invalidate-${Date.now()}`,
                priority: 1,
            });
            return res
                .status(200)
                .json({ success: true, message: "User deleted", data: userdeletion });
        }
        catch (error) {
            console.error("Error deleting user:", error);
            return res.status(500).json({ message: "Internal server error" });
        }
    },
];
//# sourceMappingURL=manage.user.update.js.map