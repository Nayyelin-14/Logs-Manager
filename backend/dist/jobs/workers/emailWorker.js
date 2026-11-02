"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
// workers/emailWorker.ts
const bullmq_1 = require("bullmq");
const redisClient_1 = require("../../config/redisClient");
const emailAction_1 = require("../../actions/emailAction");
// Create a worker that listens to the "otp_email" queue
const emailWorker = new bullmq_1.Worker("email-Queue", async (job) => {
    // job.data should contain { email, otpCode }
    if (job.name === "OtpEmail") {
        const { email, otpCode } = job.data;
        console.log("Sending OTP email");
        const result = await (0, emailAction_1.sendOTPEmail)(email, otpCode);
        if (!result.isSuccess) {
            throw new Error(result.message); // Mark the job as failed in BullMQ
        }
        return result;
    }
    else if (job.name === "AlertEmail") {
        const { email, username, tenant, title, description, severity } = job.data;
        console.log(`📤 Sending an alert mail to ${username} who belongs to ${tenant}`);
        const result = await (0, emailAction_1.sendAlertEmail)(email, username, tenant, title, description, severity);
        if (!result.isSuccess) {
            throw new Error(result.message); // Mark the job as failed in BullMQ
        }
        return result;
    }
}, {
    connection: redisClient_1.redisConnection,
    concurrency: 5, // optional: process up to 5 jobs in parallel
});
// Event listeners
emailWorker.on("completed", (job) => {
    console.log(`Job completed: ${job.id}`);
});
emailWorker.on("failed", (job, err) => {
    if (job) {
        console.error(`Job ${job.id} failed: ${err.message}`);
    }
    else {
        console.error(`Job failed, but job is undefined: ${err.message}`);
    }
});
emailWorker.on("error", (err) => {
    (0, redisClient_1.reportRedisError)("REDIS-EMAIL-WORKER", err);
});
console.log("🚀 Email worker is running...");
//# sourceMappingURL=emailWorker.js.map