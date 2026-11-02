"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.prisma = void 0;
exports.connectWithRetry = connectWithRetry;
require("dotenv/config");
const prisma_1 = require("../generated/prisma");
exports.prisma = new prisma_1.PrismaClient();
async function connectWithRetry(retries = 5, delay = 2000) {
    for (let i = 0; i < retries; i++) {
        try {
            await exports.prisma.$connect();
            console.log(" Database connected successfully!");
            return;
        }
        catch (err) {
            console.warn(` Database connection failed. Retry ${i + 1}/${retries}...`);
            if (i === retries - 1)
                throw err;
            await new Promise((res) => setTimeout(res, delay));
        }
    }
}
//# sourceMappingURL=PrismaClient.js.map