"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.redisConnection = exports.reportRedisError = void 0;
// import { Redis } from "@upstash/redis";
const ioredis_1 = __importDefault(require("ioredis"));
const dotenv_1 = __importDefault(require("dotenv"));
dotenv_1.default.config();
let redisConnection;
const lastRedisErrorBySource = new Map();
const reportRedisError = (source, error) => {
    const now = Date.now();
    const lastReportedAt = lastRedisErrorBySource.get(source) ?? 0;
    if (now - lastReportedAt < 60_000)
        return;
    lastRedisErrorBySource.set(source, now);
    const code = error.code;
    console.error(`[${source}] Redis unavailable${code ? ` (${code})` : ""}; retrying with backoff.`);
};
exports.reportRedisError = reportRedisError;
const configuredRedisUrl = process.env.REDIS_URL?.trim();
if (configuredRedisUrl) {
    if (/^redis-cli\b/i.test(configuredRedisUrl)) {
        throw new Error("Invalid REDIS_URL: provide only the Redis connection URL (redis:// or rediss://), without redis-cli flags such as --tls or -u.");
    }
    let parsedRedisUrl;
    try {
        parsedRedisUrl = new URL(configuredRedisUrl);
    }
    catch {
        throw new Error("Invalid REDIS_URL: expected a redis:// or rediss:// connection URL.");
    }
    if (!["redis:", "rediss:"].includes(parsedRedisUrl.protocol) ||
        !parsedRedisUrl.hostname) {
        throw new Error("Invalid REDIS_URL: expected a redis:// or rediss:// connection URL.");
    }
}
if (configuredRedisUrl) {
    exports.redisConnection = redisConnection = new ioredis_1.default(configuredRedisUrl, {
        maxRetriesPerRequest: null,
        retryStrategy: (attempt) => Math.min(500 * 2 ** (attempt - 1), 30_000),
    });
}
else {
    exports.redisConnection = redisConnection = new ioredis_1.default({
        host: process.env.REDIS_HOST,
        port: process.env.REDIS_PORT ? parseInt(process.env.REDIS_PORT) : 6379,
        password: process.env.REDIS_PASSWORD,
        maxRetriesPerRequest: null,
        tls: {},
        retryStrategy: (attempt) => Math.min(500 * 2 ** (attempt - 1), 30_000),
    });
}
if (process.env.NODE_ENV !== "test") {
    redisConnection.on("connect", () => {
        console.log("Redis connected successfully");
    });
    redisConnection.on("ready", () => {
        console.log("Redis ready");
    });
    redisConnection.on("error", (err) => {
        (0, exports.reportRedisError)("Redis", err);
    });
}
//# sourceMappingURL=redisClient.js.map