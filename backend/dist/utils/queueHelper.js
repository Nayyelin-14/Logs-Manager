"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.AlertEmailQueue = exports.OtpEmailQueue = void 0;
const emailQueue_1 = __importDefault(require("../jobs/queues/emailQueue"));
const OtpEmailQueue = async (payload) => {
    return await emailQueue_1.default.add("OtpEmail", // job name
    {
        // job data
        email: payload.email,
        otpCode: payload.otp,
    }, {
        // job options
        jobId: `OTP:${payload.otpId}:email`,
        attempts: 3,
        backoff: { type: "exponential", delay: 1000 },
        removeOnComplete: true,
        removeOnFail: 1000,
    });
};
exports.OtpEmailQueue = OtpEmailQueue;
const AlertEmailQueue = async (payload) => {
    return await emailQueue_1.default.add("AlertEmail", {
        email: payload.email,
        username: payload.username,
        tenant: payload.tenant,
        title: payload.title,
        description: payload.description,
        severity: payload.severity,
    }, {
        jobId: `ALERT:${payload.tenant}:${Date.now()}`,
        attempts: 3,
        backoff: { type: "exponential", delay: 1000 },
        removeOnComplete: true,
        removeOnFail: 1000,
    });
};
exports.AlertEmailQueue = AlertEmailQueue;
//# sourceMappingURL=queueHelper.js.map