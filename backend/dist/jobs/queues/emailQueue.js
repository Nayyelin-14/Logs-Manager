"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const bullmq_1 = require("bullmq");
const redisClient_1 = require("../../config/redisClient");
const emailQueue = new bullmq_1.Queue("email-Queue", {
    connection: redisClient_1.redisConnection,
    defaultJobOptions: {
        removeOnComplete: true,
        removeOnFail: 5000, // keep failed jobs for debugging
        attempts: 3, // retry 3 times
        backoff: {
            type: "exponential",
            delay: 5000, // wait 5s, then 10s, then 20s...
        },
    },
});
exports.default = emailQueue;
//# sourceMappingURL=emailQueue.js.map