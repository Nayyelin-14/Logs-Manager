"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const prisma_1 = require("../generated/prisma");
const normalize_1 = require("../utils/normalize");
const source_1 = require("../ingest/source");
const syslog_1 = require("../ingest/syslog");
const batch_1 = require("../ingest/batch");
describe("source aliases", () => {
    it("maps syslog and firewall to FIREWALL", () => {
        expect((0, source_1.normalizeSourceInput)("syslog")).toBe(prisma_1.Source.FIREWALL);
        expect((0, source_1.normalizeSourceInput)("firewall")).toBe(prisma_1.Source.FIREWALL);
        expect((0, source_1.normalizeSourceInput)("FIREWALL")).toBe(prisma_1.Source.FIREWALL);
    });
    it("maps vendor aliases", () => {
        expect((0, source_1.normalizeSourceInput)("cloudtrail")).toBe(prisma_1.Source.AWS);
        expect((0, source_1.normalizeSourceInput)("falcon")).toBe(prisma_1.Source.CROWDSTRIKE);
        expect((0, source_1.normalizeSourceInput)("office365")).toBe(prisma_1.Source.M365);
        expect((0, source_1.normalizeSourceInput)("active_directory")).toBe(prisma_1.Source.AD);
        expect((0, source_1.normalizeSourceInput)("router")).toBe(prisma_1.Source.NETWORK);
    });
    it("returns undefined for unknown sources", () => {
        expect((0, source_1.normalizeSourceInput)("not-a-source")).toBeUndefined();
        expect((0, source_1.normalizeSourceInput)(null)).toBeUndefined();
    });
});
describe("source inference", () => {
    it("infers sources from vendor fields", () => {
        expect((0, source_1.inferSourceFromEvent)({ event_source: "iam.amazonaws.com" })).toBe(prisma_1.Source.AWS);
        expect((0, source_1.inferSourceFromEvent)({ detect_name: "MalwareDetected" })).toBe(prisma_1.Source.CROWDSTRIKE);
        expect((0, source_1.inferSourceFromEvent)({ operation: "UserLoggedIn" })).toBe(prisma_1.Source.M365);
        expect((0, source_1.inferSourceFromEvent)({ event_id: 4625 })).toBe(prisma_1.Source.AD);
        expect((0, source_1.inferSourceFromEvent)({ foo: "bar" })).toBe(prisma_1.Source.API);
    });
});
describe("syslog parsing", () => {
    it("parses RFC3164 priority, host, and key-value fields", () => {
        const parsed = (0, syslog_1.parseSyslogMessage)('<134>Oct 30 22:14:15 fw01 vendor=Fortinet product=FortiGate action=DENY src=10.0.0.5 dst=8.8.8.8 spt=54321 dpt=53 proto=UDP msg="DNS query blocked" policy=block-dns if=wan1 event=traffic mac=00:11:22:33:44:55 reason=policy');
        expect(parsed).not.toBeNull();
        expect(parsed?.priority).toBe(134);
        expect(parsed?.host).toBe("fw01");
        expect(parsed?.vendor).toBe("Fortinet");
        expect(parsed?.action).toBe("DENY");
        expect(parsed?.src).toBe("10.0.0.5");
        expect(parsed?.dst).toBe("8.8.8.8");
        expect(parsed?.spt).toBe("54321");
        expect(parsed?.dpt).toBe("53");
        expect(parsed?.proto).toBe("UDP");
        expect(parsed?.msg).toBe("DNS query blocked");
        expect(parsed?.policy).toBe("block-dns");
        expect(parsed?.event).toBe("traffic");
        expect(parsed?.message).toContain("<134>");
    });
    it("parses RFC5424 messages", () => {
        const parsed = (0, syslog_1.parseSyslogMessage)("<34>1 2026-10-30T22:14:15.003Z host01 app 123 - - event=login user=alice");
        expect(parsed?.priority).toBe(34);
        expect(parsed?.host).toBe("host01");
        expect(parsed?.timestamp).toBe("2026-10-30T22:14:15.003Z");
        expect(parsed?.event).toBe("login");
    });
});
describe("normalization", () => {
    it("normalizes snake_case API fields", () => {
        const event = normalize_1.NormalizationService.normalizeEvent({
            event_type: "login_failed",
            event_subtype: "password",
            src_ip: "10.0.0.5",
            src_port: "1234",
            dst_ip: "10.0.0.6",
            dst_port: "443",
            http_method: "POST",
            status_code: "401",
            rule_name: "bruteforce",
            "@timestamp": "2026-10-30T22:14:15Z",
        }, prisma_1.Source.API);
        expect(event.eventType).toBe("login_failed");
        expect(event.eventSubtype).toBe("password");
        expect(event.srcIp).toBe("10.0.0.5");
        expect(event.srcPort).toBe(1234);
        expect(event.dstIp).toBe("10.0.0.6");
        expect(event.dstPort).toBe(443);
        expect(event.httpMethod).toBe("POST");
        expect(event.statusCode).toBe(401);
        expect(event.ruleName).toBe("bruteforce");
        expect(event.timestamp).toBe("2026-10-30T22:14:15.000Z");
    });
    it("normalizes Syslog firewall fields", () => {
        const event = normalize_1.NormalizationService.normalizeEvent({
            priority: 134,
            timestamp: "2026-10-30T22:14:15Z",
            host: "fw01",
            vendor: "Fortinet",
            product: "FortiGate",
            action: "DENY",
            src: "10.0.0.5",
            dst: "8.8.8.8",
            spt: 54321,
            dpt: 53,
            proto: "UDP",
            msg: "DNS query blocked",
            policy: "block-dns",
            if: "wan1",
            event: "traffic",
            mac: "00:11:22:33:44:55",
        }, prisma_1.Source.FIREWALL);
        expect(event.source).toBe(prisma_1.Source.FIREWALL);
        expect(event.priority).toBe(134);
        expect(event.host).toBe("fw01");
        expect(event.action).toBe("DENY");
        expect(event.srcIp).toBe("10.0.0.5");
        expect(event.dstIp).toBe("8.8.8.8");
        expect(event.srcPort).toBe(54321);
        expect(event.dstPort).toBe(53);
        expect(event.ruleName).toBe("block-dns");
        expect(event.interface).toBe("wan1");
        expect(event.mac).toBe("00:11:22:33:44:55");
        expect(event.description).toBe("DNS query blocked");
    });
    it("normalizes AWS CloudTrail events", () => {
        const event = normalize_1.NormalizationService.normalizeEvent({
            eventName: "CreateUser",
            eventSource: "iam.amazonaws.com",
            eventTime: "2026-10-30T22:17:00Z",
            awsRegion: "us-east-1",
            sourceIPAddress: "203.0.113.10",
            recipientAccountId: "123456789012",
            userIdentity: { userName: "alice", arn: "arn:aws:iam::1:user/alice" },
        }, prisma_1.Source.AWS);
        expect(event.source).toBe(prisma_1.Source.AWS);
        expect(event.eventType).toBe("CreateUser");
        expect(event.user).toBe("alice");
        expect(event.srcIp).toBe("203.0.113.10");
        expect(event.cloudAccountId).toBe("123456789012");
        expect(event.cloudRegion).toBe("us-east-1");
        expect(event.cloudService).toBe("iam.amazonaws.com");
        expect(event.vendor).toBe("aws");
        expect(event.action).toBe("CREATEUSER");
        expect(event.timestamp).toBe("2026-10-30T22:17:00.000Z");
    });
    it("normalizes CrowdStrike detections", () => {
        const event = normalize_1.NormalizationService.normalizeEvent({
            event: {
                DetectName: "MalwareDetected",
                ComputerName: "WIN-ENG-01",
                UserName: "alice",
                FileName: "invoice.exe",
                Severity: 8,
                SHA256String: "abc123",
                SourceIpAddress: "10.0.0.42",
                timestamp: "2026-10-30T22:16:00Z",
            },
        }, prisma_1.Source.CROWDSTRIKE);
        expect(event.source).toBe(prisma_1.Source.CROWDSTRIKE);
        expect(event.eventType).toBe("MalwareDetected");
        expect(event.host).toBe("WIN-ENG-01");
        expect(event.user).toBe("alice");
        expect(event.process).toBe("invoice.exe");
        expect(event.severity).toBe(8);
        expect(event.sha256).toBe("abc123");
        expect(event.srcIp).toBe("10.0.0.42");
        expect(event.vendor).toBe("crowdstrike");
    });
    it("normalizes M365 audit events", () => {
        const event = normalize_1.NormalizationService.normalizeEvent({
            Operation: "UserLoggedIn",
            Workload: "AzureActiveDirectory",
            UserId: "alice@example.com",
            ClientIP: "203.0.113.20",
            ResultStatus: "Success",
            CreationTime: "2026-10-30T22:18:00Z",
        }, prisma_1.Source.M365);
        expect(event.source).toBe(prisma_1.Source.M365);
        expect(event.eventType).toBe("UserLoggedIn");
        expect(event.action).toBe("LOGIN");
        expect(event.user).toBe("alice@example.com");
        expect(event.srcIp).toBe("203.0.113.20");
        expect(event.status).toBe("Success");
        expect(event.product).toBe("AzureActiveDirectory");
        expect(event.vendor).toBe("microsoft");
    });
    it("normalizes AD 4625 events", () => {
        const event = normalize_1.NormalizationService.normalizeEvent({
            EventID: 4625,
            TargetUserName: "alice",
            Computer: "DC01.corp.example.com",
            IpAddress: "10.0.0.77",
            LogonType: 3,
            Status: "0xC000006D",
            TimeCreated: "2026-10-30T22:19:00Z",
        }, prisma_1.Source.AD);
        expect(event.source).toBe(prisma_1.Source.AD);
        expect(event.eventType).toBe("ad_logon_failed");
        expect(event.eventId).toBe(4625);
        expect(event.user).toBe("alice");
        expect(event.host).toBe("DC01.corp.example.com");
        expect(event.srcIp).toBe("10.0.0.77");
        expect(event.loginType).toBe(3);
        expect(event.action).toBe("LOGIN");
        expect(event.severity).toBe(7);
        expect(event.vendor).toBe("microsoft");
        expect(event.product).toBe("active_directory");
    });
    it("normalizes snake_case AD fields", () => {
        const event = normalize_1.NormalizationService.normalizeEvent({
            event_id: "4625",
            target_user_name: "bob",
            computer_name: "DC02",
            ip_address: "10.0.0.80",
            logon_type: "3",
        }, prisma_1.Source.AD);
        expect(event.eventId).toBe(4625);
        expect(event.user).toBe("bob");
        expect(event.host).toBe("DC02");
        expect(event.srcIp).toBe("10.0.0.80");
        expect(event.loginType).toBe(3);
    });
});
describe("batch parsing", () => {
    it("parses a JSON array", () => {
        const events = (0, batch_1.parseBatchBuffer)(Buffer.from(JSON.stringify([{ source: "api" }, { source: "aws" }])), "events.json", "application/json");
        expect(events).toHaveLength(2);
        expect(events[1].source).toBe("aws");
    });
    it("parses JSONL", () => {
        const events = (0, batch_1.parseBatchBuffer)(Buffer.from('{"source":"api"}\n{"source":"ad"}\n'), "events.jsonl", "application/x-ndjson");
        expect(events).toHaveLength(2);
        expect(events[0].source).toBe("api");
    });
    it("parses CSV with quoted fields", () => {
        const events = (0, batch_1.parseBatchBuffer)(Buffer.from('source,event_type,msg\nad,ad_logon_failed,"failed, bad password"\n'), "events.csv", "text/csv");
        expect(events).toHaveLength(1);
        expect(events[0].source).toBe("ad");
        expect(events[0].event_type).toBe("ad_logon_failed");
        expect(events[0].msg).toBe("failed, bad password");
    });
});
//# sourceMappingURL=ingestion.test.js.map