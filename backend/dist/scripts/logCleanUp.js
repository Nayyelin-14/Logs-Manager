"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.cleanupOldLogs = cleanupOldLogs;
const PrismaClient_1 = require("../config/PrismaClient");
async function cleanupOldLogs() {
    const sevenDaysAgo = new Date();
    sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
    const result = await PrismaClient_1.prisma.securityEvent.deleteMany({
        where: {
            timestamp: {
                lt: sevenDaysAgo,
            },
        },
    });
    console.log(`🧹 Deleted ${result.count} logs older than 7 days`);
}
//# sourceMappingURL=logCleanUp.js.map