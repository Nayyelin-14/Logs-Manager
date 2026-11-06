#!/usr/bin/env python3
"""Log simulator for the Logs Manager demo.

Generates current-timestamp events for all 7 source types, including
bruteforce attack patterns (>=8 failed logins from one IP within 60s).
"""

from __future__ import annotations

import argparse
import itertools
import json
import random
import socket
import sys
import time
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    print("ERROR: install requests: pip install requests", file=sys.stderr)
    sys.exit(1)

TENANT_IPS = {
    "demoA": ["203.0.113.10", "203.0.113.11", "203.0.113.12", "203.0.113.77"],
    "demoB": ["198.51.100.10", "198.51.100.11", "198.51.100.23"],
}
BRUTE_FORCE_IP = "203.0.113.77"
_SEQ = itertools.count(1)


def _stamp_unique(event: dict) -> dict:
    """Add a unique record marker so repeated identical-looking events never collide."""
    raw = event.get("raw")
    if not isinstance(raw, dict):
        raw = {}
        event["raw"] = raw
    raw["_sim_seq"] = next(_SEQ)
    raw["_sim_ns"] = time.time_ns()
    return event


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def rand_ip(tenant: str) -> str:
    return random.choice(TENANT_IPS.get(tenant, ["10.0.0.1"]))


def make_event(source: str, tenant: str, scenario: str) -> dict:
    now = now_iso()
    ip = rand_ip(tenant)
    force_brute = (
        scenario == "bruteforce"
        and source in ("ad", "api")
        and random.random() < 0.75
    )
    if force_brute:
        ip = BRUTE_FORCE_IP

    if source == "ad":
        if scenario == "bruteforce" and ip == BRUTE_FORCE_IP:
            return {
                "tenant": tenant, "source": "ad", "event_id": 4625,
                "event_type": "LogonFailed", "user": "demo\\eve", "host": "DC01",
                "ip": ip, "logon_type": 3, "action": "LOGIN", "status": "Failure",
                "severity": 7, "@timestamp": now,
                "raw": {"_sim": True, "scenario": scenario, "event_id": 4625},
                "tags": ["demo", "simulator"],
            }
        return {
            "tenant": tenant, "source": "ad",
            "event_id": random.choice([4624, 4625, 4634, 4720]),
            "event_type": random.choice(["LogonSuccess", "LogonFailed", "Logoff", "UserCreated"]),
            "user": f"user{random.randint(1, 50)}", "host": f"DC{random.randint(1, 5)}",
            "ip": ip, "logon_type": random.choice([2, 3, 10]),
            "action": random.choice(["LOGIN", "LOGOUT", "CREATE"]),
            "status": random.choice(["Success", "Failure"]),
            "severity": random.randint(1, 8), "@timestamp": now,
            "raw": {"_sim": True, "scenario": scenario}, "tags": ["demo", "simulator"],
        }

    if source == "api":
        if scenario == "bruteforce" and ip == BRUTE_FORCE_IP:
            return {
                "tenant": tenant, "source": "api",
                "event_type": "app_login_failed", "user": "alice", "ip": ip,
                "reason": "wrong_password", "@timestamp": now,
                "raw": {"_sim": True, "scenario": scenario}, "tags": ["demo", "simulator"],
            }
        return {
            "tenant": tenant, "source": "api",
            "event_type": random.choice(["app_login", "app_logout", "app_login_failed"]),
            "user": f"user{random.randint(1, 50)}", "ip": ip,
            "reason": random.choice(["wrong_password", "account_locked", None]),
            "@timestamp": now, "raw": {"_sim": True, "scenario": scenario},
            "tags": ["demo", "simulator"],
        }

    if source == "crowdstrike":
        return {
            "tenant": tenant, "source": "crowdstrike", "event_type": "malware_detected",
            "host": f"WIN{random.randint(1, 99):02d}-01",
            "process": random.choice(["powershell.exe", "cmd.exe", "mimikatz.exe"]),
            "severity": random.randint(6, 9), "action": "quarantine",
            "@timestamp": now, "raw": {"_sim": True, "scenario": scenario, "sha256": "abc..."},
            "tags": ["demo", "simulator"],
        }

    if source == "aws":
        return {
            "tenant": tenant, "source": "aws",
            "event_type": random.choice(["CreateUser", "DeleteUser", "ConsoleLogin", "CreateAccessKey"]),
            "user": "admin", "ip": ip,
            "cloud": {"service": "iam", "account_id": "123456789012", "region": "us-east-1"},
            "action": random.choice(["CREATE", "DELETE", "LOGIN"]),
            "severity": random.randint(3, 7), "@timestamp": now,
            "raw": {"_sim": True, "scenario": scenario, "eventName": "CreateUser"},
            "tags": ["demo", "simulator"],
        }

    if source == "m365":
        return {
            "tenant": tenant, "source": "m365",
            "event_type": random.choice(["UserLoggedIn", "UserLoggedOut", "MailboxLogin"]),
            "user": f"user{random.randint(1, 50)}@demo.local", "ip": ip,
            "status": random.choice(["Success", "Failure"]),
            "workload": random.choice(["Exchange", "SharePoint", "Teams"]),
            "@timestamp": now, "raw": {"_sim": True, "scenario": scenario},
            "tags": ["demo", "simulator"],
        }

    return {
        "tenant": tenant, "source": "firewall", "event_type": "firewall_deny",
        "action": "deny", "src_ip": ip,
        "src_port": random.randint(1024, 65535),
        "dst_ip": random.choice(["8.8.8.8", "1.1.1.1", "10.0.0.1"]),
        "dst_port": random.choice([53, 80, 443, 22]),
        "protocol": random.choice(["udp", "tcp"]), "host": "fw01",
        "rule_name": "Block-DNS", "severity": random.randint(3, 6),
        "@timestamp": now, "raw": {"_sim": True, "scenario": scenario, "msg": "DNS blocked"},
        "tags": ["demo", "simulator"],
    }


def make_network_event(tenant: str, scenario: str) -> dict:
    return {
        "tenant": tenant, "source": "network", "event_type": "link-down",
        "host": "r1", "interface": "ge-0/0/1",
        "mac": f"aa:bb:cc:dd:{random.randint(10, 99):02d}:ee",
        "reason": "carrier-loss", "severity": 4,
        "@timestamp": now_iso(),
        "raw": {"_sim": True, "scenario": scenario, "if": "ge-0/0/1", "event": "link-down"},
        "tags": ["demo", "simulator"],
    }


def send_syslog(message: str, host: str, port: int, proto: str = "udp") -> None:
    try:
        if proto == "udp":
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(message.encode("utf-8"), (host, port))
            sock.close()
        else:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.connect((host, port))
            sock.sendall((message + "\n").encode("utf-8"))
            sock.close()
    except Exception as exc:
        print(f"WARNING: syslog send failed ({proto} {host}:{port}): {exc}", file=sys.stderr)


def format_syslog_firewall(event: dict) -> str:
    ts = datetime.now(timezone.utc).strftime("%b %d %H:%M:%S")
    return (
        f"<134> {ts} fw01 vendor=demo product=ngfw "
        f"action={event['action']} src={event['src_ip']} "
        f"dst={event['dst_ip']} spt={event['src_port']} "
        f"dpt={event['dst_port']} proto={event['protocol']} "
        f"msg=\"{event['raw'].get('msg', 'blocked')}\" policy={event.get('rule_name', 'Block-DNS')}"
    )


def format_syslog_router(event: dict) -> str:
    ts = datetime.now(timezone.utc).strftime("%b %d %H:%M:%S")
    return (
        f"<190> {ts} r1 if={event['interface']} "
        f"event={event['event_type']} mac={event['mac']} "
        f"reason={event['reason']}"
    )


def post_event(event: dict, url: str, api_key: str) -> None:
    try:
        headers = {"Content-Type": "application/json", "X-API-Key": api_key}
        requests.post(f"{url.rstrip('/')}/ingest", json=event, headers=headers, timeout=5)
    except Exception as exc:
        print(f"WARNING: POST /ingest failed: {exc}", file=sys.stderr)


def run_simulator(rate: float, duration: int, tenants: list, scenario: str,
                  url: str, api_key: str, syslog_host: str, syslog_port: int) -> None:
    end_time = time.time() + duration
    interval = 1.0 / rate if rate > 0 else 1.0
    sources = ["firewall", "network", "api", "crowdstrike", "aws", "m365", "ad"]
    count = 0
    brute_count = 0

    print(f"Simulator: rate={rate}/s, duration={duration}s, scenario={scenario}")
    print(f"  Tenants: {tenants}  URL: {url}  Syslog: {syslog_host}:{syslog_port}")

    while time.time() < end_time:
        tenant = random.choice(tenants)
        source = random.choice(sources)
        count += 1

        if source == "firewall":
            event = _stamp_unique(make_event(source, tenant, scenario))
            if scenario == "bruteforce" and event.get("src_ip") == BRUTE_FORCE_IP:
                brute_count += 1
            send_syslog(format_syslog_firewall(event), syslog_host, syslog_port, "udp")
        elif source == "network":
            event = _stamp_unique(make_network_event(tenant, scenario))
            send_syslog(format_syslog_router(event), syslog_host, syslog_port, "udp")
        else:
            event = _stamp_unique(make_event(source, tenant, scenario))
            if scenario == "bruteforce" and event.get("ip") == BRUTE_FORCE_IP:
                brute_count += 1
            post_event(event, url, api_key)

        if source == "firewall" and count % 10 == 0:
            event = _stamp_unique(make_event(source, tenant, scenario))
            send_syslog(format_syslog_firewall(event), syslog_host, syslog_port, "tcp")

        time.sleep(interval)

    print(f"\nFinished: {count} events, {brute_count} brute-force events")


def main() -> None:
    global BRUTE_FORCE_IP
    parser = argparse.ArgumentParser(description="Log simulator for Logs Manager demo")
    parser.add_argument("--rate", type=float, default=5.0, help="Events per second")
    parser.add_argument("--duration", type=int, default=60, help="Duration in seconds")
    parser.add_argument("--tenants", type=str, default="demoA,demoB", help="Comma-separated tenants")
    parser.add_argument("--scenario", type=str, choices=["normal", "bruteforce"], default="normal")
    parser.add_argument("--url", type=str, default="http://localhost:4500", help="Backend API URL")
    parser.add_argument("--api-key", type=str, default="ingest-key-dev", help="Ingest API key")
    parser.add_argument("--syslog-host", type=str, default="127.0.0.1", help="Syslog host")
    parser.add_argument("--syslog-port", type=int, default=514, help="Syslog port")
    parser.add_argument("--brute-ip", type=str, default=BRUTE_FORCE_IP, help="Source IP used for bruteforce events")
    args = parser.parse_args()

    BRUTE_FORCE_IP = args.brute_ip
    tenants = [t.strip() for t in args.tenants.split(",") if t.strip()]

    try:
        run_simulator(
            rate=args.rate, duration=args.duration, tenants=tenants, scenario=args.scenario,
            url=args.url, api_key=args.api_key,
            syslog_host=args.syslog_host, syslog_port=args.syslog_port,
        )
    except KeyboardInterrupt:
        print("\nSimulator interrupted")
        sys.exit(0)
    except Exception as exc:
        print(f"FATAL: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
