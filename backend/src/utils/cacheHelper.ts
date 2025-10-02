import { redisConnection } from "../config/redisClient";

export const getOrSetCache = async (cacheKey: string, cb: any) => {
  try {
    const cacheData = await redisConnection.get(cacheKey);
    if (cacheData) {
      console.log("cache hit", cacheKey);
      console.log(cacheData);
      return JSON.parse(cacheData);
    }
    console.log("cache missed");
    const freshData = await cb(); // if there is no cache
    await redisConnection.setex(cacheKey, 3600, JSON.stringify(freshData));
    return freshData;
  } catch (error) {
    console.log("Redis error ", error);
    throw error;
  }
};
