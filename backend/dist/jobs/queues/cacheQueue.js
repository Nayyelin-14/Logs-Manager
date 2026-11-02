"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const bullmq_1 = require("bullmq");
const redisClient_1 = require("../../config/redisClient");
const cacheQueue = new bullmq_1.Queue("cache-invalidation", {
    connection: redisClient_1.redisConnection,
    defaultJobOptions: {
        attempts: 3,
        backoff: {
            delay: 3000,
            type: "exponential",
        },
        removeOnComplete: true,
        removeOnFail: 1000,
    },
});
exports.default = cacheQueue;
//# sourceMappingURL=cacheQueue.js.map