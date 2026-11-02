import { prisma } from "../config/PrismaClient";

export async function cleanupOldLogs() {
  const sevenDaysAgo = new Date();
  sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);

  const result = await prisma.securityEvent.deleteMany({
    where: {
      timestamp: {
        lt: sevenDaysAgo,
      },
    },
  });

  console.log(`🧹 Deleted ${result.count} logs older than 7 days`);
}
