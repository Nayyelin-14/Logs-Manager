# Project Audit Report — Log Manager / Mini SIEM

**Date:** 2026-11-03  
**Auditor:** Senior Software Architect / Senior Python Backend Engineer / DevOps Engineer

---

## 1. Existing Architecture Overview

### 1.1 Repository Structure

```
log-manager/
├── backend/                 # Express.js + TypeScript (current production backend)
│   ├── src/
│   │   ├── config/          # Prisma, Redis, seed data, canonical events
│   │   ├── controllers/     # Route handlers (auth, logs, alerts, users, ingest)
│   │   ├── ingest/          # Syslog UDP/TCP, batch parsing, source detection
│   │   ├── jobs/            # BullMQ queues (email, cache) + workers
│   │   ├── middleware/      # Auth, authorization, ingest auth, rate limiting
│   │   ├── services/        # Business logic (ingest, auth, logs, alerts)
│   │   ├── utils/           # Normalization, alert engine, email, cache, JWT
│   │   ├── types/           # TypeScript types
│   │   ├── generated/       # Prisma client
│   │   ├── scripts/         # Cleanup jobs
│   │   ├── app.ts           # Express app setup
│   │   └── index.ts         # Entry point
│   ├── package.json
│   ├── tsconfig.json
│   └── .env.example
├── frontend/lms/            # React 19 + TypeScript + Vite (KEEP - UI is complete)
│   ├── src/
│   │   ├── api/             # Axios + React Query hooks
│   │   ├── components/      # shadcn/ui components
│   │   ├── pages/           # Dashboard, Logs, Alerts, Rules, Users
│   │   ├── store/           # Zustand stores (auth, filters)
│   │   ├── types/           # TypeScript interfaces
│   │   └── AppComponents/   # Layout, charts, tables, forms
│   └── package.json
├── samples/                 # Sample log files + ingestion scripts
├── docs/                    # Architecture docs, setup guides
├── docker-compose.yml       # Multi-service deployment
├── Makefile
└── README.md
```

### 1.2 Technology Stack (Current)

| Layer | Technology |
|-------|------------|
| **Backend** | Express 5, TypeScript, Node.js |
| **Database** | PostgreSQL (Neon), Prisma ORM |
| **Cache/Queue** | Redis (ioredis), BullMQ |
| **Auth** | JWT (access + refresh tokens), HttpOnly cookies, OTP via Gmail SMTP |
| **Background Jobs** | BullMQ workers (email, cache), node-cron (retention) |
| **Syslog** | Native UDP (dgram) + TCP (net) listeners |
| **Frontend** | React 19, Vite, TypeScript, React Query, Zustand, Tailwind, shadcn/ui, Recharts |

---

## 2. Current Database Schema (Prisma)

### 2.1 Models

| Model | Key Fields | Indexes |
|-------|-----------|---------|
| **User** | id, username, email, password, role (USER/ADMIN), tenant, status | tenant, role, createdAt, status |
| **AlertRule** | id, name, description, tenant, conditions (JSON), enabled, severity | - |
| **Alert** | id, ruleId, tenant, description, triggeredAt, eventIds[], severity, status, title, dedupeKey | (tenant,status), (ruleId,dedupeKey,triggeredAt) |
| **Otp** | id, email, optCode, rememberToken, verifyToken, count, error | email |
| **SecurityEvent** | id, @timestamp, tenant, source, vendor, product, eventType, canonicalEventType, originalEventType, eventSubtype, severity, action, srcIp, srcPort, dstIp, dstPort, protocol, user, host, process, url, httpMethod, statusCode, ruleName, ruleId, cloudAccountId, cloudRegion, cloudService, raw (JSON), tags[], createdAt, updatedAt, ip, user, description, eventId, loginType, priority, sha256, status, interface, mac | 15+ indexes on tenant, timestamp, source, eventType, canonicalEventType, severity, srcIp, user, action, etc. |

### 2.2 Enums

- **Role**: USER, ADMIN
- **Status**: FREEZE, INACTIVE, ACTIVE
- **Action**: ALLOW, DENY, CREATE, DELETE, LOGIN, LOGOUT, ALERT, QUARANTINE, CREATEUSER
- **Source**: FIREWALL, CROWDSTRIKE, AWS, M365, AD, API, NETWORK

---

## 3. Existing Backend Capabilities

### 3.1 Authentication & Authorization

| Feature | Implementation | Status |
|---------|---------------|--------|
| **Login** | Email + password, returns access + refresh tokens in HttpOnly cookies | ✅ Working |
| **Logout** | Clears cookies | ✅ Working |
| **Token Refresh** | Automatic via middleware when access token expired | ✅ Working |
| **OTP Verification** | Gmail SMTP + Nodemailer, stored in Otp table | ✅ Working |
| **Role-based Access** | ADMIN vs USER (VIEWER) | ✅ Working |
| **Tenant Isolation** | Middleware enforces tenant scope for VIEWER role | ✅ Working |
| **API Key Ingestion** | X-API-Key header with tenant binding | ✅ Working |

### 3.2 Log Ingestion Pipeline

| Method | Endpoint/Handler | Status |
|--------|------------------|--------|
| **HTTP Single** | `POST /api/ingest` | ✅ Working |
| **HTTP Batch** | `POST /api/ingest/batch` (JSON, JSONL, CSV) | ✅ Working |
| **File Upload** | Multipart file to `/api/ingest/batch` | ✅ Working |
| **Syslog UDP** | Port 514 (configurable), dgram socket | ✅ Working (disabled by default) |
| **Syslog TCP** | Port 514 (configurable), net server with octet framing + newline fallback | ✅ Working (disabled by default) |

### 3.3 Source Parsers (7 Implemented)

| Source | Parser Function | Key Fields Mapped | Status |
|--------|----------------|-------------------|--------|
| **Firewall / Syslog** | `normalizeSyslog()` | PRI, facility, severity, timestamp, hostname, msg, key-values (src, dst, spt, dpt, proto, policy, if, mac, event) | ✅ Working |
| **Network / Router** | `normalizeNetwork()` | Extends syslog, parses interface, MAC, link up/down from message | ✅ Working |
| **Generic HTTP API** | `normalizeAPI()` | Snake_case fields (event_type, src_ip, dst_ip, etc.) | ✅ Working |
| **CrowdStrike** | `normalizeCrowdStrike()` | DetectName, ComputerName, UserName, FileName, Severity, SHA256, SourceIpAddress | ✅ Working |
| **AWS CloudTrail** | `normalizeAWS()` | eventName, eventSource, eventTime, awsRegion, sourceIPAddress, userIdentity, recipientAccountId | ✅ Working |
| **Microsoft 365** | `normalizeM365()` | Operation, Workload, UserId, ClientIP, ResultStatus, CreationTime | ✅ Working |
| **Active Directory** | `normalizeAD()` | EventID (4624/4625/4634/4720/4726), TargetUserName, Computer, IpAddress, LogonType, Status | ✅ Working |

### 3.4 Normalization & Canonical Events

- **Central Normalization Service** routes to source-specific normalizers
- **Canonical Event Taxonomy** (`canonicalEvents.ts`) maps 30+ canonical event types with aliases across all 7 sources
- **Original event preserved** in `raw` JSONB field
- **Tags** array for parse errors, parse_error tag on failure
- **Severity mapping**: Syslog PRI → severity (priority % 8), string labels → 0-10 scale

### 3.5 Storage & Search

| API | Endpoint | Features |
|-----|----------|----------|
| **Event Search** | `GET /api/get-logs` | Pagination (cursor), filters (tenant, source, action, severity, eventType, date, search), tenant-scoped for VIEWER |
| **Event Delete** | `DELETE /api/delete-log/:logId` | Admin only |
| **Dashboard Stats** | `GET /api/dashboard` | Total events, top IPs/users/eventTypes, events by source, severity distribution, alerts by day/status/severity, rules by enabled, recent alerts, sources |

### 3.6 Alert Engine

| Feature | Implementation | Status |
|---------|---------------|--------|
| **Rule Storage** | AlertRule model with JSON conditions | ✅ Working |
| **Condition Types** | `event_type`, `severity_min`, `field_value`, `threshold_count`, `repeated_failures` | ✅ Working |
| **Repeated Failures** | Counts auth failures (LOGIN action + severity ≥ 5 OR canonical types ad_logon_failed, login_failed, M365 failures) grouped by srcIp/user/host | ✅ Working |
| **Deduplication** | dedupeKey with configurable window (default 300s) | ✅ Working |
| **Auto-evaluation** | Runs on every ingestion via `AlertService.checkAlerts()` | ✅ Working |
| **Cooldown** | 600s (configurable per rule) | ✅ Partial (uses windowSeconds) |

### 3.7 Email Notifications

| Feature | Implementation | Status |
|---------|---------------|--------|
| **Queue** | BullMQ `email-Queue` with exponential backoff (3 retries) | ✅ Working |
| **Worker** | Separate process (`emailWorker.ts`) | ✅ Working |
| **Templates** | HTML emails for OTP and Alerts | ✅ Working |
| **Trigger** | Queued after alert creation in `AlertService.triggerAlert()` | ✅ Working |
| **SMTP** | Gmail (service: gmail) via Nodemailer | ✅ Working |
| **Recipient** | Event user → tenant admin fallback | ✅ Working |

### 3.8 Background Jobs

| Job | Schedule | Implementation |
|-----|----------|----------------|
| **Log Retention** | Daily 05:00 (node-cron) | Deletes SecurityEvent where `timestamp < 7 days ago` |
| **Cache Invalidation** | On ingestion | BullMQ `cacheQueue` with pattern `logs:*` |
| **Email Worker** | Continuous | BullMQ worker process |
| **Cache Worker** | Continuous | BullMQ worker process |

---

## 4. Existing Frontend Capabilities (KEEP - UI Complete)

### 4.1 Pages

| Page | Route | Components | Data Source |
|------|-------|------------|-------------|
| **Login** | `/login` | AuthForm, OtpForm | `/api/auth/login` |
| **Register** | `/register` | RegisterPage | `/api/auth/register` |
| **OTP** | `/otp` | OtpForm | `/api/auth/verify-otp` |
| **Dashboard** | `/` | DashboardStatsPage (EventPulse, DetectionRail, SourceReadout, RuleReadout, TopIps, RecentLogsTable) | `/api/dashboard`, `/api/get-logs` |
| **Logs** | `/logs` | LogsTable (infinite scroll, filters) | `/api/get-logs` |
| **Alerts** | `/alerts` | AlertsPage (queue + detail panel, resolve action) | `/api/get-alerts`, `PATCH /api/alerts/:id` |
| **Rules** | `/rules` | RulesTable (CRUD) | `/api/get-rules`, CRUD endpoints |
| **Users** | `/users` | UserManagementTable (Admin only) | `/api/get-users`, CRUD endpoints |
| **Analytics** | `/analytics` | Placeholder | - |

### 4.2 State Management

- **Zustand**: `authStore` (user, tenant, role, token), `filterStore` (log/alert filters)
- **React Query**: All server state with caching, invalidation, infinite queries
- **API Layer**: Axios instances (`API`, `adminApi`, `authAPI`) with cookie credentials

### 4.3 UI Components (shadcn/ui + Custom)

- Tables with sorting, pagination, column filtering
- Charts: GradientAreaChart, SourceChart, EventTypeChart, TopUserChart, TopIpPanel
- Forms: MultiSourceLogForm (dynamic fields per source), RuleForm, AuthForm
- Dashboard: Stat cards, severity badges, event timeline, detection rail

---

## 5. Feature Verification Table

| Feature | Frontend | Backend | Database | End-to-End Status |
|---------|----------|---------|----------|-------------------|
| **Login** | ✅ AuthForm, OTP flow | ✅ JWT + cookies, OTP email | ✅ User + Otp models | **Working** |
| **Dashboard** | ✅ DashboardStatsPage (charts, tables) | ✅ `/api/dashboard` with 18 parallel queries | ✅ GroupBy aggregations | **Working** |
| **Log Ingestion (HTTP)** | ✅ MultiSourceLogForm | ✅ `/api/ingest`, `/api/ingest/batch` | ✅ SecurityEvent create | **Working** |
| **Log Ingestion (Syslog UDP)** | ❌ No UI | ✅ UDP listener on :514 | ✅ Same pipeline | **Working (backend only)** |
| **Log Ingestion (Syslog TCP)** | ❌ No UI | ✅ TCP listener on :514 | ✅ Same pipeline | **Working (backend only)** |
| **File Ingestion** | ✅ MultiSourceLogForm (file upload) | ✅ Multer + parseBatchBuffer | ✅ Batch processing | **Working** |
| **Event Search** | ✅ LogsTable (infinite, filters) | ✅ `/api/get-logs` with cursor pagination | ✅ Indexed queries | **Working** |
| **Event Details** | ✅ LogsTable row click → detail | ❌ No detail endpoint | ✅ All fields in model | **Partial (no detail API)** |
| **Dashboard Stats** | ✅ Real-time charts | ✅ Aggregated queries | ✅ GroupBy | **Working** |
| **Alert Generation** | ❌ No trigger UI | ✅ Auto on ingestion | ✅ Alert model | **Working (backend only)** |
| **Alert List** | ✅ AlertsPage (queue + detail) | ✅ `/api/get-alerts` | ✅ Alert + Rule join | **Working** |
| **Alert Acknowledge** | ✅ Resolve button (Admin) | ✅ `PATCH /api/alerts/:id` | ✅ Status field | **Working** |
| **Alert Rules CRUD** | ✅ RulesPage + RuleForm | ✅ CRUD endpoints | ✅ AlertRule model | **Working** |
| **Email Notifications** | ❌ No UI config | ✅ BullMQ queue + worker | ❌ No notification log | **Working (backend only)** |
| **Tenant Isolation** | ✅ VIEWER sees own tenant | ✅ Middleware enforces | ✅ Tenant on all models | **Working** |
| **User Management** | ✅ UsersPage (Admin) | ✅ CRUD endpoints | ✅ User model | **Working** |
| **7-Day Retention** | ❌ No UI | ✅ Cron job at 05:00 | ✅ Deletes by timestamp | **Working** |
| **Syslog UDP/TCP** | ❌ No UI | ✅ Listeners (disabled by default) | ✅ Same pipeline | **Working (needs enable)** |

---

## 6. Working / Partially Working / Broken Features

### 6.1 Working Features (Verified via Code Review + Tests)

1. **Authentication**: Login, logout, JWT refresh, OTP email flow
2. **Role-based Access**: ADMIN vs USER with proper middleware
3. **Tenant Isolation**: VIEWER locked to own tenant on all queries
4. **HTTP Ingestion**: Single + batch (JSON/JSONL/CSV) with API key auth
5. **File Ingestion**: Multipart upload with format detection
6. **7 Source Parsers**: All 7 normalizers implemented and tested
7. **Canonical Event Taxonomy**: 30+ canonical types with cross-source mapping
7. **Event Search**: Cursor pagination, filters, tenant scoping
8. **Dashboard Statistics**: 18 parallel aggregations, real data
9. **Alert Engine**: 5 condition types, deduplication, cross-source repeated_failures
10. **Email Queue**: BullMQ with retries, HTML templates
11. **Background Workers**: Email + cache workers as separate processes
12. **Retention Job**: Daily cron deleting by `timestamp`
13. **Syslog Listeners**: UDP + TCP with RFC3164/RFC5424 parsing
14. **Automated Tests**: Parser, ingestion, tenant scope, alert service tests

### 6.2 Partially Working Features

| Feature | Gap |
|---------|-----|
| **Event Detail API** | No `GET /api/events/:id` endpoint; frontend cannot show full event |
| **Syslog Enabled by Default** | `SYSLOG_ENABLED=false` in docker-compose; needs manual enable |
| **Email Notification Logging** | No persistent record of sent/failed emails; only console logs |
| **Alert Cooldown Config** | Uses `windowSeconds` but no explicit cooldown field on rule |
| **Retention by `ingested_at`** | Currently deletes by original `timestamp` — assignment requires `ingested_at` |
| **Severity Mapping Documentation** | Syslog severity (0-7) vs normalized (0-10) not clearly documented |
| **Frontend Alert Email Config** | No UI to configure SMTP recipients; only env vars |
| **Docker Port 514** | Maps host 514 → container 514 (privileged); should use 5514 internally |

### 6.3 Broken / Missing Features

| Feature | Issue |
|---------|-------|
| **Event Detail View** | Frontend has no detail page/modal; no backend endpoint |
| **SAAS Deployment HTTPS** | Caddy configured but not tested with real certs |
| **Appliance Single Command** | `docker compose up` works but syslog ports need root |
| **Test Coverage** | No integration tests for full frontend→backend flow |
| **Sample Data in Repo** | Samples exist but no automated demo script |
| **API Documentation** | No OpenAPI/Swagger spec generated |
| **Health Checks** | Only `/healthz`; no readiness/liveness for k8s |

---

## 7. Security Vulnerabilities Identified

| Issue | Severity | Location |
|-------|----------|----------|
| **Hardcoded JWT Secrets** | Medium | `.env.example` has placeholders; production must override |
| **Gmail App Password in Env** | Medium | `GMAIL_PASS` in env; should use secret manager in production |
| **Syslog on Privileged Port 514** | Low | Docker maps host 514; container runs as root or needs CAP_NET_BIND_SERVICE |
| **No Rate Limiting on Auth** | Low | `/api/auth/login` has global rate limit but no per-IP/account limit |
| **Cookie Security** | Low | `COOKIE_SECURE=false` in dev; must be `true` in production |
| **No Audit Logging** | Medium | Admin actions (user create/delete, rule changes) not logged |

---

## 8. Integration Problems

| Problem | Impact |
|---------|--------|
| **Frontend expects `/api/dashboard`** | Backend has `/api/dashboard` but frontend query uses `/dashboard?` — need to verify exact path |
| **Frontend uses `/api/get-logs`** | Backend route is `/api/get-logs` — matches |
| **Frontend uses `/api/get-alerts`** | Backend route is `/api/get-alerts` — matches |
| **Frontend uses `/api/get-rules`** | Backend route is `/api/get-rules` — matches |
| **Frontend uses `/api/user-dashboard/:userId`** | Backend has this — matches |
| **Cookie domain mismatch** | Frontend on port 8080, backend on 4500; CORS + cookies must align |
| **Syslog port in Docker** | Host 514 → container 514 requires root; better: host 514 → container 5514 |

---

## 9. Code That Can Be Reused Conceptually (Migration Targets)

| Component | Reuse Strategy |
|-----------|----------------|
| **Prisma Schema** | Migrate to SQLAlchemy + Alembic; keep table/column names |
| **Canonical Event Taxonomy** | Port `canonicalEvents.ts` → Python module 1:1 |
| **Normalization Logic** | Port all 7 normalizers + helpers to Python |
| **Alert Engine** | Port `AlertService` logic to Python (same condition types) |
| **Syslog Parsing** | Port `parseSyslogMessage` + RFC3164/RFC5424 handling |
| **Batch Parsing** | Port `parseBatchBuffer` (JSON/JSONL/CSV) |
| **Source Inference** | Port `inferSourceFromEvent` + `normalizeSourceInput` |
| **Seed Data** | Reuse sample logs + users + rule for Python seeding |
| **Docker Compose** | Keep structure; replace backend image with FastAPI |
| **Frontend** | **ZERO CHANGES** to UI; only update API base URL + response handling if contracts change |

---

## 10. Code That Must Be Replaced

| Component | Replacement |
|-----------|-------------|
| **Express.js App** | FastAPI application |
| **Prisma Client** | SQLAlchemy 2.x async + Alembic |
| **JWT Middleware** | FastAPI dependencies + `python-jose` |
| **BullMQ Queues** | Redis + `arq` or `dramatiq` or custom async worker |
| **node-cron** | `apscheduler` or `croniter` + async task |
| **Nodemailer** | `aiosmtplib` or `smtplib` async |
| **dgram/net Syslog** | `asyncio` UDP/TCP servers |
| **Cookie Parser** | FastAPI `Response.set_cookie` + `Request.cookies` |
| **express-validator** | Pydantic models + FastAPI validation |
| **TypeScript Types** | Pydantic models (shared via OpenAPI) |

---

## 11. Migration Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Database schema drift** | High | High | Use Alembic autogenerate from existing DB; verify with `prisma db pull` first |
| **Cookie/auth breakage** | High | High | Implement exact same JWT payload, cookie names, refresh flow |
| **Syslog port permissions** | Medium | Medium | Use container port 5514, map host 514→5514 |
| **Frontend API contract mismatch** | Medium | High | Generate OpenAPI spec; update frontend types from spec |
| **Alert evaluation timing** | Low | Medium | Keep async evaluation; don't block ingestion |
| **Email delivery reliability** | Low | Low | Keep BullMQ-style retries; add dead letter logging |
| **Retention by `timestamp` vs `ingested_at`** | Medium | Medium | Add `ingested_at` column; migrate retention job |

---

## 12. Recommended Final Architecture (FastAPI)

```
log-manager/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app factory
│   │   ├── core/
│   │   │   ├── config.py           # Pydantic Settings
│   │   │   ├── security.py         # JWT, password hashing
│   │   │   └── dependencies.py     # FastAPI deps (auth, tenant, RBAC)
│   │   ├── api/
│   │   │   └── routes/
│   │   │       ├── auth.py
│   │   │       ├── users.py
│   │   │       ├── ingest.py
│   │   │       ├── search.py
│   │   │       ├── dashboard.py
│   │   │       ├── alerts.py
│   │   │       ├── rules.py
│   │   │       └── sources.py
│   │   ├── models/                 # SQLAlchemy models
│   │   ├── schemas/                # Pydantic request/response
│   │   ├── services/
│   │   ├── repositories/
│   │   ├── parsers/                # 7 source normalizers
│   │   ├── workers/
│   │   │   ├── email_worker.py
│   │   │   ├── retention_worker.py
│   │   │   └── alert_worker.py
│   │   ├── integrations/
│   │   │   ├── email.py
│   │   │   └── syslog.py
│   │   └── utils/
│   ├── migrations/                 # Alembic
│   ├── tests/
│   ├── requirements.txt
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/lms/                   # UNCHANGED
├── samples/
├── docs/
├── docker-compose.yml
├── Makefile
├── .env.example
└── README.md
```

### Key Dependencies (Python)

| Purpose | Library |
|---------|---------|
| Web Framework | `fastapi`, `uvicorn[standard]` |
| ORM | `sqlalchemy[asyncio]`, `alembic`, `asyncpg` |
| Validation | `pydantic`, `pydantic-settings` |
| Auth | `python-jose[cryptography]`, `passlib[bcrypt]` |
| Redis/Queue | `redis`, `arq` (or `dramatiq`) |
| Email | `aiosmtplib` |
| Syslog | `asyncio` (stdlib) |
| Testing | `pytest`, `pytest-asyncio`, `httpx` |
| Config | `python-dotenv` |

---

## 13. Next Steps (Phase Two Onward)

1. **Create `docs/architecture.md`** with detailed FastAPI design decisions
2. **Set up Python backend skeleton** with FastAPI, SQLAlchemy, Alembic
3. **Generate Alembic migration** from existing PostgreSQL schema (preserve data)
4. **Port canonical event taxonomy** → `app/core/canonical_events.py`
5. **Port all 7 normalizers** → `app/parsers/`
6. **Implement auth** (JWT, cookies, refresh, OTP)
7. **Implement ingestion APIs** (HTTP, batch, file, syslog UDP/TCP)
8. **Implement alert engine** with background evaluation
9. **Implement email worker** with `aiosmtplib`
10. **Implement retention worker** using `ingested_at`
11. **Update Docker Compose** for FastAPI backend
12. **Verify frontend integration** (update API base URL only)
13. **Write comprehensive tests** (parser, ingestion, tenant isolation, alerts, email)
14. **Document deployment** (appliance + SaaS)

---

## 14. Appendix: Key Files Reference

### Backend Entry Points
- `backend/src/index.ts` — Main entry, starts Express + syslog
- `backend/src/app.ts` — Express middleware, routes, cron
- `backend/src/routes/index.route.ts` — Route mounting with auth guards

### Core Services
- `backend/src/services/ingest.service.ts` — Ingestion orchestration
- `backend/src/utils/normalize.ts` — Normalization router
- `backend/src/utils/normalization/` — 7 source normalizers
- `backend/src/utils/alertService.ts` — Alert evaluation engine
- `backend/src/services/alert.service.ts` — AlertRule CRUD
- `backend/src/services/auth.service.ts` — User/Otp DB operations

### Auth & Middleware
- `backend/src/middleware/isAuth.ts` — JWT verification + auto-refresh
- `backend/src/middleware/authorization.ts` — Role checks
- `backend/src/middleware/ingestAuth.ts` — API key auth for ingestion
- `backend/src/utils/refreshToken.ts` — Token generation + cookie setting

### Syslog
- `backend/src/ingest/syslog.ts` — RFC3164/RFC5424 parsing + KV extraction
- `backend/src/ingest/udp.ts` — UDP listener
- `backend/src/ingest/tcp.ts` — TCP listener with octet framing

### Workers
- `backend/src/jobs/queues/emailQueue.ts` — BullMQ queue
- `backend/src/jobs/workers/emailWorker.ts` — Email processor
- `backend/src/jobs/workers/cacheWorker.ts` — Cache invalidation

### Database
- `backend/src/generated/prisma/schema.prisma` — Full schema
- `backend/src/config/seed.ts` — Seed script
- `backend/src/config/sampleData.ts` — Sample logs, users, rules

### Frontend Integration
- `frontend/lms/src/api/index.ts` — Axios instances
- `frontend/lms/src/api/query.ts` — React Query hooks
- `frontend/lms/src/types/types.ts` — TypeScript interfaces
- `frontend/lms/src/store/authStore.ts` — Auth state

---

**End of Audit Report**