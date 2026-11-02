"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const bullmq_1 = require("bullmq");
const redisClient_1 = require("../../config/redisClient");
console.log("cache worker is working");
const cacheWorker = new bullmq_1.Worker("cache-invalidation", async (job) => {
    const { pattern } = job.data;
    console.log(pattern);
    await invalidateCache(pattern);
}, {
    connection: redisClient_1.redisConnection,
    concurrency: 5,
});
cacheWorker.on("completed", (job) => {
    console.log(`Job is completed ${job.id}`);
});
cacheWorker.on("failed", (job, error) => {
    console.log(`Job is  ${job.id} failed  with ${error.message}`);
});
cacheWorker.on("error", (err) => {
    (0, redisClient_1.reportRedisError)("REDIS-CACHE-WORKER", err);
});
const invalidateCache = async (pattern) => {
    try {
        const stream = redisClient_1.redisConnection.scanStream({
            match: pattern,
            count: 100,
        });
        const pipeLine = redisClient_1.redisConnection.pipeline();
        let totalKeys = 0;
        stream.on("data", (keys) => {
            if (keys.length > 0) {
                keys.forEach((key) => {
                    pipeLine.del(key);
                    totalKeys++;
                });
            }
        });
        await new Promise((resolve, reject) => {
            stream.on("end", async () => {
                try {
                    if (totalKeys > 0) {
                        await pipeLine.exec();
                        console.log(`Invalidated ${totalKeys}`);
                    }
                    resolve();
                }
                catch (execError) {
                    console.error(execError);
                    reject(execError);
                }
            });
            stream.on("error", (error) => {
                reject(error);
            });
        });
    }
    catch (error) {
        console.log("Invalidation error", error);
        throw error;
    }
};
//# sourceMappingURL=cacheWorker.js.map