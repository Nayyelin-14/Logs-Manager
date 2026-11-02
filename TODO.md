# LMS Project Completion Plan

Gap analysis and actionable checklist to bring the project in line with the
Full-Stack Developer (Intern) Practical Assignment.

Estimated current score: **~45-55 / 100**.
Minimum pass: 60. Strong hire: 85+.
The main blockers are ingestion breadth, deployment, TLS, samples, and a few
demo-breaking bugs.

How to use this file: work top-down. P0 items are required to pass the
acceptance checklist at all. P1 earns the remaining core points. P2 is polish
and bonus. Tick items off as they are completed.

---

## P0 - Blockers (cannot demo or pass without these)

### 1. Ingestion: more protocols and sources (20 pts)

- [x] Add a **Syslog UDP listener** (port 514) using Node `dgram` in `backend/src/ingest/udp.ts`.
- [x] Add a **Syslog TCP listener** (port 514) using Node `net` in `backend/src/ingest/tcp.ts`.
- [x] Parse RFC3164 / key-value syslog into fields (`priority`, `timestamp`, `host`, `vendor`, `product`, `action`, `src`, `dst`, `spt`, `dpt`, `proto`, `msg`, `policy`, `if`, `event`, `mac`, `reason`).
- [x] Feed parsed syslog through the existing `NormalizationService` and persist as `SecurityEvent` (reuse the ingest controller logic).
- [x] Accept `source: "syslog"` and `source: "firewall"` aliases; map them to `Source.FIREWALL`. Currently rejected by `body("source").isIn(Object.values(Source))` in `backend/src/controllers/admin/logs.con.ts:42`.
- [x] Add **file/batch ingestion** `POST /api/ingest/batch` using `multer` (already a dependency): accept JSON array, JSONL, and CSV.
- [x] Add an **API-key authentication path** for machine senders (`X-API-Key` header) so Syslog/agents/file uploads do not need a browser JWT cookie.
- [x] Ensure at least **4 sources actually work end-to-end**: Syslog firewall, HTTP JSON API, CrowdStrike JSON, AWS CloudTrail, M365 audit, AD 4625. Sample files count as working sources.
- [x] Add a CSV/JSON mapping for CrowdStrike, AWS, M365, AD if they are uploaded as files.

### 2. Samples and sender scripts

- [x] Create `/samples/syslog_firewall.log` (the `<134>...` firewall example).
- [x] Create `/samples/syslog_network.log` (the `<190>...` router example).
- [x] Create `/samples/crowdstrike.json` (malware_detected example).
- [x] Create `/samples/aws_cloudtrail.json` (CreateUser example).
- [x] Create `/samples/m365_audit.json` (UserLoggedIn example).
- [x] Create `/samples/ad_4625.json` (LogonFailed Event ID 4625 example).
- [x] Create `/samples/send_syslog.sh` using `logger` / `nc -u` / `nc`.
- [x] Create `/samples/post_logs.py` to send single and batch JSON over HTTP.
- [x] Add a short `/samples/README.md` with exact commands.

### 3. Deployment (10 pts)

- [ ] Create `backend/Dockerfile` (multi-stage: build TS, run `dist/index.js`, run workers).
- [ ] Create `frontend/lms/Dockerfile` (build with Vite, serve with nginx).
- [ ] Create `docker-compose.yml` with: `postgres`, `redis`, `api`, `email-worker`, `cache-worker`, `frontend`, reverse proxy.
- [ ] Expose ports `80/443` (HTTP/HTTPS), `4500` (API), `514/udp`, `514/tcp` (syslog).
- [ ] Add healthchecks and `depends_on` ordering for postgres/redis before api/workers.
- [ ] Add persistent volumes for Postgres and Redis.
- [ ] Add a seed step / service that runs `npm run seed` after migrations.
- [ ] Create `Makefile` with targets: `up`, `down`, `build`, `logs`, `seed`, `migrate`, `test`.
- [ ] Or create `run.sh` if a Makefile is not preferred.
- [ ] Write `docs/setup_appliance.md`: Ubuntu 22.04+ prerequisites, open ports, one-command start, verification steps.
- [ ] Update `docs/setup_saas.md`: correct env names (`VITE_API_URL`, `ACCESS_TOKEN_SECRET`, `REFRESH_TOKEN_SECRET`, `REDIS_URL`, `GMAIL_*`), remove `JWT_SECRET`/`NEXT_PUBLIC_API_URL`.
- [ ] Add TLS for SaaS: Caddy or nginx + Let's Encrypt, or documented self-signed cert profile.
- [ ] Add a `docker-compose.prod.yml` or Caddy profile for HTTPS.

### 4. Alerting demo path (10 pts)

- [ ] Wire `frontend/lms/src/AppComponents/Forms/RuleForm.tsx` to `POST /api/create-alertRule` (currently `TODO: call API` at line 46).
- [ ] Align condition types between UI and engine: UI uses `threshold_count`, engine expects `repeated_failures` (`backend/src/utils/alertService.ts:57`). Pick one naming and use it everywhere.
- [ ] Add a dedicated Alerts page and `GET /api/get-alerts` endpoint (currently missing; docs claim it exists).
- [ ] Add a reliable notification channel. Prefer a generic **webhook** plus optional email; Gmail-only is brittle for a demo.
- [ ] Send alert notifications to tenant admins when `event.user` does not match a local user. Currently alert creation throws when the user is missing (`backend/src/utils/alertService.ts`).
- [ ] Make sure the demo alert rule + demo log data actually trigger: seed a rule (e.g. repeated failed logins from same IP within 5 min) and seed matching events.
- [ ] Verify alert shows in UI (toast/list) and optionally email/webhook.

### 5. Demo data / retention

- [ ] Change `backend/src/config/sampleData.ts` timestamps from hardcoded `2025-08-20` to **relative dates** (`now - 1..7 days`).
- [ ] Seed a demo user matching sample events (`alice`) so alerts and viewer dashboard have data.
- [ ] Seed at least one alert rule.
- [ ] Confirm the cleanup job (`backend/src/scripts/logCleanUp.ts`) does not immediately delete seeded/demo data.
- [ ] Change cleanup schedule from weekly Monday 5 AM to daily (`backend/src/app.ts:58`) to match docs and retention expectations.

---

## P1 - Core correctness and scoring

### 6. Normalization / schema (10 pts)

- [x] Accept both **snake_case (assignment examples)** and camelCase in `backend/src/utils/normalize.ts`:
  - `@timestamp`, `event_type`, `event_subtype`, `src_ip`, `src_port`, `dst_ip`, `dst_port`, `http_method`, `status_code`, `rule_name`, `rule_id`, `event_id`, `logon_type`, `cloud.account_id`, `cloud.region`, `cloud.service`.
- [x] Current code reads `event.eventType`, `event.srcIp`, `event.event_id`, `event.login_type`; assignment samples use `event_type`, `src_ip`, `event_id`, `logon_type`. The sample payloads normalize to `api_event` / `ad_event` instead of the intended type.
- [x] Add `vendor`/`product` mapping where available.
- [x] Preserve the full original message in `raw` for every source.
- [ ] Document the canonical schema mapping in `docs/architecture.md`.
- [x] Add tests for each source mapping.

### 7. Storage and query (10 pts)

- [ ] Add GIN/trigram/full-text indexes for search fields (`user`, `description`, `srcIp`, `eventType`) or a `tsvector` column.
- [ ] Add `from` / `to` time-range query params for logs (currently only a single `date`).
- [ ] Handle `eventType` as a server-side filter (frontend sends it; backend ignores it).
- [ ] Use exact tenant match instead of `contains` (`backend/src/controllers/admin/logs.con.ts:267`).
- [ ] Fix cursor pagination consistency: order by `timestamp` + `id` if logs can be backfilled with older timestamps.
- [ ] Fix the `severity` filter typing (`SecurityEventFilters.severity` is typed `number` in frontend but sent as `low|medium|high`).
- [ ] Optional: partition/rollover for retention instead of only delete.

### 8. Dashboard/UI (10 pts)

- [ ] Add a time-range filter to the logs table (not only date picker).
- [ ] Implement the "Edit" user button (currently a no-op in `frontend/lms/src/AppComponents/Tables/UserManagementTable.tsx`).
- [ ] Fix frontend filter invalidation: several components create a **local** `new QueryClient()` instead of using the shared `queryClient`, so invalidations do nothing (`LogsTable.tsx`, `RulesTable.tsx`).
- [ ] Show normalized `event_type`/source details in a log detail dialog (raw + normalized).
- [ ] Ensure Viewer/User dashboard only requests own-tenant data and never hits admin endpoints.
- [ ] Fix the admin `/login` redirect loop in `frontend/lms/src/router/loaders/index.ts:25` (admin should redirect to `/`, not `/login`).

### 9. Security, AuthN/AuthZ, tenant isolation (10 pts)

- [ ] Enforce tenant on ingest: tenant must match the JWT tenant claim or the tenant bound to the API key.
- [ ] Fix Viewer log filtering: filter by tenant, not by `user.username` (`backend/src/controllers/admin/logs.con.ts:273`).
- [ ] Fix delete-log authorization: it compares the requester's id to their own id, so non-admins always pass (`logs.con.ts:538-539`). Compare against the log’s owner/tenant.
- [ ] Check user `status` (`ACTIVE`/`FREEZE`/`INACTIVE`) at login.
- [ ] Remove or fix dead `requireTenant` code that references non-existent `req.user.tenants`.
- [ ] Re-enable rate limiting (`app.ts` has it commented out) and make it env-configurable.
- [ ] Make CORS origin env-driven instead of hardcoded `http://localhost:5173` + `https://yourdomain.com` (`backend/src/app.ts:15`).
- [ ] Fix `authorization.ts`: `checkUserIfNotExist(user)` is not awaited (unhandled rejection).
- [ ] Fix `isAuth` + `refreshToken`: errors passed to the internal no-op `next` are silently swallowed.
- [ ] Document role mapping: assignment says Admin/Viewer, project uses `ADMIN`/`USER`.
- [ ] Remove committed `frontend/lms/.env`; add `frontend/lms/.env.example`.
- [ ] Consolidate `new PrismaClient()` instances into one singleton module.
- [ ] Unify port config: backend default `8080`, docs `3000`, root/frontend `4500`. Pick `4500`.
- [ ] Remove overclaims from `README.md` (Syslog/agents/rate limiting/`get-alerts`/retention that are not implemented yet).

### 10. Alerting correctness

- [ ] Fix duplicate alert-rule check: `getExistedAlertRule` returns an array and `checkExistedAlertRule` throws only when falsy, so duplicates are never blocked (`backend/src/utils/alert.util.ts:4`, `backend/src/controllers/admin/alert.con.ts:67-68`).
- [ ] Validate alert-rule tenant against the admin's tenant.
- [ ] Return a clear alert object and prevent partially-created alerts when notification setup fails.
- [ ] Add alert status lifecycle (open/acknowledged/closed) if time permits.

### 11. Docs and deliverables

- [ ] Rewrite `docs/architecture.md` so the data flow matches reality (Syslog UDP/TCP + HTTP + file batch -> normalize -> Postgres, Redis cache, BullMQ workers).
- [ ] Explain the tenant model (claim vs body vs header) and isolation enforcement.
- [ ] Add technology-choice rationale.
- [ ] Add `docs/setup_appliance.md`.
- [ ] Add `docs/demo_script.md` for the 30-minute video (architecture -> ingest -> search -> dashboard -> alert).
- [ ] Add `/postman/LMS.postman_collection.json` covering auth, ingest, ingest batch, get logs, rules, alerts.
- [ ] Add root `README.md` quick start that matches the actual commands.
- [ ] Add `.env.example` at repo root covering all backend + frontend variables.

### 12. Tests and DX (5 pts)

- [ ] Keep the existing Jest tests (`backend/src/__tests__/user_login.test.ts`, `create_alert_rule.test.ts`).
- [x] Add normalization tests for all 6 sources (snake_case + camelCase).
- [ ] Add an integration test: ingest -> query -> alert triggered.
- [ ] Add RBAC/tenant-isolation tests (Viewer cannot read another tenant).
- [ ] Add frontend test setup (Vitest + Testing Library) or document it as not covered.
- [ ] Add a root `/tests/` folder if the grader expects that location.
- [ ] Add `Makefile`/`run.sh` with lint, test, build, seed.
- [ ] Add GitHub Actions CI: install, lint, test, build (backend + frontend).
- [ ] Add a `health` endpoint (`/healthz`) for compose/deploy checks.

---

## P2 - Bonus (+10 max)

- [ ] True multi-tenancy: per-tenant schema/table/partition or separate index.
- [ ] Field-level RBAC (e.g. hide raw payloads from Viewer).
- [ ] Enrichment during ingestion: GeoIP, reverse DNS.
- [ ] IaC: Terraform/Helm.
- [ ] Observability: metrics, request tracing, structured logs.
- [ ] Hardening: secrets management, cookie flags review, CSRF strategy, dependency audit.
- [ ] Export logs (CSV/JSON) and saved searches.

---

## Bug list (quick reference)

- [ ] `frontend/lms/src/router/loaders/index.ts:25` - admin login redirect loop.
- [ ] `backend/src/controllers/admin/logs.con.ts:273` - Viewer filtered by username, not tenant.
- [ ] `backend/src/controllers/admin/logs.con.ts:538-539` - delete-log ownership check is a no-op.
- [ ] `backend/src/utils/alert.util.ts:4` + `alert.con.ts:67` - duplicate rule check inverted.
- [ ] `frontend/lms/src/AppComponents/Forms/RuleForm.tsx:46` - create-rule API not called.
- [ ] `frontend/lms/src/AppComponents/Tables/LogsTable.tsx` / `RulesTable.tsx` - local `QueryClient` makes invalidation useless.
- [ ] `backend/src/controllers/admin/logs.con.ts:42` - `source: "syslog"` rejected.
- [ ] `backend/src/utils/normalize.ts` - snake_case sample fields ignored.
- [ ] `backend/src/controllers/auth/auth.con.ts` - login does not check user status.
- [ ] `backend/src/utils/alertService.ts` - email depends on `event.user` existing locally; Gmail-only.
- [ ] `backend/src/app.ts:58` - cleanup weekly vs documented daily.
- [ ] `backend/src/config/sampleData.ts` - hardcoded old timestamps.
- [ ] `backend/src/app.ts:15` - hardcoded CORS whitelist.
- [ ] `backend/src/middleware/authorization.ts` - missing `await` on `checkUserIfNotExist`.
- [ ] `backend/src/middleware/isAuth.ts` + `utils/refreshToken.ts` - swallowed refresh errors.
- [ ] `backend/src/index.ts:7` / docs / frontend `.env` - port mismatch.
- [ ] Multiple `new PrismaClient()` across files.
- [ ] Committed `frontend/lms/.env`.
- [ ] `README.md` claims features that are not implemented.

---

## Acceptance checklist mapping

- [ ] Appliance starts with one command.
  - Requires: Dockerfiles, `docker-compose.yml`, `Makefile`, `docs/setup_appliance.md`.
- [ ] Send a Syslog message with `logger`/`nc` and see it in the UI within one minute.
  - Requires: UDP/TCP 514 listener, normalization, sample script.
- [ ] `POST /ingest` with sample JSON, then search the record.
  - Requires: snake_case field mapping + auth docs.
- [ ] Upload or point at AWS/M365/AD sample files and verify normalization.
  - Requires: file/batch ingest + sample files.
- [ ] Top N, timeline, tenant/source/time filters work.
  - Requires: eventType/time-range filters, exact tenant filter.
- [ ] Create an alert rule and see a notification (UI/email/webhook).
  - Requires: RuleForm wiring, condition alignment, alerts endpoint/page, webhook or working email.
- [ ] Viewer can see only their own tenant.
  - Requires: tenant isolation fixes in query, ingest, and delete paths.
- [ ] SaaS URL is reachable over HTTPS.
  - Requires: prod compose + TLS proxy + deployment docs.
- [ ] 30-minute demo video recorded.
  - Requires: demo script and working demo data.

---

## Suggested order of work

1. P0.5 demo data + seed fixes (fastest visible win).
2. P0.1 Syslog listener + P0.2 samples (ingestion score).
3. P0.3 Docker/compose/Makefile + appliance docs (deployment score).
4. P0.4 alert UI wiring + alerts endpoint (alerting score).
5. P1.6-9 normalization, filters, tenant isolation, security (core score).
6. P1.11-12 docs, Postman, tests, CI (DX score).
7. P2 bonuses only after the acceptance checklist is green end-to-end.

---

## Definition of done

- Fresh clone + `cp .env.example .env` + `make up` starts the system.
- `python samples/post_logs.py` and `samples/send_syslog.sh` both create visible logs.
- At least 4 sources are demonstrably normalized and searchable.
- Dashboard Top N, timeline, tenant/source/time filters work.
- A rule can be created from the UI and produces a visible/queued notification.
- Viewer account sees only its tenant.
- SaaS instance is reachable over HTTPS.
- Backend and frontend builds pass; tests pass; docs match reality.
