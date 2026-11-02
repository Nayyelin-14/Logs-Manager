"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.createUser = void 0;
const express_validator_1 = require("express-validator");
const auth_service_1 = require("../../services/auth.service");
const auth_utils_1 = require("../../utils/auth.utils");
const errrorcode_1 = require("../../config/errrorcode");
const errorHandeling_1 = require("../../utils/errorHandeling");
const bcryptjs_1 = __importDefault(require("bcryptjs"));
const cacheQueue_1 = __importDefault(require("../../jobs/queues/cacheQueue"));
exports.createUser = [
    (0, express_validator_1.body)("username")
        .trim()
        .notEmpty()
        .withMessage("Name is required")
        .isLength({ min: 2, max: 50 })
        .withMessage("Name must be between 2 and 50 characters"),
    (0, express_validator_1.body)("role", "Invalid role").isIn(["ADMIN", "USER"]).optional(),
    (0, express_validator_1.body)("email")
        .trim()
        .notEmpty()
        .withMessage("Email is required")
        .isEmail()
        .withMessage("Invalid email address"),
    (0, express_validator_1.body)("tenant")
        .trim()
        .notEmpty()
        .withMessage("Tenant is required")
        .isLength({ min: 2, max: 50 })
        .withMessage("Tenant must be 2-50 characters"),
    (0, express_validator_1.body)("password", "Invalid Credentials")
        .trim()
        .notEmpty()
        .matches(/^[0-9]+$/)
        .isLength({ min: 8, max: 8 }),
    (0, express_validator_1.body)("confirmPassword", "Invalid Credentials")
        .trim()
        .notEmpty()
        .matches(/^[0-9]+$/)
        .isLength({ min: 8, max: 8 }),
    async (req, res, next) => {
        const errors = (0, express_validator_1.validationResult)(req).array({ onlyFirstError: true });
        if (errors.length > 0) {
            return next((0, errorHandeling_1.handleError)(errors[0].msg, 400, errrorcode_1.errorCode.invalid));
        }
        const { email, username, role, tenant, password, confirmPassword } = req.body;
        if (!email || !username || !tenant || !password || !confirmPassword) {
            return res.status(400).json({ message: "All field sare required" });
        }
        const userId = req.user?.userId;
        const user = await (0, auth_service_1.getUserById)(Number(userId));
        await (0, auth_utils_1.checkUserIfNotExist)(user);
        if (user?.role !== "ADMIN") {
            return next((0, errorHandeling_1.handleError)("Unauthorized user detected ", 400, errrorcode_1.errorCode.unauthorized));
        }
        if (password !== confirmPassword) {
            return res.status(400).json({ message: "Passwords do not  match" });
        }
        const hashedPassword = await bcryptjs_1.default.hash(password, 10);
        const newUserData = {
            username,
            email,
            password: hashedPassword,
            tenant,
            role,
        };
        const newUser = await (0, auth_service_1.createNewUser)(newUserData);
        const { password: _storedPassword, ...safeUser } = newUser;
        await cacheQueue_1.default.add("invalidate-post-cache", {
            pattern: "users:*",
        }, {
            jobId: `invalidate-${Date.now()}`,
            priority: 1,
        });
        return res.status(201).json({
            message: "New user created successfully",
            newUser: safeUser,
        });
    },
];
//# sourceMappingURL=manage.user.create.js.map