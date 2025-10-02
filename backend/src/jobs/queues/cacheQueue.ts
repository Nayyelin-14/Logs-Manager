import { Queue } from "bullmq";
import { redisConnection } from "../../config/redisClient";

const cacheQueue = new Queue("cache-invalidation", {
  connection: redisConnection,
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

export default cacheQueue;
