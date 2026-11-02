import { Source } from "../generated/prisma";
import { NormalizationService } from "../utils/normalize";
import {
  inferSourceFromEvent,
  normalizeSourceInput,
} from "../ingest/source";
import { parseSyslogMessage } from "../ingest/syslog";
import { parseBatchBuffer } from "../ingest/batch";

describe("source aliases", () => {
  it("maps syslog and firewall to FIREWALL", () => {
    expect(normalizeSourceInput("syslog")).toBe(Source.FIREWALL);
    expect(normalizeSourceInput("firewall")).toBe(Source.FIREWALL);
    expect(normalizeSourceInput("FIREWALL")).toBe(Source.FIREWALL);
  });

  it("maps vendor aliases", () => {
    expect(normalizeSourceInput("cloudtrail")).toBe(Source.AWS);
    expect(normalizeSourceInput("falcon")).toBe(Source.CROWDSTRIKE);
    expect(normalizeSourceInput("office365")).toBe(Source.M365);
    expect(normalizeSourceInput("active_directory")).toBe(Source.AD);
    expect(normalizeSourceInput("router")).toBe(Source.NETWORK);
  });

  it("returns undefined for unknown sources", () => {
    expect(normalizeSourceInput("not-a-source")).toBeUndefined();
    expect(normalizeSourceInput(null)).toBeUndefined();
  });
});

describe("source inference", () => {
  it("infers sources from vendor fields", () => {
    expect(inferSourceFromEvent({ event_source: "iam.amazonaws.com" })).toBe(
      Source.AWS
    );
    expect(inferSourceFromEvent({ detect_name: "MalwareDetected" })).toBe(
      Source.CROWDSTRIKE
    );
    expect(inferSourceFromEvent({ operation: "UserLoggedIn" })).toBe(
      Source.M365
    );
    expect(inferSourceFromEvent({ event_id: 4625 })).toBe(Source.AD);
    expect(inferSourceFromEvent({ foo: "bar" })).toBe(Source.API);
  });
});

describe("syslog parsing", () => {
  it("parses RFC3164 priority, host, and key-value fields", () => {
    const parsed = parseSyslogMessage(
      '<134>Oct 30 22:14:15 fw01 vendor=Fortinet product=FortiGate action=DENY src=10.0.0.5 dst=8.8.8.8 spt=54321 dpt=53 proto=UDP msg="DNS query blocked" policy=block-dns if=wan1 event=traffic mac=00:11:22:33:44:55 reason=policy'
    );

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
    const parsed = parseSyslogMessage(
      "<34>1 2026-10-30T22:14:15.003Z host01 app 123 - - event=login user=alice"
    );

    expect(parsed?.priority).toBe(34);
    expect(parsed?.host).toBe("host01");
    expect(parsed?.timestamp).toBe("2026-10-30T22:14:15.003Z");
    expect(parsed?.event).toBe("login");
  });
});

describe("normalization", () => {
  it("normalizes snake_case API fields", () => {
    const event = NormalizationService.normalizeEvent(
      {
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
      },
      Source.API
    );

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
    const event = NormalizationService.normalizeEvent(
      {
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
      },
      Source.FIREWALL
    );

    expect(event.source).toBe(Source.FIREWALL);
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
    const event = NormalizationService.normalizeEvent(
      {
        eventName: "CreateUser",
        eventSource: "iam.amazonaws.com",
        eventTime: "2026-10-30T22:17:00Z",
        awsRegion: "us-east-1",
        sourceIPAddress: "203.0.113.10",
        recipientAccountId: "123456789012",
        userIdentity: { userName: "alice", arn: "arn:aws:iam::1:user/alice" },
      },
      Source.AWS
    );

    expect(event.source).toBe(Source.AWS);
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
    const event = NormalizationService.normalizeEvent(
      {
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
      },
      Source.CROWDSTRIKE
    );

    expect(event.source).toBe(Source.CROWDSTRIKE);
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
    const event = NormalizationService.normalizeEvent(
      {
        Operation: "UserLoggedIn",
        Workload: "AzureActiveDirectory",
        UserId: "alice@example.com",
        ClientIP: "203.0.113.20",
        ResultStatus: "Success",
        CreationTime: "2026-10-30T22:18:00Z",
      },
      Source.M365
    );

    expect(event.source).toBe(Source.M365);
    expect(event.eventType).toBe("UserLoggedIn");
    expect(event.action).toBe("LOGIN");
    expect(event.user).toBe("alice@example.com");
    expect(event.srcIp).toBe("203.0.113.20");
    expect(event.status).toBe("Success");
    expect(event.product).toBe("AzureActiveDirectory");
    expect(event.vendor).toBe("microsoft");
  });

  it("normalizes AD 4625 events", () => {
    const event = NormalizationService.normalizeEvent(
      {
        EventID: 4625,
        TargetUserName: "alice",
        Computer: "DC01.corp.example.com",
        IpAddress: "10.0.0.77",
        LogonType: 3,
        Status: "0xC000006D",
        TimeCreated: "2026-10-30T22:19:00Z",
      },
      Source.AD
    );

    expect(event.source).toBe(Source.AD);
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
    const event = NormalizationService.normalizeEvent(
      {
        event_id: "4625",
        target_user_name: "bob",
        computer_name: "DC02",
        ip_address: "10.0.0.80",
        logon_type: "3",
      },
      Source.AD
    );

    expect(event.eventId).toBe(4625);
    expect(event.user).toBe("bob");
    expect(event.host).toBe("DC02");
    expect(event.srcIp).toBe("10.0.0.80");
    expect(event.loginType).toBe(3);
  });
});

describe("batch parsing", () => {
  it("parses a JSON array", () => {
    const events = parseBatchBuffer(
      Buffer.from(JSON.stringify([{ source: "api" }, { source: "aws" }])),
      "events.json",
      "application/json"
    );

    expect(events).toHaveLength(2);
    expect(events[1].source).toBe("aws");
  });

  it("parses JSONL", () => {
    const events = parseBatchBuffer(
      Buffer.from('{"source":"api"}\n{"source":"ad"}\n'),
      "events.jsonl",
      "application/x-ndjson"
    );

    expect(events).toHaveLength(2);
    expect(events[0].source).toBe("api");
  });

  it("parses CSV with quoted fields", () => {
    const events = parseBatchBuffer(
      Buffer.from(
        'source,event_type,msg\nad,ad_logon_failed,"failed, bad password"\n'
      ),
      "events.csv",
      "text/csv"
    );

    expect(events).toHaveLength(1);
    expect(events[0].source).toBe("ad");
    expect(events[0].event_type).toBe("ad_logon_failed");
    expect(events[0].msg).toBe("failed, bad password");
  });
});
