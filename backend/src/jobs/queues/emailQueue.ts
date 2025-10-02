import { Queue } from "bullmq";
import { redisConnection } from "../../config/redisClient";

const emailQueue = new Queue("email-Queue", {
  connection: redisConnection,
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

export default emailQueue;
