# Log Manager — 30-Minute Demo Guide

A step-by-step demo script matching the assignment acceptance checklist.
Total: ~30 minutes.

## Prerequisites
 
 - Stack running: `make up && make seed`
 - Demo credentials (after seed):
   - Printed to stdout during seeding
   - Set via `SEED_ADMIN_PASSWORD`, `SEED_VIEWER_A_PASSWORD`, `SEED_VIEWER_B_PASSWORD` env vars
 - API key: printed at seed time, or check `demoa` tenant in the UI

---

## 0. Architecture overview (5 min)

Open `docs/architecture.md` and walk through the Mermaid diagram:

```
Sources → Ingest (syslog 514, HTTP /ingest, file upload) →
Normalize (Pydantic NormalizedEvent) →
PostgreSQL (JSONB + GIN) →
Search/Stats API →
React Dashboard
                                    ↓
                           Alert Worker (30s sweep) →
                           Alerts UI + Webhook
```

Key points to explain:
- 7 source types normalized to one common schema
- Tenant isolation enforced server-side (VIEWER = own tenant)
- Alert rules are stored data, evaluated every 30 seconds
- Retention ≥7 days (deletion based on ingested_at)

---

## 1. Live ingest via logger / curl / upload (6 min)

### 1a. Syslog (UDP + TCP on port 514)

```bash
# UDP - firewall sample
logger --udp --server 127.0.0.1 --port 514 \
  '<134>Aug 20 12:44:56 fw01 vendor=demo product=ngfw action=deny \
  src=10.0.1.10 dst=8.8.8.8 spt=5353 dpt=53 proto=udp \
  msg="DNS blocked" policy=Block-DNS'

# TCP - router sample
echo '<190>Aug 20 13:01:02 r1 if=ge-0/0/1 event=link-down \
mac=aa:bb:cc:dd:ee:ff reason=carrier-loss' | nc 127.0.0.1 514
```

Wait ~10 seconds, then open the UI at `https://localhost/` (or
`https://localhost:${HTTPS_PORT}/` if you changed the port) and verify the
firewall/network events appear in the logs table.

This is the native self-hosted path. In SaaS, demonstrate the same lines through
the HTTPS endpoint instead:

```bash
SYSLOG_HTTP_URL=https://<project>.vercel.app/api/ingest/syslog \
  INGEST_API_KEY='<demoa-api-key>' \
  samples/send_syslog_http.sh samples/syslog_firewall.log
```

### 1b. HTTP POST /ingest (sample 4.3)

```bash
curl -X POST http://localhost:4500/ingest \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <demoa-api-key>" \
  -d '{
    "tenant": "demoA",
    "source": "api",
    "event_type": "app_login_failed",
    "user": "alice",
    "ip": "203.0.113.7",
    "reason": "wrong_password",
    "@timestamp": "2026-11-05T10:00:00Z"
  }'
```

Then search:
```bash
curl -s "http://localhost:4500/api/get-logs?source=api&user=alice" \
  -H "X-API-Key: <demoa-api-key>"
```

### 1c. File upload (AWS/M365/AD)

```bash
# AWS CloudTrail
curl -X POST http://localhost:4500/ingest/file \
  -H "X-API-Key: <demoa-api-key>" \
  -F "file=@samples/aws_cloudtrail.json" \
  -F "source=aws"

# Microsoft 365
curl -X POST http://localhost:4500/ingest/file \
  -H "X-API-Key: <demoa-api-key>" \
  -F "file=@samples/m365_audit.json" \
  -F "source=m365"

# Active Directory
curl -X POST http://localhost:4500/ingest/file \
  -H "X-API-Key: <demoa-api-key>" \
  -F "file=@samples/ad_4625.json" \
  -F "source=ad"
```

Verify normalized fields in the UI (event_type, src_ip, user, cloud fields,
etc.).

---

## 2. Raw vs normalized (3 min)

Fetch one event's detail (normalized fields plus the original payload in `raw`):

```bash
curl -s -b /tmp/cookies "http://localhost:4500/api/get-logs?limit=1" | \
  python3 -c 'import json,sys; print(json.load(sys.stdin)["logs"][0]["id"])'

curl -s -b /tmp/cookies http://localhost:4500/api/events/<event-id> | python3 -m json.tool
```

Show the normalized fields (ts, tenant, source, event_type, severity, action,
outcome, src_ip, user, host, etc.) and the preserved `raw` JSON. A tenant
VIEWER or tenant-bound ADMIN gets HTTP 404 for another tenant's event, while a
platform ADMIN (tenant `NULL`) can read any tenant.

Demonstrate that a syslog message, an AWS CloudTrail record, and an AD event
all look the same in normalized form, with the original preserved in `raw`.
A row-click detail drawer in the web UI is a future enhancement; the API above
is the supported path today.

---

## 3. Search and dashboard (5 min)

In the UI dashboard:

- **KPI cards**: total events, failed logins, open alerts, active sources
- **Timeline chart**: stacked by source, showing event volume over time
- **Top 10 Source IPs**: bar chart of most frequent source IPs
- **Top 10 Users**: bar chart of most active users
- **Top Event Types**: bar chart of event type distribution
- **Source distribution**: pie chart

Apply filters:
- Time range: 15m, 1h, 24h, 7d, or custom
- Tenant: Admin can select "All" or a specific tenant; Viewer is locked to their own
- Source: multi-select (firewall, network, api, crowdstrike, aws, m365, ad)

Verify that changing any filter re-queries all widgets.

---

## 4. Bruteforce simulator → alert + webhook (5 min)

Run the simulator in bruteforce mode:

```bash
make demo
```

This runs:
```bash
python3 samples/simulator.py \
  --rate 20 --duration 15 --scenario bruteforce \
  --tenants demoA \
  --url http://localhost:4500 \
  --api-key <demoa-api-key> \
  --syslog-host 127.0.0.1 --syslog-port 514
```

This generates ≥8 AD 4625 (failed logon) and api app_login_failed events from
IP 203.0.113.77 within 60 seconds.

Observe:
- The seeded "Brute force: repeated failed logins" rule (5 failures / 5 min per
  src_ip, all tenants) fires
- An alert appears in the Alerts page with status=open, severity=high
- The alert shows group_value=203.0.113.77, count≥5
- If a webhook URL is configured on the rule, the webhook-receiver logs it

Check the webhook receiver:
```bash
curl -s http://localhost:8008/alerts
```

Demonstrate cooldown: run the simulator again immediately — no duplicate alert
is created within the cooldown window (15 minutes by default).

---

## 5. RBAC: viewer-a vs demoB (3 min)

Log in as viewerA@demo.local / (seed-printed-password):

1. Open the dashboard — only demoA data is shown
2. Open the logs page — no demoB events appear
3. Try to access demoB directly via API:

```bash
# Login as viewer-a to get a session cookie
 curl -c /tmp/cookies -X POST http://localhost:4500/api/auth/login \
   -H "Content-Type: application/json" \
   -d '{"email":"viewerA@demo.local","password":"<viewerA-password>"}'

# Try to see demoB data - should return zero demoB rows
curl -b /tmp/cookies "http://localhost:4500/api/get-logs?tenant=demoB&limit=5"
```

4. Try to create a rule as viewer — should return 403:
```bash
curl -b /tmp/cookies -X POST http://localhost:4500/api/create-alertRule \
  -H "Content-Type: application/json" \
  -d '{"name":"test","tenant":"demoA","conditions":[{"type":"event_type","value":"test"}]}'
```

Log in as admin@demo.local and verify admin can see all tenants and create rules.

---

## 6. Public HTTPS URL (3 min)

For the SaaS deployment, open the Vercel URL. Vercel and Render manage TLS, so
there is no domain or certificate work:

```bash
curl -sSI https://<project>.vercel.app/
curl -s -o /dev/null -w '%{http_code}\n' https://<project>.vercel.app/api/get-logs
```

For a self-hosted appliance with a domain, set `DOMAIN`, `CADDY_EMAIL`, and
`CADDY_BIND_IP=0.0.0.0` in `.env`, then start the standard Compose file. Caddy
requests a certificate once DNS points at the host:

```bash
CADDY_BIND_IP=0.0.0.0
DOMAIN=logs.example.com
CADDY_EMAIL=admin@example.com
make up
```

For a local appliance without a domain, Caddy uses an internal certificate and
the browser shows a warning. Document that as expected. `docker-compose.vm.yml`
is an internal deployment artifact and is not used for the self-hosted demo.

---

## 7. Retention (3 min)

Check retention configuration:

```bash
grep RETENTION_DAYS .env
# RETENTION_DAYS=7
```

Run maintenance manually:

```bash
make maintenance
```

Verify that events older than 7 days (based on ingested_at) are purged.
The worker runs this hourly automatically.

---

## Demo credentials hand-off
 
 Give reviewers the credentials verbally or in a separate secure channel —
 **never commit them to the repository**:
 
 - Admin: admin@demo.local / (seed-printed-password)
 - Viewer A: viewerA@demo.local / (seed-printed-password) (demoA)
 - Viewer B: viewerB@demo.local / (seed-printed-password) (demoB)
 - API key: printed at `make seed` time (demoa tenant)
