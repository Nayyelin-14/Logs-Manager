"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.getOrSetCache = void 0;
const redisClient_1 = require("../config/redisClient");
const getOrSetCache = async (cacheKey, cb) => {
    try {
        const cacheData = await redisClient_1.redisConnection.get(cacheKey);
        if (cacheData) {
            return JSON.parse(cacheData);
        }
        const freshData = await cb(); // if there is no cache
        await redisClient_1.redisConnection.setex(cacheKey, 3600, JSON.stringify(freshData));
        return freshData;
    }
    catch (error) {
        console.log("Redis error ", error);
        throw error;
    }
};
exports.getOrSetCache = getOrSetCache;
//# sourceMappingURL=cacheHelper.js.map