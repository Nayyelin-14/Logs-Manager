"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.confirmPassword = void 0;
const jsonwebtoken_1 = __importDefault(require("jsonwebtoken"));
const bcryptjs_1 = __importDefault(require("bcryptjs"));
const express_validator_1 = require("express-validator");
const moment_1 = __importDefault(require("moment/moment"));
const auth_service_1 = require("../../services/auth.service");
const auth_utils_1 = require("../../utils/auth.utils");
const errrorcode_1 = require("../../config/errrorcode");
const PrismaClient_1 = require("../../config/PrismaClient");
exports.confirmPassword = [
    (0, express_validator_1.body)("email")
        .trim()
        .notEmpty()
        .withMessage("Email is required")
        .isEmail()
        .withMessage("Invalid email address"),
    (0, express_validator_1.body)("username")
        .trim()
        .notEmpty()
        .withMessage("Name is required")
        .isLength({ min: 2, max: 50 })
        .withMessage("Name must be between 2 and 50 characters"),
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
    (0, express_validator_1.body)("tenant")
        .trim()
        .notEmpty()
        .withMessage("Tenant is required")
        .isLength({ min: 2, max: 50 })
        .withMessage("Tenant must be 2-50 characters"),
    (0, express_validator_1.body)("token", "Invalid token").trim().notEmpty().escape(),
    async (req, res, next) => {
        const errors = (0, express_validator_1.validationResult)(req).array({ onlyFirstError: true });
        if (errors.length > 0) {
            const error = new Error(errors[0].msg);
            error.status = 400;
            error.code = errrorcode_1.errorCode.invalid;
            return next(error); //This next(error) skips all other routes/middlewares and jumps directly to your error-handling middleware:
        }
        const { password, token, email, username, tenant, confirmPassword } = req.body;
        if (!password ||
            !token ||
            !email ||
            !username ||
            !tenant ||
            !confirmPassword) {
            return res.status(400).json({ error: "Missing required fields" });
        }
        const user = await (0, auth_service_1.getUserByEmail)(email);
        await (0, auth_utils_1.checkUserExist)(user);
        const otpResult = await (0, auth_service_1.getOtpByEmail)(email);
        await (0, auth_utils_1.checkOtpExist)(otpResult);
        if (otpResult.error > 5) {
            const error = new Error("Invalid crendentials");
            error.status = 400;
            error.code = errrorcode_1.errorCode.overLimit;
            return next(error);
        }
        if (otpResult?.verifyToken !== token) {
            //if token is wrong , error and can't be verify again
            const otpData = {
                error: 5,
            };
            await (0, auth_service_1.updateOtp)(otpData, otpResult.id);
            const error = new Error("Invalid Token");
            error.status = 400;
            error.code = errrorcode_1.errorCode.invalid;
            return next(error);
        }
        const isOtpExpired = (0, moment_1.default)().diff(otpResult?.updatedAt, "minutes") > 10; //lek shi a chain nk minute htoke pyy pee 10 mins htk kyee yin expired
        if (isOtpExpired) {
            const error = new Error("Your request is expired. Try again later");
            error.status = 403;
            error.code = errrorcode_1.errorCode.otpExpired;
            return next(error);
        }
        const isPasswordMatch = password === confirmPassword;
        if (!isPasswordMatch) {
            const error = new Error("Passwords do not match");
            error.status = 400;
            error.code = errrorcode_1.errorCode.invalid;
            return next(error);
        }
        const salt = await bcryptjs_1.default.genSalt(10);
        const hashedPassword = await bcryptjs_1.default.hash(password, salt);
        const userData = { email, username, tenant, password: hashedPassword };
        const newUser = await PrismaClient_1.prisma.user.create({
            data: userData,
        });
        const Payload = {
            userId: newUser.id,
            username: newUser.username,
            email: newUser.email,
            tenant: newUser.tenant,
            role: newUser.role,
        };
        const generateAccessToken = jsonwebtoken_1.default.sign(Payload, process.env.ACCESS_TOKEN_SECRET, { expiresIn: 60 * 15 });
        const generateRefreshToken = jsonwebtoken_1.default.sign(Payload, process.env.REFRESH_TOKEN_SECRET, { expiresIn: "30d" });
        const option = {
            httpOnly: true,
            secure: process.env.NODE_ENV === "production",
            sameSite: (process.env.NODE_ENV === "production" ? "none" : "strict"),
        };
        const { password: _storedPassword, ...safeUser } = newUser;
        return res
            .cookie("accessToken", generateAccessToken, {
            ...option,
            maxAge: 15 * 60 * 1000, // 15 minutes
        })
            .cookie("refreshToken", generateRefreshToken, {
            ...option,
            maxAge: 30 * 24 * 60 * 60 * 1000, // 30 days
        })
            .status(201)
            .json({
            message: "Successfully created a new account",
            userId: newUser.id,
            userData: safeUser,
        });
    },
];
//# sourceMappingURL=password.js.map