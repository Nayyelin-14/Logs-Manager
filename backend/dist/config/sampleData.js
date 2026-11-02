"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.sample_seed_data = exports.hashedPassword = void 0;
const prisma_1 = require("../generated/prisma");
const bcryptjs_1 = __importDefault(require("bcryptjs"));
// Hashing function
const hashedPassword = async (password) => {
    const salt = await bcryptjs_1.default.genSalt(10);
    const hash = await bcryptjs_1.default.hash(password, salt);
    return hash;
};
exports.hashedPassword = hashedPassword;
// Sample data
exports.sample_seed_data = {
    sampleLogs: [
        {
            timestamp: "2025-08-20T12:44:56Z",
            tenant: "demoA",
            source: prisma_1.Source.FIREWALL,
            vendor: "demo",
            product: "ngfw",
            eventType: "deny",
            severity: 5,
            action: prisma_1.Action.ALERT,
            srcIp: "10.0.1.10",
            dstIp: "8.8.8.8",
            protocol: "udp",
            user: null,
            raw: "<134>Aug 20 12:44:56 fw01 vendor=demo product=ngfw action=deny src=10.0.1.10 dst=8.8.8.8 spt=5353 dpt=53 proto=udp msg=DNS blocked policy=Block-DNS",
        },
        {
            timestamp: "2025-08-20T13:01:02Z",
            tenant: "demoA",
            source: prisma_1.Source.NETWORK,
            eventType: "link-down",
            severity: 3,
            action: prisma_1.Action.ALERT,
            host: "r1",
            raw: "<190>Aug 20 13:01:02 r1 if=ge-0/0/1 event=link-down mac=aa:bb:cc:dd:ee:ff reason=carrier-loss",
        },
        {
            timestamp: "2025-08-20T07:20:00Z",
            tenant: "demoA",
            source: prisma_1.Source.API,
            eventType: "app_login_failed",
            user: "alice",
            srcIp: "203.0.113.7",
            severity: 7,
            action: prisma_1.Action.ALERT,
            raw: '{ "tenant":"demoA", "source":"api", "eventType":"app_login_failed", "user":"alice", "ip":"203.0.113.7", "reason":"wrong_password" }',
        },
        {
            timestamp: "2025-08-20T08:00:00Z",
            tenant: "demoA",
            source: prisma_1.Source.CROWDSTRIKE,
            eventType: "malware_detected",
            host: "WIN10-01",
            process: "powershell.exe",
            severity: 8,
            action: prisma_1.Action.QUARANTINE,
            raw: '{ "tenant":"demoA", "source":"crowdstrike", "eventType":"malware_detected", "host":"WIN10-01", "process":"powershell.exe", "severity":8, "action":"quarantine" }',
        },
        {
            timestamp: "2025-08-20T09:10:00Z",
            tenant: "demoB",
            source: prisma_1.Source.AWS,
            eventType: "CreateUser",
            user: "admin",
            severity: 6,
            action: prisma_1.Action.CREATEUSER,
            raw: '{ "tenant":"demoB", "source":"aws", "eventType":"CreateUser", "user":"admin" }',
        },
        {
            timestamp: "2025-08-20T10:05:00Z",
            tenant: "demoB",
            source: prisma_1.Source.M365,
            eventType: "UserLoggedIn",
            user: "bob@demo.local",
            srcIp: "198.51.100.23",
            severity: 4,
            action: prisma_1.Action.LOGIN,
            raw: '{ "tenant":"demoB", "source":"m365", "eventType":"UserLoggedIn", "user":"bob@demo.local", "status":"Success" }',
        },
    ],
    sampleUsers: [
        {
            username: "Test User",
            email: "testuser@example.com",
            tenant: "TenantA",
            role: prisma_1.Role.USER,
            status: prisma_1.Status.ACTIVE,
        },
        {
            username: "Test Admin",
            email: "testadmin@example.com",
            tenant: "TenantA",
            role: prisma_1.Role.ADMIN,
            status: prisma_1.Status.ACTIVE,
        },
    ],
};
//# sourceMappingURL=sampleData.js.map