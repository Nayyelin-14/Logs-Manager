import { Worker } from "bullmq";
import { redisConnection } from "../../config/redisClient";
console.log("cache worker is working");
const cacheWorker = new Worker(
  "cache-invalidation",
  async (job) => {
    const { pattern } = job.data;
    console.log(pattern);
    await invalidateCache(pattern);
  },
  {
    connection: redisConnection,
    concurrency: 5,
  }
);

cacheWorker.on("completed", (job) => {
  console.log(`Job is completed ${job!.id}`);
});

cacheWorker.on("failed", (job, error) => {
  console.log(`Job is  ${job!.id} failed  with ${error.message}`);
});

const invalidateCache = async (pattern: string) => {
  try {
    const stream = redisConnection.scanStream({
      match: pattern,
      count: 100,
    });

    const pipeLine = redisConnection.pipeline();

    let totalKeys = 0;

    stream.on("data", (keys: string[]) => {
      if (keys.length > 0) {
        keys.forEach((key) => {
          pipeLine.del(key);
          totalKeys++;
        });
      }
    });

    await new Promise<void>((resolve, reject) => {
      stream.on("end", async () => {
        try {
          if (totalKeys > 0) {
            await pipeLine.exec();
            console.log(`Invalidated ${totalKeys}`);
          }
          resolve();
        } catch (execError) {
          console.error(execError);
          reject(execError);
        }
      });

      stream.on("error", (error) => {
        reject(error);
      });
    });
  } catch (error) {
    console.log("Invalidation error", error);
    throw error;
  }
};
