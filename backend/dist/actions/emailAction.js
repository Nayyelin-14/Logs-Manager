"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.sendOTPEmail = sendOTPEmail;
exports.sendAlertEmail = sendAlertEmail;
const nodemailer_1 = require("nodemailer");
const dotenv_1 = __importDefault(require("dotenv"));
const OTP_template_1 = require("../emailTemplates.ts/OTP-template");
const Alert_template_1 = require("../emailTemplates.ts/Alert-template");
dotenv_1.default.config();
async function sendOTPEmail(email, otpCode) {
    try {
        const transporter = (0, nodemailer_1.createTransport)({
            service: "gmail",
            auth: {
                user: process.env.GMAIL_USER,
                pass: process.env.GMAIL_PASS,
            },
        });
        const subject = "Verify One Time Password";
        const message = (0, OTP_template_1.otpEmailHtml)(email, otpCode);
        await transporter.sendMail({
            from: process.env.GMAIL_USER,
            to: email,
            subject,
            html: message,
        });
        console.log("Verification email sent successfully!");
        return {
            isSuccess: true,
            message: "Verification email sent successfully.",
        };
    }
    catch (error) {
        console.error("Error sending verification email:", error);
        return { isSuccess: false, message: "Failed to send verification email." };
    }
}
async function sendAlertEmail(email, username, tenant, title, description, severity) {
    try {
        const transporter = (0, nodemailer_1.createTransport)({
            service: "gmail",
            auth: {
                user: process.env.GMAIL_USER,
                pass: process.env.GMAIL_PASS,
            },
        });
        const subject = `[ALERT] ${title} - Severity: ${severity} at ${tenant}`;
        const message = (0, Alert_template_1.alertEmailHtml)(username, title, description, severity);
        await transporter.sendMail({
            from: process.env.GMAIL_USER,
            to: email,
            subject,
            html: message,
        });
        console.log("Alert email sent successfully!");
        return {
            isSuccess: true,
            message: "Alert email sent successfully.",
        };
    }
    catch (error) {
        console.error("Error sending Alert email:", error);
        return { isSuccess: false, message: "Failed to send Alert email." };
    }
}
//# sourceMappingURL=emailAction.js.map