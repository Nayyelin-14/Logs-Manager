// src/data/sampleData.js

export const sampleDashboardStats = {
  totalLogs: 123456,
  logsLast24Hours: 8765,
  uniqueSources: 7,
  topSources: [
    { name: "firewall", count: 3200 },
    { name: "api", count: 2100 },
    { name: "aws", count: 1500 },
    { name: "m365", count: 900 },
    { name: "ad", count: 700 },
  ],
  topEventTypes: [
    { name: "deny", count: 1800 },
    { name: "app_login_failed", count: 1200 },
    { name: "UserLoggedIn", count: 800 },
    { name: "CreateUser", count: 700 },
    { name: "malware_detected", count: 600 },
  ],
  logTimeline: [
    { timestamp: "2025-08-20T00:00:00Z", count: 500 },
    { timestamp: "2025-08-20T01:00:00Z", count: 600 },
    { timestamp: "2025-08-20T02:00:00Z", count: 750 },
    { timestamp: "2025-08-20T03:00:00Z", count: 820 },
    { timestamp: "2025-08-20T04:00:00Z", count: 910 },
  ],
};
