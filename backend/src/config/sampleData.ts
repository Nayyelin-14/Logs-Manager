import { Source, Action, Status, Role } from "../generated/prisma";
import bcrypt from "bcryptjs";

// Hashing function
export const hashedPassword = async (password: string) => {
  const salt = await bcrypt.genSalt(10);
  const hash = await bcrypt.hash(password, salt);
  return hash;
};

// Sample data
export const sample_seed_data = {
  sampleLogs: [
    {
      timestamp: "2025-08-20T12:44:56Z",
      tenant: "demoA",
      source: Source.FIREWALL,
      vendor: "demo",
      product: "ngfw",
      eventType: "deny",
      severity: 5,
      action: Action.ALERT,
      srcIp: "10.0.1.10",
      dstIp: "8.8.8.8",
      protocol: "udp",
      user: null,
      raw: "<134>Aug 20 12:44:56 fw01 vendor=demo product=ngfw action=deny src=10.0.1.10 dst=8.8.8.8 spt=5353 dpt=53 proto=udp msg=DNS blocked policy=Block-DNS",
    },
    {
      timestamp: "2025-08-20T13:01:02Z",
      tenant: "demoA",
      source: Source.NETWORK,
      eventType: "link-down",
      severity: 3,
      action: Action.ALERT,
      host: "r1",
      raw: "<190>Aug 20 13:01:02 r1 if=ge-0/0/1 event=link-down mac=aa:bb:cc:dd:ee:ff reason=carrier-loss",
    },
    {
      timestamp: "2025-08-20T07:20:00Z",
      tenant: "demoA",
      source: Source.API,
      eventType: "app_login_failed",
      user: "alice",
      srcIp: "203.0.113.7",
      severity: 7,
      action: Action.ALERT,
      raw: '{ "tenant":"demoA", "source":"api", "eventType":"app_login_failed", "user":"alice", "ip":"203.0.113.7", "reason":"wrong_password" }',
    },
    {
      timestamp: "2025-08-20T08:00:00Z",
      tenant: "demoA",
      source: Source.CROWDSTRIKE,
      eventType: "malware_detected",
      host: "WIN10-01",
      process: "powershell.exe",
      severity: 8,
      action: Action.QUARANTINE,
      raw: '{ "tenant":"demoA", "source":"crowdstrike", "eventType":"malware_detected", "host":"WIN10-01", "process":"powershell.exe", "severity":8, "action":"quarantine" }',
    },
    {
      timestamp: "2025-08-20T09:10:00Z",
      tenant: "demoB",
      source: Source.AWS,
      eventType: "CreateUser",
      user: "admin",
      severity: 6,
      action: Action.CREATEUSER,
      raw: '{ "tenant":"demoB", "source":"aws", "eventType":"CreateUser", "user":"admin" }',
    },
    {
      timestamp: "2025-08-20T10:05:00Z",
      tenant: "demoB",
      source: Source.M365,
      eventType: "UserLoggedIn",
      user: "bob@demo.local",
      srcIp: "198.51.100.23",
      severity: 4,
      action: Action.LOGIN,
      raw: '{ "tenant":"demoB", "source":"m365", "eventType":"UserLoggedIn", "user":"bob@demo.local", "status":"Success" }',
    },
  ],

  sampleUsers: [
    {
      username: "Test User",
      email: "testuser@example.com",
      tenant: "TenantA",
      role: Role.USER,
      status: Status.ACTIVE,
    },
    {
      username: "Test Admin",
      email: "testadmin@example.com",
      tenant: "TenantA",
      role: Role.ADMIN,
      status: Status.ACTIVE,
    },
  ],
};
