"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.getDashboardStats = void 0;
const express_validator_1 = require("express-validator");
const PrismaClient_1 = require("../../config/PrismaClient");
exports.getDashboardStats = [
    (0, express_validator_1.query)("tenant")
        .trim()
        .optional()
        .isLength({ min: 2, max: 50 })
        .withMessage("Tenant must be 2-50 characters"),
    (0, express_validator_1.query)("range")
        .trim()
        .optional()
        .isLength({ min: 2, max: 50 })
        .withMessage("Range must be 2-50 characters"),
    async (req, res) => {
        try {
            const { tenant, range } = req.query;
            let tenantFilter = {};
            if (req.user?.role !== "ADMIN") {
                tenantFilter = req.user?.tenant;
            }
            else if (tenant && tenant !== "all") {
                tenantFilter = tenant;
            }
            else {
                tenantFilter = undefined;
            }
            console.log(range);
            // Set date range for last 7 days
            const days = range === "1d" ? 1 : range === "3d" ? 3 : 7;
            const endDate = new Date();
            const startDate = new Date(endDate);
            startDate.setHours(0, 0, 0, 0);
            startDate.setDate(startDate.getDate() - (days - 1));
            const dateFilter = {
                gte: startDate,
                lte: endDate,
            };
            const [totalEvents, topIPs, topUsers, topEventTypes, eventsBySource, alertsRuleByDay, alertsByDay, recentAlert, severityCounts, eventSources, eventsByTenant, alertCountsByStatus, alertCountsBySeverity, ruleCountsByEnabled,] = await Promise.all([
                PrismaClient_1.prisma.securityEvent.count({
                    where: {
                        ...(tenantFilter !== undefined ? { tenant: tenantFilter } : {}),
                        timestamp: dateFilter,
                    },
                }),
                PrismaClient_1.prisma.securityEvent.groupBy({
                    by: ["srcIp"],
                    where: {
                        ...(tenantFilter !== undefined ? { tenant: tenantFilter } : {}),
                        timestamp: dateFilter,
                        srcIp: { not: null },
                    },
                    _count: true,
                    orderBy: { _count: { srcIp: "desc" } },
                }),
                PrismaClient_1.prisma.securityEvent.groupBy({
                    by: ["user"],
                    where: {
                        ...(tenantFilter !== undefined ? { tenant: tenantFilter } : {}),
                        timestamp: dateFilter,
                        user: { not: null },
                    },
                    _count: true,
                    orderBy: { _count: { user: "desc" } },
                }),
                PrismaClient_1.prisma.securityEvent.groupBy({
                    by: ["eventType"],
                    where: {
                        ...(tenantFilter !== undefined ? { tenant: tenantFilter } : {}),
                        timestamp: dateFilter,
                    },
                    _count: true,
                    orderBy: { _count: { eventType: "desc" } },
                }),
                await PrismaClient_1.prisma.securityEvent.groupBy({
                    by: ["tenant", "source", "timestamp"],
                    _count: {
                        id: true,
                    },
                    where: {
                        ...(tenantFilter !== undefined ? { tenant: tenantFilter } : {}),
                        timestamp: dateFilter,
                    },
                }),
                await PrismaClient_1.prisma.alertRule.groupBy({
                    by: ["tenant", "createdAt"],
                    _count: {
                        id: true,
                    },
                    where: {
                        ...(tenantFilter !== undefined ? { tenant: tenantFilter } : {}),
                        createdAt: dateFilter,
                    },
                }),
                await PrismaClient_1.prisma.alert.groupBy({
                    by: ["tenant", "triggeredAt"],
                    _count: {
                        id: true,
                    },
                    where: {
                        ...(tenantFilter !== undefined ? { tenant: tenantFilter } : {}),
                        triggeredAt: dateFilter,
                    },
                }),
                await PrismaClient_1.prisma.alert.findMany({
                    where: {
                        ...(tenantFilter !== undefined ? { tenant: tenantFilter } : {}),
                    },
                    orderBy: { triggeredAt: "desc" },
                    take: 5,
                }),
                PrismaClient_1.prisma.securityEvent.groupBy({
                    by: ["severity"],
                    where: {
                        ...(tenantFilter !== undefined ? { tenant: tenantFilter } : {}),
                        timestamp: dateFilter,
                    },
                    _count: { id: true },
                    orderBy: { severity: "asc" },
                }),
                PrismaClient_1.prisma.securityEvent.groupBy({
                    by: ["source"],
                    where: {
                        ...(tenantFilter !== undefined ? { tenant: tenantFilter } : {}),
                        timestamp: dateFilter,
                    },
                    _count: { id: true },
                    _max: { timestamp: true },
                    orderBy: { _count: { id: "desc" } },
                }),
                PrismaClient_1.prisma.securityEvent.groupBy({
                    by: ["tenant"],
                    where: {
                        ...(tenantFilter !== undefined ? { tenant: tenantFilter } : {}),
                        timestamp: dateFilter,
                    },
                    _count: { id: true },
                    orderBy: { _count: { id: "desc" } },
                    take: 8,
                }),
                PrismaClient_1.prisma.alert.groupBy({
                    by: ["status"],
                    where: {
                        ...(tenantFilter !== undefined ? { tenant: tenantFilter } : {}),
                        triggeredAt: dateFilter,
                    },
                    _count: { id: true },
                }),
                PrismaClient_1.prisma.alert.groupBy({
                    by: ["severity"],
                    where: {
                        ...(tenantFilter !== undefined ? { tenant: tenantFilter } : {}),
                        triggeredAt: dateFilter,
                    },
                    _count: { id: true },
                }),
                PrismaClient_1.prisma.alertRule.groupBy({
                    by: ["enabled"],
                    where: {
                        ...(tenantFilter !== undefined ? { tenant: tenantFilter } : {}),
                    },
                    _count: { id: true },
                }),
            ]);
            const tenants = await PrismaClient_1.prisma.securityEvent.findMany({
                select: { tenant: true },
                distinct: ["tenant"], // ensures each tenant appears only once
            });
            res.json({
                totalEvents,
                topIPs: topIPs.map((item) => ({ ip: item.srcIp, count: item._count })),
                topUsers: topUsers.map((item) => ({
                    user: item.user,
                    count: item._count,
                })),
                topEventTypes: topEventTypes.map((item) => ({
                    type: item.eventType,
                    count: item._count,
                })),
                eventsBySource,
                alertsByDay,
                alertsRuleByDay,
                severityCounts: severityCounts.map((item) => ({
                    severity: item.severity ?? 0,
                    count: item._count.id,
                })),
                sources: eventSources.map((item) => ({
                    source: item.source,
                    _count: item._count.id,
                    latestEventAt: item._max.timestamp,
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
                tenants,
                recentAlert,
            });
        }
        catch (error) {
            console.error("Error fetching dashboard stats:", error);
            res.status(500).json({ error: "Failed to fetch dashboard stats" });
        }
    },
];
//# sourceMappingURL=logs.dashboard.js.map