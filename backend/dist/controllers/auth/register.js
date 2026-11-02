"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.veridyOtp = exports.registerUser = void 0;
const bcryptjs_1 = __importDefault(require("bcryptjs"));
const express_validator_1 = require("express-validator");
const moment_1 = __importDefault(require("moment/moment"));
const auth_service_1 = require("../../services/auth.service");
const auth_utils_1 = require("../../utils/auth.utils");
const generateOTP_1 = require("../../utils/generateOTP");
const queueHelper_1 = require("../../utils/queueHelper");
const PrismaClient_1 = require("../../config/PrismaClient");
exports.registerUser = [
    (0, express_validator_1.body)("username")
        .trim()
        .notEmpty()
        .withMessage("Name is required")
        .isLength({ min: 2, max: 50 })
        .withMessage("Name must be between 2 and 50 characters"),
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
    async (req, res, next) => {
        const errors = (0, express_validator_1.validationResult)(req).array({ onlyFirstError: true });
        if (errors.length > 0) {
            const error = new Error(errors[0].msg);
            error.status = 400;
            error.code = "Invalid_Error";
            return next(error);
        }
        const { email, tenant, username } = req.body;
        if (!email || !tenant || !username) {
            return res.status(403).json({
                message: "All fields are required",
            });
        }
        const user = await (0, auth_service_1.getUserByEmail)(email);
        await (0, auth_utils_1.checkUserExist)(user);
        //generate OTP function
        const otp = (0, generateOTP_1.generateOTP)();
        //hash otp
        const salt = await bcryptjs_1.default.genSalt(10);
        const hashedOtp = await bcryptjs_1.default.hash(otp.toString(), salt);
        //generate Token function
        const token = (0, generateOTP_1.generateToken)();
        const otpHistory = await (0, auth_service_1.getOtpByEmail)(email);
        let otpResult;
        if (!otpHistory) {
            //store  new  otp data if there is no otp request history
            const otpData = {
                optCode: hashedOtp,
                email,
                rememberToken: token,
                count: 1,
            };
            otpResult = await (0, auth_service_1.storeOtp)(otpData);
            await (0, queueHelper_1.OtpEmailQueue)({
                email: otpResult.email,
                otp,
                otpId: otpResult.id,
            });
        }
        else {
            //if there is otp request history
            //otp is wrong 5 times in one day
            const lastRequestDate = new Date(otpHistory.updatedAt)
                .toISOString()
                .split("T")[0];
            const currentDate = new Date().toISOString().split("T")[0];
            const isSameDate = lastRequestDate === currentDate;
            if (isSameDate && otpHistory.error > 5) {
                return res.status(403).json({
                    message: "OTP is wrong for 5 times. Try again after 24 hours",
                });
            }
            if (!isSameDate) {
                //reset error count and store new otp if not the same date
                const updateotpData = {
                    optCode: hashedOtp,
                    rememberToken: token,
                    count: 1,
                    error: 0,
                };
                otpResult = await (0, auth_service_1.updateOtp)(updateotpData, otpHistory.id);
            }
            else {
                if (otpHistory.count === 3) {
                    const error = new Error("OTP is allowed to request to 3 times per day.Try again later");
                    error.status = 429;
                    error.code = "Exceed_Limit";
                    return next(error);
                }
                else {
                    const updateotpData = {
                        optCode: hashedOtp,
                        rememberToken: token,
                        count: {
                            increment: 1,
                        },
                        error: 0,
                    };
                    otpResult = await (0, auth_service_1.updateOtp)(updateotpData, otpHistory.id);
                }
            }
            await (0, queueHelper_1.OtpEmailQueue)({
                email: otpResult.email,
                otp,
                otpId: otpResult.id,
            });
        }
        return res.status(200).json({
            message: `We are sending otp to ${otpResult.email}`,
            userData: otpResult,
            tenant,
            username,
            token: otpResult.rememberToken,
        });
    },
];
exports.veridyOtp = [
    (0, express_validator_1.body)("username")
        .trim()
        .notEmpty()
        .withMessage("Name is required")
        .isLength({ min: 2, max: 50 })
        .withMessage("Name must be between 2 and 50 characters"),
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
    (0, express_validator_1.body)("otp", "Invalid OTP")
        .trim()
        .notEmpty()
        .matches(/^[0-9]+$/)
        .isLength({ min: 6, max: 6 }),
    (0, express_validator_1.body)("token", "Invalid token").trim().notEmpty().escape(),
    async (req, res, next) => {
        const errors = (0, express_validator_1.validationResult)(req).array({ onlyFirstError: true });
        if (errors.length > 0) {
            const error = new Error(errors[0].msg);
            error.status = 400;
            error.code = "Invalid_Error";
            return next(error);
        }
        const { otp, token, email } = req.body;
        const user = await (0, auth_service_1.getOtpByEmail)(email);
        await (0, auth_utils_1.checkOtpExist)(user);
        //there must have otp to verify
        const existedOtp = await (0, auth_service_1.getOtpByEmail)(user.email);
        await (0, auth_utils_1.checkOtpExist)(existedOtp);
        const lastVerifyDate = new Date(existedOtp.updatedAt)
            .toISOString()
            .split("T")[0];
        const currentDate = new Date().toISOString().split("T")[0];
        const isSameDate = lastVerifyDate === currentDate;
        if (isSameDate && existedOtp.error > 5) {
            return res.status(403).json({
                message: "OTP is wrong for 5 times. Try again after 24 hours",
                isSuccess: false,
            });
        }
        //-------//
        //check token //
        if (existedOtp?.rememberToken !== token) {
            //if token is wrong , error and can't be verify again
            const otpData = {
                error: 5,
            };
            await PrismaClient_1.prisma.otp.update({
                where: { id: existedOtp.id },
                data: otpData,
            });
            const error = new Error("Unauhorized OTP detected");
            error.status = 400;
            error.code = "Error_Invalid";
            return next(error);
        }
        //====//
        //check otp is expired over 2 minutes//
        const isOtpExpired = (0, moment_1.default)().diff(existedOtp?.updatedAt, "minutes") > 2;
        if (isOtpExpired) {
            return res
                .status(403)
                .json({ message: "One time password is expired", isSuccess: false });
        }
        //
        //check otp match or not
        const isOtpMatch = await bcryptjs_1.default.compare(otp, existedOtp.optCode);
        if (!isOtpMatch) {
            const otpData = isSameDate ? { error: { increment: 1 } } : { error: 1 };
            await (0, auth_service_1.updateOtp)(otpData, existedOtp.id);
            return res
                .status(403)
                .json({ message: "One time password is incorrect", isSuccess: false });
        }
        //
        //if everything ok , an otp must have verify token for that account is verified
        const verifiedToken = (0, generateOTP_1.generateToken)();
        const latestOtpData = {
            verifyToken: verifiedToken,
            count: 1,
            error: 0,
        };
        const latestOtpResult = await (0, auth_service_1.updateOtp)(latestOtpData, existedOtp.id);
        //
        return res.json({
            isSuccess: true,
            message: "OTP is successfully verified",
            token: latestOtpResult.verifyToken,
        });
    },
];
//# sourceMappingURL=register.js.map