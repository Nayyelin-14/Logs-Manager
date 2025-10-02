// import { Redis } from "@upstash/redis";
import Redis from "ioredis";
import dotenv from "dotenv";

dotenv.config();
let redisConnection: Redis;

if (process.env.REDIS_URL) {
  redisConnection = new Redis(process.env.REDIS_URL!, {
    maxRetriesPerRequest: null,
  });
} else {
  redisConnection = new Redis({
    host: process.env.REDIS_HOST,
    port: process.env.REDIS_PORT ? parseInt(process.env.REDIS_PORT) : 6379,
    password: process.env.REDIS_PASSWORD,
    maxRetriesPerRequest: null,
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
    console.error("Redis error:", err);
  });
}

export { redisConnection };
