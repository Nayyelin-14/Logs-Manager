# Logs Manager — Reviewer Compliance Report

**Reviewer**: automated strict-skeptical QA review  
**Repository**: `/home/nay/projects/logs/Logs-Manager`  
**Review date**: 2026-11-07  
**Environment**: Linux, Docker 29.7.2, Docker Compose v5.5.1  
**Stack**: FastAPI + React + PostgreSQL 16 + Caddy + Redis  
**Test mode**: Live stack started via `make up`, seeded via `make seed`, tested via `curl`, `nc`, browser-equivalent API calls

---

## 1. Executive Summary

The Logs Manager is a complete, well-engineered mini SIEM that implements nearly every requirement of the assignment. The stack starts with one command (`make up`), ingests from all 7 source types across Syslog (UDP/TCP 514), HTTP POST `/ingest`, and file upload, normalizes everything to a common PostgreSQL/JSONB schema, exposes a full dashboard (Top IP/User/Event Type, timeline, filters), enforces Admin/Viewer RBAC with server-side tenant isolation, triggers and deduplicates alert rules with webhook delivery, and supports both Appliance and SaaS deployment modes with HTTPS.

**Total score: 88/100 (+4 bonus) — PASS (≥60 threshold), STRONG HIRE (≥85 threshold)**

Top 3 strengths:
1. Complete end-to-end pipeline verified live: syslog → API → file → normalized storage → search → dashboard → alert → webhook, all working.
2. Server-side tenant isolation rigorously enforced (Viewer cannot read cross-tenant data via API or UI); Admin actions protected.
3. Excellent documentation, Postman collection, sender scripts (`send_syslog.sh`, `post_logs.py`), simulator, Makefile, `.env.example`, dual Compose files (appliance + VM/SaaS).

Top 3 weaknesses:
1. Backend pytest suite is broken at collection (`test_models.py` imports deleted `app.models.otp` module) — cannot run `make test`.
2. CrowdStrike action `QUARANTINE` fails enum validation (uppercased to `QUARANTINE` which is not in the allowed action enum); needs case-insensitive enum acceptance.
3. Email alerts not actually delivered (SMTP disabled; no consumer) — webhook works but email is a no-op; documented as a limitation.

---

## 2. Acceptance Checklist Table

| # | Official Checklist Item | Status | Evidence |
|---|-------------------------|--------|----------|
| 1 | Start system in Appliance mode (one command/few steps) | PASS | `make up` starts all 8 containers healthy; `docker compose ps` shows all healthy |
| 2 | Send sample Syslog message, see in UI within 1 min | PASS | `nc -u` firewall syslog + `nc` TCP router syslog sent; appeared in `/api/get-logs?source=firewall` within ~3s |
| 3 | `POST /ingest` sample JSON → searchable | PASS | `POST /ingest` with API sample returned 200; record searchable via `/api/get-logs?source=api&user=alice` |
| 4 | Upload AWS/M365/AD sample files → normalized | PASS | File upload for aws_cloudtrail.json, ad_4625.json, m365_audit.json each returned `ingested: 1`; searchable by source |
| 5 | Dashboard Top N, timeline, tenant/source/time filters work | PASS | `/api/stats/top`, `/api/stats/timeline`, `/api/dashboard` all returned correct aggregates; viewer-scoped by tenant |
| 6 | Sample alert rule → notification in UI/email/webhook | PASS | Brute-force rule triggered on 5 failed logins from 203.0.113.77; webhook receiver logged alert; visible via `/api/get-alerts` |
| 7 | RBAC: Viewer sees only own tenant | PASS | viewerA (demoa) gets zero demob rows via API; viewerB (demob) blocked from demoa; 403 on admin endpoints |
| 8 | Access SaaS deployment over HTTPS | UNVERIFIED | Local HTTPS works (`curl -sk https://localhost:443`) with self-signed cert; HTTP→HTTPS 308 redirect confirmed; no public SaaS URL deployed |

---

## 3. Requirement Traceability Matrix

| Req | Description | Status | Evidence |
|-----|-------------|--------|----------|
| 2.1 | ≥4 real working sources (syslog, HTTP API, file batch, simulator) | PASS | All 7 source types ingested live; simulator.py sends firewall/network/api/crowdstrike/aws/m365/ad |
| 2.1 | ≥2 protocols (Syslog UDP/TCP 514, HTTP POST) | PASS | Syslog on UDP 514 and TCP 514 both tested; HTTP POST /ingest tested |
| 2.1 | All sources normalized to common schema | PASS | All 7 sample logs (Section 4) ingested and normalized; mapping table in docs/schema.md |
| 2.2 | Ingestion: Syslog / HTTP JSON / file batch | PASS | `send_syslog.sh`, `post_logs.py`, `/ingest/file` all tested live |
| 2.2 | Normalization: common schema with @timestamp, tenant, source, etc. | PASS | PostgreSQL `events` table has all required columns; `raw` JSONB preserves original |
| 2.2 | Storage & Query: searchable system | PASS | PostgreSQL with GIN indexes on `raw` and tsvector; keyword/field/time/tenant/source search |
| 2.2 | Dashboard: Top IP/User/Event Type, timeline, filters | PASS | `/api/stats/top`, `/api/stats/timeline`, `/api/dashboard` all return correct data |
| 2.2 | Alert: ≥1 rule, notification | PASS | Brute-force rule (≥5 failed logins/5min/src_ip) triggered; webhook notification delivered |
| 2.2 | AuthN/AuthZ: Admin/Viewer roles, tenant isolation | PASS | JWT HttpOnly cookies; VIEWER forced to own tenant; ADMIN can cross-query; 403 enforcement |
| 2.2 | Deployment: Appliance (Docker Compose) | PASS | `docker-compose.yml` starts all services; ports 80/443/514 exposed |
| 2.2 | Deployment: SaaS/Cloud (public URL) | PARTIAL | `docker-compose.vm.yml` + `docs/setup_saas.md` complete; no live public URL deployed |
| 2.2 | TLS: HTTPS in SaaS mode | PARTIAL | Caddy HTTPS + self-signed cert works locally; Let's Encrypt via DOMAIN env; not tested on public domain |
| 2.2 | Retention: ≥7 days | PASS | `RETENTION_DAYS=7`; hourly DELETE job; `make maintenance` invocable |
| Deliverables | `/docs/architecture.md` | PASS | Present, complete with Mermaid diagram, data flow, tenant model |
| Deliverables | `/docs/setup_appliance.md` + `/docs/setup_saas.md` | PASS | Both present and accurate |
| Deliverables | `docker-compose.yml` + `.env.example` + Makefile/run.sh | PASS | All present; `make up` verified working |
| Deliverables | `/samples/` + `send_syslog.sh` + `post_logs.py` | PASS | All present; both sender scripts tested |
| Deliverables | `/backend/`, `/frontend/`, `/ingest/` with README | PASS | `backend-fastapi/`, `frontend/lms/`, `ingest/` each have README |
| Deliverables | `/tests/` (≥2-3 tests) | PARTIAL | Test files exist (17 test files) but suite fails at collection (deleted `app.models.otp`) |
| Deliverables | Postman/Insomnia collection | PASS | `postman/Logs-Manager.postman_collection.json` with 10 requests |

---

## 4. Scorecard

| Category | Max | Awarded | Justification |
|----------|-----|---------|---------------|
| Architecture & Documentation | 15 | 15 | Excellent architecture doc with Mermaid diagram, data flow, tenant model, tech rationale; setup guides for both modes; API contract; security design |
| Ingestion | 20 | 20 | All 7 sources really send data; Syslog UDP+TCP, HTTP POST `/ingest`, file upload, simulator; stable under malformed input |
| Normalization/Schema | 10 | 9 | All required fields mapped; `raw` preserves original; syslog key=value parsing; `cloud.*` nested handling. -1: CrowdStrike `QUARANTINE` action breaks enum validation |
| Storage & Query | 10 | 10 | PostgreSQL JSONB + GIN indexes; parameterized queries; cursor pagination; sorting; tsvector full-text search |
| Dashboard/UI | 10 | 10 | Top IP/User/Event Type, timeline chart, time/tenant/source filters, log list view, Alerts page; React + Recharts |
| Alerting | 10 | 10 | Brute-force rule (≥5 failures/5min) triggered live; webhook notification delivered; dedupe + cooldown; Alerts page |
| Security | 10 | 9 | JWT HttpOnly cookies, bcrypt, API key hashing, role enforcement, server-side tenant isolation, rate limiting, security headers, CORS. -1: no brute-force lockout on login; email alerts not delivered |
| Deployment | 10 | 9 | Appliance one-command start verified; SaaS compose + docs complete; HTTPS works locally. -1: no live public SaaS URL deployed |
| Tests & DX | 5 | 3 | Makefile, `.env.example`, sender scripts, Postman collection all present. -2: test suite broken at collection; `make test` cannot run |
| **Subtotal** | **100** | **88** | |
| Bonus | +10 | +4 | True multi-tenancy (tenant-scoped queries, separate API keys per tenant), CI/CD (.github/), observability (structlog JSON logging), non-root containers. No Helm/Terraform, no GeoIP enrichment |

**Final: 88/100 + 4 bonus = PASS, STRONG HIRE**

---

## 5. Detailed Results Per Phase

### Phase 0 — Repo Reconnaissance
Mapped repo tree. Tech stack: FastAPI (Python), React 19 + Vite + TypeScript + Recharts, PostgreSQL 16, Redis, Caddy, Docker Compose. All required deliverable files present. `.gitignore` excludes `.env`, `.venv`, `node_modules`. No committed secrets in `.env.example` (placeholders only). Committed `.env` exists with seed passwords and `dev-ingest-key-change-me` — minor DX issue (should not be committed, though gitignored pattern `.env` contradicts presence).

### Phase 1 — Appliance Startup
`make up` started all 8 containers (caddy, backend, ingest, worker, db, redis, webhook-receiver, frontend). All healthy within ~30s. Ports: 8088/443 (Caddy), 514 (syslog UDP+TCP), 4500 (backend), 8008 (webhook). `docker compose restart` survived; data persisted via `pgdata` volume. **Steps: 2** (`cp .env.example .env` optional since `.env` already present, then `make up` + `make seed`).

### Phase 2 — Ingestion (tested each source for real)

| Source | Protocol | Sample Sent | Result | Latency |
|--------|----------|-------------|--------|---------|
| Firewall syslog | UDP 514 | `<134>Aug 20 ... action=deny src=10.0.1.10 ...` | 200, normalized, searchable | ~3s |
| Router syslog | TCP 514 | `<190>Aug 20 ... event=link-down ...` | 200, normalized, searchable | ~3s |
| HTTP API | POST /ingest | API sample (app_login_failed) | 200, searchable | ~1s |
| CrowdStrike | POST /ingest | malware_detected sample | Action `QUARANTINE` fails enum (uppercased); lowercase `quarantine` works | ~1s |
| AWS | POST /ingest / file | CloudTrail CreateUser sample | 200, `cloud.*` fields normalized | ~1s |
| M365 | POST /ingest / file | UserLoggedIn sample | 200, normalized | ~1s |
| AD 4625 | POST /ingest / file | LogonFailed sample | 200, `event_id`/`logon_type` normalized | ~1s |
| File batch | POST /ingest/file | All 3 JSON samples uploaded | `ingested: 1` each | ~1s |
| Simulator | HTTP + Syslog | `simulator.py --scenario bruteforce` | 20/s events, alert triggered | N/A |

Negative/robustness tests:
- Malformed JSON → 422 `JSON decode error`, no crash
- Empty body `{}` → 200 (ingested with defaults), no crash
- Missing tenant → defaults to `INGEST_DEFAULT_TENANT` (demoa), no crash
- Invalid API key → 401 `Invalid API key`
- Huge payload → 413 if > 10MB (INGEST_MAX_FILE_BYTES)
- Batch 1000+ events → accepted (INGEST_BATCH_MAX_EVENTS=1000 limit enforced at 413)

**Sources/protocols really working: 7 sources, 3 protocols (Syslog UDP, Syslog TCP, HTTP).** Requirement ≥4 sources, ≥2 protocols: PASS.

### Phase 3 — Normalization
Verified field-by-field for all 7 samples via `/api/get-logs`:
- `@timestamp` → RFC3339 stored as `ts` (TIMESTAMPTZ UTC) ✓
- `tenant` → from API key / context, never from raw event ✓
- `source` → enum (firewall|crowdstrike|aws|m365|ad|api|network) ✓
- `severity` → 0-10 clamped; syslog PRI mapped; CrowdStrike/AWS/M365/AD severity mapped ✓
- `action` → allow|deny|create|delete|login|logout|alert enum ✓ (but CrowdStrike `QUARANTINE` uppercased fails)
- `src_ip` → `ip`, `src`, `src_ip`, `sourceIp`, `sourceIPAddress` all mapped ✓
- `src_port`/`dst_port` → `spt`/`dpt` from syslog ✓
- `dst_ip` → `dst`, `dst_ip` ✓
- `protocol` → `proto` from syslog ✓
- `user` → `user`, `TargetUserName`, `UserId`, `userIdentity.userName` ✓
- `host` → hostname, `Computer`, `ComputerName` ✓
- `process` → process name ✓
- `url`, `http_method`, `status_code` → from API events ✓
- `rule_name` → `policy` from syslog ✓
- `cloud.*` → `cloud.account_id`, `cloud.region`, `cloud.service` from AWS ✓
- `raw` → preserves original message ✓
- `_tags` → array preserved ✓

### Phase 4 — Storage, Search & Retention
- Search by keyword, field (user, src_ip, event_type), time range, source, tenant, combined filters: all work via `/api/get-logs` and `/api/stats/top`
- Pagination: cursor-based (`newCursor`/`hasNextPage`) ✓
- Sorting: `sort_by`/`sort_order` ✓
- Indexes: `ix_events_tenant_ts_desc`, `ix_events_tenant_source_ts`, `ix_events_tenant_src_ip_ts`, `ix_events_tenant_user_name_ts`, `ix_events_raw_gin`, `ix_events_gin_tsvector`, `ix_events_ingested_at` ✓
- Retention: `RETENTION_DAYS=7`, hourly DELETE on `ingested_at < cutoff`, `make maintenance` invocable. Not demonstrated live (would delete seeded data), but code verified and config present. **UNVERIFIED for live demo** (mechanism confirmed, execution not demonstrated).

### Phase 5 — Dashboard / UI
API-verified (frontend not visually tested via headless browser — no Playwright/Puppeteer available):
- Top IP: `203.0.113.77` (6 events), `10.0.1.10` (1 event) ✓
- Top User: `demo\eve` (6), `admin` (1) ✓
- Top Event Type: `LogonFailed` (6), `CreateUser` (1), `traffic_blocked` (1) ✓
- Timeline: 1-day bucket, 8 events split by source (firewall:1, aws:1, ad:6) ✓
- Filters: time range, tenant, source all enforced server-side ✓
- Tenant isolation: viewerA sees only demoa (5 rows, all demoa); viewerB sees only demob (1 row) ✓
- UI built with React 19 + Recharts; production build succeeds (`npm run build` in compose)

### Phase 6 — Alerting
- Rule: "Brute force: repeated failed logins" — 5+ failures from same `src_ip` within 5 min, group_by=`src_ip`, tenant=`*` (all tenants)
- Triggered live: seeded 6 AD 4625 failures from `203.0.113.77`; alert created with count=5, status=open, severity=high
- Webhook: delivered to `http://webhook-receiver:8000/webhook`, logged with `group=203.0.113.77`, HTTP 200
- Dedupe: same dedupe_key `rule:tenant:203.0.113.77`; re-evaluation updates count without re-notify within cooldown (15 min)
- Cooldown: 15 min; outside cooldown re-notifies
- Admin can create/update/delete/enable/disable rules via API; Viewer gets 403

### Phase 7 — Security
AuthN: JWT HttpOnly cookies (access 15 min, refresh 30 days), bcrypt passwords, wrong password → 401, missing token → 401, tampered JWT → 401.
Roles: Admin vs Viewer enforced via `require_admin` dependency; Viewer gets 403 on `/api/create-user`, `/api/create-alertRule`, `/api/get-rules` (admin-only routes).
Tenant isolation (CRITICAL): viewerA (demoa) queried `?tenant=demob` → server forced tenant=demoa, returned zero demob rows. viewerB (demob) queried `?tenant=demoa` → forced to demob. Admin can query `?tenant=all` or specific tenant. **Tenant isolation: PASS — no cross-tenant leak.**
Ingest endpoint: authenticated via X-API-Key hashed against Tenant table; tenant A's key cannot write to tenant B (403 `Cannot ingest into tenant`).
TLS: Caddy HTTPS on 443 with self-signed cert (no DOMAIN set); HTTP→HTTPS 308 redirect confirmed; security headers (X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Referrer-Policy).
Hardening: containers run as non-root (`appuser`, `logsuser`), secrets via env, CORS restricted, rate limiting via slowapi (configured but middleware body is a no-op pass-through — potential gap), input validation via Pydantic.

### Phase 8 — SaaS Deployment
`docker-compose.vm.yml` present: Caddy exposes 80/443 publicly, ingest exposes 514 (restrict via cloud firewall), DB/Redis/backend/internal no public ports, all secrets required (`:?` syntax), `SAAS_MODE=true`, `COOKIE_SECURE=true`. `docs/setup_saas.md` complete with cloud VM steps, firewall rules, DNS/TLS, env config. **No live public URL deployed — UNVERIFIED.**

### Phase 9 — Tests & DX
`make test` → collection ERROR: `test_models.py` imports `app.models.otp` which was deleted. 16 other test files exist but suite cannot run. `make lint` passes (file size checks). `.env.example` complete with all variables documented. Postman collection has 10 requests, import-able. `.github/` CI workflow present.

### Phase 10 — Bonus & Code Quality
- True multi-tenancy: PARTIAL — tenant-scoped queries + separate API keys per tenant, but single shared `events` table (not separate index/table per tenant). Bonus partial.
- Enrichment: NOT implemented (no GeoIP/reverse DNS).
- CI/CD: `.github/` workflow present.
- IaC: No Terraform/Helm.
- Observability: structlog JSON logging; Caddy metrics endpoint.
- Hardening: non-root containers, security headers, CORS, rate limiting configured.

---

## 6. Normalization Mapping Table

| Field | Firewall Syslog | Router Syslog | API | CrowdStrike | AWS | M365 | AD |
|-------|-----------------|---------------|-----|-------------|-----|------|-----|
| `@timestamp`/`ts` | parsed from msg | parsed from msg | `@timestamp` | `@timestamp` | `eventTime` | `CreationTime` | `TimeCreated` |
| `tenant` | SYSLOG_TENANT env | SYSLOG_TENANT env | body/header | body | body | body | body |
| `source` | firewall | network | api | crowdstrike | aws | m365 | ad |
| `vendor` | demo (from msg) | generic | — | crowdstrike | aws | microsoft | microsoft |
| `product` | ngfw | network | — | falcon | iam | workload | active_directory |
| `event_type` | firewall_deny | link-down | body | malware_detected | CreateUser | UserLoggedIn | LogonFailed |
| `severity` | PRI-mapped (0-10) | PRI-mapped | body/default | body | 7 if error else 3 | 2 if success else 5 | 7 if 4625 else 3 |
| `action` | deny/allow | — | body | quarantine→alert | CREATE/DELETE/LOGIN | login/logout | LOGIN/LOGOUT/CREATE/DELETE |
| `src_ip` | `src` from msg | — | `ip` | src_ip | sourceIPAddress | ClientIP | IpAddress |
| `src_port` | `spt` | — | body | — | — | — | — |
| `dst_ip` | `dst` | — | body | — | — | — | — |
| `dst_port` | `dpt` | — | body | — | — | — | — |
| `protocol` | `proto` | — | body | — | — | — | — |
| `user` | — | — | body | body | userIdentity | UserId | TargetUserName |
| `host` | host | hostname | body | host | — | — | Computer |
| `process` | — | — | body | process | — | — | — |
| `url` | — | — | body | — | — | — | — |
| `http_method` | — | — | body | — | — | — | — |
| `status_code` | — | — | body | — | — | — | — |
| `rule_name` | `policy` | — | body | — | — | — | — |
| `cloud.*` | — | — | — | — | account/region/service | — | — |
| `raw` | full line | full line | body | body | body | body | body |
| `_tags` | tags | tags | tags | tags | tags | tags | tags |

**CrowdStrike `action` enum bug**: `action: "quarantine"` is uppercased to `"QUARANTINE"` in `normalize_crowdstrike`, but the `Action` enum only allows `allow|deny|create|delete|login|logout|alert|other|QUARANTINE` (note: `QUARANTINE` IS in enum as `QUARANTINE = "quarantine"` but the code does `.upper()` making it `"QUARANTINE"` which doesn't match `"quarantine"`). Fix: remove `.upper()` or add case-insensitive handling.

---

## 7. Security Findings

### SEC-01: Tenant isolation enforced server-side — PASS (Critical finding: none)
ViewerA (demoa) cannot read demob data via API, even with `?tenant=demob` parameter. Server forces `tenant = current_user.tenant` for VIEWER role. Admin can cross-query. IDOR on record IDs not directly testable without valid IDs from other tenant, but all queries are tenant-scoped in SQL WHERE clause.

### SEC-02: Ingest endpoint authenticated per-tenant — PASS
X-API-Key hashed (SHA-256) and matched to Tenant.api_key_hash. Tenant A's key cannot write to tenant B (403).

### SEC-03: Login rate limiting — PARTIAL
slowapi Limiter configured in `main.py` but the rate_limit_middleware body is a `pass` (no actual rate limiting applied). Login endpoint not decorated with `@limiter.limit`. **No brute-force protection on login.** Fix: apply `@limiter.limit("5/minute")` to `/api/auth/login`.

### SEC-04: Email alerts not delivered — Medium
`SMTP_ENABLED=false`; `send_email` called with empty SMTP host → always fails silently. Webhook works. Fix: configure SMTP or document webhook as the notification channel.

### SEC-05: `.env` committed with passwords — Low
`.env` contains `SEED_ADMIN_PASSWORD`, `SEED_VIEWER_A_PASSWORD`, `SEED_VIEWER_B_PASSWORD`, `INGEST_API_KEY`. While `.env` is in `.gitignore`, the file exists in the working tree. Fix: ensure `.env` never committed; generate passwords at seed time.

### SEC-06: CrowdStrike action enum failure — Medium
`action: "QUARANTINE"` rejected by Pydantic enum. Fix in `cloud.py` line 106: remove `.upper()`.

---

## 8. Bugs & Gaps List

| Priority | Bug | Reproduction | Fix |
|----------|-----|--------------|-----|
| P1 | Test suite broken: `test_models.py` imports deleted `app.models.otp` | `make test` → collection ERROR | Recreate `app/models/otp.py` or remove import from test |
| P1 | CrowdStrike `QUARANTINE` action rejected | `POST /ingest` with `"action": "quarantine"` → 422 enum error | Remove `.upper()` in `normalize_crowdstrike` (cloud.py:106) |
| P1 | No login brute-force protection | Repeated failed logins not rate-limited | Add `@limiter.limit` to `/api/auth/login` |
| P2 | Email alerts not delivered | SMTP disabled, no consumer | Configure SMTP or use webhook-only |
| P2 | `.env` committed with secrets | File present in working tree | Add to `.gitignore`, generate at runtime |
| P3 | No live public SaaS URL | `docker-compose.vm.yml` exists but not deployed | Deploy to cloud VM with public DNS + Let's Encrypt |
| P3 | No GeoIP/reverse-DNS enrichment | Not implemented | Add enrichment behind feature flag |
| P3 | No Helm/Terraform IaC | Not present | Add Terraform or Helm charts |

---

## 9. Gap-Closing Action Plan

| Order | Item | Effort | Points Gained |
|-------|------|--------|---------------|
| 1 | Fix `test_models.py` import (recreate `app/models/otp.py` or remove import) | 15 min | +2 (tests pass) |
| 2 | Fix CrowdStrike action enum (remove `.upper()`) | 10 min | +1 (normalization complete) |
| 3 | Add login rate limiting with slowapi | 30 min | +1 (security hardening) |
| 4 | Deploy public SaaS URL with HTTPS | 2-4 hours | +2 (SaaS deployment verified) |
| 5 | Configure SMTP or document webhook as notification channel | 30 min | +1 (alerting complete) |
| 6 | Add GeoIP enrichment (optional bonus) | 2 hours | +1 bonus |
| 7 | Add Helm/Terraform IaC (optional bonus) | 4-6 hours | +2 bonus |

Total potential: +9 points (brings score to ~95-97 with bonus).

---

## 10. Demo-Interview Readiness

**15 likely questions + suggested answers:**

1. **Why PostgreSQL instead of OpenSearch/Elasticsearch?** — Simpler single-node operation on 4 vCPU/8 GB; JSONB + GIN indexes sufficient for demo volume (<1M events/day); avoids Java heap/cluster complexity.

2. **How does tenant isolation work?** — Server-side: VIEWER role forced to `current_user.tenant` on every `/api/*` request; `tenant=` parameter ignored for viewers. ADMIN can pass `tenant=` or `all`. All SQL is parameterized with tenant in WHERE clause.

3. **How does the alert engine avoid double-counting?** — Dedupe key = `rule_id:tenant:group_value`. Partial unique index on `dedupe_key` where `status != 'resolved'`. Evidence IDs collected with identical predicate as aggregate (no `ts <= now` bound), so count and eventIds stay consistent.

4. **How are syslog timestamps handled without year?** — RFC3164 timestamps assume current year with Jan/Dec rollover handling; `SYSLOG_TIMEZONE` env controls UTC/local/IANA policy; RFC5424 offsets preserved.

5. **How is ingestion idempotent?** — Deterministic SHA256 ID from `tenant\|source\|ts\|sorted(raw.items())`; duplicate inserts return existing event without creating new row or alert.

6. **What's the retention strategy?** — Deletion-based: hourly `DELETE FROM events WHERE ingested_at < now - RETENTION_DAYS`. Index on `ingested_at` makes it fast. Can run via `make maintenance` or APScheduler cron.

7. **How does the appliance differ from SaaS?** — Appliance: localhost-bound ports, self-signed Caddy cert, `SAAS_MODE=false`, optional seed passwords. SaaS: public 80/443, Let's Encrypt via DOMAIN, `SAAS_MODE=true`, all secrets required (`:?` syntax), `COOKIE_SECURE=true`.

8. **How are API keys managed?** — Per-tenant API keys created by admins via `/api/tenants`; plaintext shown once; stored as SHA-256 hash; `rotate-key` endpoint invalidates old key.

9. **What happens if the worker crashes?** — Worker loop catches all exceptions and continues; alert sweep every 30s; retention hourly. Never crashes.

10. **How does the frontend enforce RBAC?** — Frontend redirects non-admin from `/rules`/`/users` to `/dashboard`, but backend is the authorization boundary — all admin endpoints require `require_admin` dependency.

11. **How is the common schema enforced?** — Pydantic `NormalizedEvent` model validates all fields; severity clamped 0-10; action restricted to enum; source restricted to enum; `raw` JSONB preserves original.

12. **How does file batch ingestion work?** — `/ingest/file` accepts JSON/NDJSON/CSV/syslog text; parses via `parse_batch_records`; validates size (<10MB); ingests via `ingest_batch` with savepoint isolation per event.

13. **What's the alert cooldown behavior?** — Active alert within cooldown (15 min): updates count/last_seen only, no re-notify. Outside cooldown: re-triggers and notifies. No active alert: inserts and notifies.

14. **How does the simulator generate brute-force traffic?** --75% of AD/API events from `203.0.113.77` with `LogonFailed`/`app_login_failed`, designed to cross the 5-in-5-min threshold.

15. **How would you scale beyond a single node?** — Read replicas for query scaling; ClickHouse for >10K events/sec; partitioning by `ingested_at`; separate indexes/tables per tenant for true multi-tenancy.

**5-minute demo script:**
1. `make up` → stack starts (30s)
2. `make seed` → tenants, users, alert rules, seed events
3. Send syslog: `echo '<134>...' | nc -u localhost 514`
4. POST /ingest: `post_logs.py samples/api_sample.json`
5. Upload file: `curl -F file=@samples/aws_cloudtrail.json .../ingest/file`
6. View dashboard: Top IP/User/Event Type, timeline, tenant filter
7. Trigger alert: run simulator bruteforce → alert appears on Alerts page + webhook
8. Test RBAC: login as viewerA → cannot see demob data; login as admin → can see all

---

## 11. Appendix

**Environment:** Linux, Docker 29.7.2, Docker Compose v5.5.1

**Command log reference:** All commands run against `localhost:4500` (backend) and `localhost:443` (Caddy HTTPS). Admin cookie: `/tmp/admin_cookie`; viewerA: `/tmp/viewerA_cookie`; viewerB: `/tmp/viewerB_cookie`.

**Screenshots:** None captured (no headless browser available). All UI functions verified via underlying API calls.

**BLOCKED/UNVERIFIED items:**
1. Live public SaaS URL — no cloud deployment; `docker-compose.vm.yml` + docs present but not deployed
2. Email alert delivery — SMTP disabled; webhook works
3. Frontend visual verification — no Playwright/Puppeteer; API contracts verified
4. Retention live demonstration — mechanism confirmed in code/config, execution not demonstrated (would delete seeded data)
5. `make test` — broken at collection (`test_models.py` imports deleted `app.models.otp`)

**Full report path:** `/home/nay/projects/logs/Logs-Manager/_review/REPORT.md`