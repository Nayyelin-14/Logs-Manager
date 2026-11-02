// import { Redis } from "@upstash/redis";
import Redis from "ioredis";
import dotenv from "dotenv";

dotenv.config();
let redisConnection: Redis;
const lastRedisErrorBySource = new Map<string, number>();

export const reportRedisError = (source: string, error: Error) => {
  const now = Date.now();
  const lastReportedAt = lastRedisErrorBySource.get(source) ?? 0;
  if (now - lastReportedAt < 60_000) return;

  lastRedisErrorBySource.set(source, now);
  const code = (error as NodeJS.ErrnoException).code;
  console.error(
    `[${source}] Redis unavailable${code ? ` (${code})` : ""}; retrying with backoff.`
  );
};

const configuredRedisUrl = process.env.REDIS_URL?.trim();

if (configuredRedisUrl) {
  if (/^redis-cli\b/i.test(configuredRedisUrl)) {
    throw new Error(
      "Invalid REDIS_URL: provide only the Redis connection URL (redis:// or rediss://), without redis-cli flags such as --tls or -u."
    );
  }

  let parsedRedisUrl: URL;
  try {
    parsedRedisUrl = new URL(configuredRedisUrl);
  } catch {
    throw new Error("Invalid REDIS_URL: expected a redis:// or rediss:// connection URL.");
  }

  if (
    !["redis:", "rediss:"].includes(parsedRedisUrl.protocol) ||
    !parsedRedisUrl.hostname
  ) {
    throw new Error("Invalid REDIS_URL: expected a redis:// or rediss:// connection URL.");
  }
}

if (configuredRedisUrl) {
  redisConnection = new Redis(configuredRedisUrl, {
    maxRetriesPerRequest: null,
    retryStrategy: (attempt) => Math.min(500 * 2 ** (attempt - 1), 30_000),
  });
} else {
  redisConnection = new Redis({
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
    reportRedisError("Redis", err);
  });
}

export { redisConnection };
