import { PrismaClient } from "../../generated/prisma";
import { getUserByEmail } from "../../services/auth.service";
import { checkUserIfNotExist } from "../../utils/auth.utils";
import { CustomRequest } from "../../utils/refreshToken";
import { Response } from "express";

const prisma = new PrismaClient();
export const getUserDashboardStats = async (
  req: CustomRequest,
  res: Response
) => {
  try {
    const { email } = req.user || {};

    if (!req.user) return res.status(403).json({ error: "No user found" });
    const user = await getUserByEmail(email!);
    await checkUserIfNotExist(user);

    if (user?.role !== "USER") {
      return res.status(403).json({ error: "Only users allowed" });
    }

    const endDate = new Date();
    endDate.setHours(23, 59, 59, 999);

    const startDate = new Date();
    startDate.setDate(startDate.getDate() - 7);
    startDate.setHours(0, 0, 0, 0);

    const dateFilter = { gte: startDate, lte: endDate };

    const [
      totalEvents,
      topIPs,
      topEventTypes,
      eventsBySource,
      alertsByDay,
      recentAlert,
      sources,
    ] = await Promise.all([
      prisma.securityEvent.findMany({
        where: {
          tenant: user?.tenant!, // strictly tenant from user
          user: user?.username!, // strict username match
          timestamp: dateFilter,
        },
        orderBy: { timestamp: "desc" },
      }),

      prisma.securityEvent.groupBy({
        by: ["srcIp"],
        where: {
          tenant: user?.tenant!, // strictly tenant from user
          user: user?.username!, // strict username match
          timestamp: dateFilter,
          srcIp: { not: null },
        },
        _count: true,
        orderBy: { _count: { srcIp: "desc" } },
      }),

      prisma.securityEvent.groupBy({
        by: ["eventType"],
        where: {
          tenant: user?.tenant!,
          user: user?.username!,
          timestamp: dateFilter,
        },
        _count: true,
        orderBy: { _count: { eventType: "desc" } },
      }),

      prisma.securityEvent.groupBy({
        by: ["tenant", "source", "timestamp"],
        where: {
          tenant: user?.tenant!,
          user: user?.username!,
          timestamp: dateFilter,
        },
        _count: { id: true },
      }),

      prisma.alert.groupBy({
        by: ["tenant", "triggeredAt"],
        where: { tenant: user?.tenant!, triggeredAt: dateFilter },
        _count: { id: true },
      }),

      prisma.alert.findMany({
        where: { tenant: user?.tenant! },
        orderBy: { triggeredAt: "desc" },
        take: 5,
      }),
      prisma.securityEvent.groupBy({
        by: ["source"],
        where: {
          tenant: user?.tenant!,
          user: user?.username!,
          timestamp: dateFilter,
        },
        _count: true,
        orderBy: { _count: { eventType: "desc" } },
      }),
    ]);

    res.json({
      totalEvents,
      topIPs: topIPs.map((item) => ({ ip: item.srcIp, count: item._count })),
      topEventTypes: topEventTypes.map((item) => ({
        type: item.eventType,
        count: item._count,
      })),
      eventsBySource,
      alertsByDay,
      recentAlert,
      sources,
    });
  } catch (error) {
    console.error("Error fetching user dashboard stats:", error);
    res.status(500).json({ error: "Failed to fetch dashboard stats" });
  }
};
