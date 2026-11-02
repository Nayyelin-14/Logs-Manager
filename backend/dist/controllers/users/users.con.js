"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.getUserDashboardStats = void 0;
const auth_service_1 = require("../../services/auth.service");
const auth_utils_1 = require("../../utils/auth.utils");
const PrismaClient_1 = require("../../config/PrismaClient");
const getUserDashboardStats = async (req, res) => {
    try {
        const { email } = req.user || {};
        if (!req.user)
            return res.status(403).json({ error: "No user found" });
        const user = await (0, auth_service_1.getUserByEmail)(email);
        await (0, auth_utils_1.checkUserIfNotExist)(user);
        if (user?.role !== "USER") {
            return res.status(403).json({ error: "Only users allowed" });
        }
        const endDate = new Date();
        const requestedRange = String(req.query.range || "7d");
        const days = requestedRange === "1d" ? 1 : requestedRange === "3d" ? 3 : 7;
        const startDate = new Date(endDate);
        startDate.setHours(0, 0, 0, 0);
        startDate.setDate(startDate.getDate() - (days - 1));
        const dateFilter = { gte: startDate, lte: endDate };
        const [totalEvents, topIPs, topEventTypes, eventsBySource, alertsRuleByDay, alertsByDay, recentAlert, sources, severityCounts, eventsByTenant, alertCountsByStatus, alertCountsBySeverity, ruleCountsByEnabled,] = await Promise.all([
            PrismaClient_1.prisma.securityEvent.count({
                where: {
                    tenant: user?.tenant,
                    user: user?.username ?? user?.email,
                    timestamp: dateFilter,
                },
            }),
            PrismaClient_1.prisma.securityEvent.groupBy({
                by: ["srcIp"],
                where: {
                    tenant: user?.tenant, // strictly tenant from user
                    user: user?.username ?? user?.email,
                    timestamp: dateFilter,
                    srcIp: { not: null },
                },
                _count: true,
                orderBy: { _count: { srcIp: "desc" } },
            }),
            PrismaClient_1.prisma.securityEvent.groupBy({
                by: ["eventType"],
                where: {
                    tenant: user?.tenant,
                    user: user?.username ?? user?.email,
                    timestamp: dateFilter,
                },
                _count: true,
                orderBy: { _count: { eventType: "desc" } },
            }),
            PrismaClient_1.prisma.securityEvent.groupBy({
                by: ["tenant", "source", "timestamp"],
                where: {
                    tenant: user?.tenant,
                    user: user?.username ?? user?.email,
                    timestamp: dateFilter,
                },
                _count: { id: true },
            }),
            PrismaClient_1.prisma.alertRule.groupBy({
                by: ["tenant", "createdAt"],
                where: { tenant: user?.tenant, createdAt: dateFilter },
                _count: { id: true },
            }),
            PrismaClient_1.prisma.alert.groupBy({
                by: ["tenant", "triggeredAt"],
                where: { tenant: user?.tenant, triggeredAt: dateFilter },
                _count: { id: true },
            }),
            PrismaClient_1.prisma.alert.findMany({
                where: { tenant: user?.tenant },
                orderBy: { triggeredAt: "desc" },
                take: 5,
            }),
            PrismaClient_1.prisma.securityEvent.groupBy({
                by: ["source"],
                where: {
                    tenant: user?.tenant,
                    user: user?.username ?? user?.email,
                    timestamp: dateFilter,
                },
                _count: true,
                _max: { timestamp: true },
                orderBy: { _count: { source: "desc" } },
            }),
            PrismaClient_1.prisma.securityEvent.groupBy({
                by: ["severity"],
                where: {
                    tenant: user?.tenant,
                    user: user?.username ?? user?.email,
                    timestamp: dateFilter,
                },
                _count: { id: true },
                orderBy: { severity: "asc" },
            }),
            PrismaClient_1.prisma.securityEvent.groupBy({
                by: ["tenant"],
                where: {
                    tenant: user?.tenant,
                    user: user?.username ?? user?.email,
                    timestamp: dateFilter,
                },
                _count: { id: true },
            }),
            PrismaClient_1.prisma.alert.groupBy({
                by: ["status"],
                where: { tenant: user?.tenant, triggeredAt: dateFilter },
                _count: { id: true },
            }),
            PrismaClient_1.prisma.alert.groupBy({
                by: ["severity"],
                where: { tenant: user?.tenant, triggeredAt: dateFilter },
                _count: { id: true },
            }),
            PrismaClient_1.prisma.alertRule.groupBy({
                by: ["enabled"],
                where: { tenant: user?.tenant },
                _count: { id: true },
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
            alertsRuleByDay,
            alertsByDay,
            recentAlert,
            sources: sources.map((item) => ({
                source: item.source,
                _count: item._count,
                latestEventAt: item._max.timestamp,
            })),
            severityCounts: severityCounts.map((item) => ({
                severity: item.severity ?? 0,
                count: item._count.id,
            })),
            eventsByTenant: eventsByTenant.map((item) => ({
                tenant: item.tenant,
                count: item._count.id,
            })),
            alertCountsByStatus: alertCountsByStatus.map((item) => ({
                status: item.status,
                count: item._count.id,
            })),
            alertCountsBySeverity: alertCountsBySeverity.map((item) => ({
                severity: item.severity,
                count: item._count.id,
            })),
            ruleCountsByEnabled: ruleCountsByEnabled.map((item) => ({
                enabled: item.enabled,
                count: item._count.id,
            })),
        });
    }
    catch (error) {
        console.error("Error fetching user dashboard stats:", error);
        res.status(500).json({ error: "Failed to fetch dashboard stats" });
    }
};
exports.getUserDashboardStats = getUserDashboardStats;
//# sourceMappingURL=users.con.js.map