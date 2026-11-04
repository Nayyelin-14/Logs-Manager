# Migration Roadmap — Express to FastAPI

**Version:** 1.0  
**Date:** 2026-11-03  
**Status:** Design Phase

---

## 1. Phase Overview

| Phase | Focus | Duration | Dependencies |
|-------|-------|----------|--------------|
| **Phase 0** | Project Setup & Baseline | 1-2 days | None |
| **Phase 1** | Database Models & Alembic Baseline | 2-3 days | Phase 0 |
| **Phase 2** | Authentication System | 3-4 days | Phase 1 |
| **Phase 3** | Canonical Taxonomy & Parsers | 3-4 days | Phase 1 |
| **Phase 4** | Ingestion Pipeline (HTTP + Syslog) | 3-4 days | Phase 2, 3 |
| **Phase 5** | Search & Dashboard APIs | 2-3 days | Phase 1, 4 |
| **Phase 6** | Alert Engine & Rules | 3-4 days | Phase 3, 4 |
| **Phase 7** | Email & Background Workers | 2-3 days | Phase 1, 6 |
| **Phase 8** | Retention & Cache Workers | 1-2 days | Phase 1, 7 |
| **Phase 9** | Frontend Integration & Testing | 2-3 days | All phases |
| **Phase 10** | Docker, Deploy, Documentation | 2-3 days | Phase 9 |

**Total Estimated:** 24-35 days

---

## 2. Detailed Phase Breakdown

### Phase 0: Project Setup & Baseline (1-2 days)

#### Tasks
- [ ] Create `backend/` directory structure per `architecture.md`
- [ ] Initialize `pyproject.toml` with dependencies
- [ ] Create `requirements.txt` (pinned versions)
- [ ] Set up `Dockerfile` (multi-stage)
- [ ] Configure `docker-compose.yml` for FastAPI backend
- [ ] Set up `pytest` + `pytest-asyncio` + `httpx`
- [ ] Configure `ruff` (lint) + `mypy` (type check) + `black` (format)
- [ ] Create `.env.example` with all required variables
- [ ] Set up pre-commit hooks
- [ ] Verify existing Express backend still runs

#### Deliverables
- Runnable FastAPI skeleton (`uvicorn app.main:app --reload`)
- Passing CI pipeline (lint, typecheck, test)
- Docker Compose starts all services

#### Acceptance Criteria
- `make dev` starts FastAPI on :4500
- `make test` passes (empty test suite)
- `make lint` / `make typecheck` pass

---

### Phase 1: Database Models & Alembic Baseline (2-3 days)

#### Tasks
- [ ] Write SQLAlchemy models matching Prisma schema exactly (`app/models/`)
  - Use actual identifier names (e.g., `"User"`, `security_logs`), let SQLAlchemy handle quoting
  - Replicate all indexes, enums, constraints exactly
- [ ] Configure Alembic for async (`migrations/env.py`)
- [ ] Generate baseline migration: `alembic revision --autogenerate -m "baseline_from_prisma"`
- [ ] **Verify baseline is empty** (no `op.create_table`, no `op.add_column`)
- [ ] Stamp baseline: `alembic stamp head`
- [ ] Verify `alembic current` shows baseline revision
- [ ] Create test database fixture (docker-compose.test.yml)
- [ ] Write migration test: verify baseline produces no changes

#### Critical Verification
```bash
# This MUST produce empty upgrade()/downgrade()
alembic revision --autogenerate -m "verify_baseline"
cat migrations/versions/xxx_verify_baseline.py
# Should only have: def upgrade(): pass / def downgrade(): pass
```

#### Deliverables
- `app/models/` with all 5 models + enums
- `migrations/` with baseline revision
- Migration test in CI

#### Acceptance Criteria
- Models match existing DB schema exactly (column names, types, indexes, FKs)
- Baseline migration applies cleanly to test DB
- `alembic current` shows baseline revision
- No data loss risk

---

### Phase 2: Authentication System (3-4 days)

#### Tasks
- [ ] Implement `app/core/security.py` (JWT, bcrypt, tokens)
- [ ] Implement `app/core/dependencies.py` (auth dependencies)
- [ ] Implement `app/core/config.py` (Pydantic Settings)
- [ ] Create auth schemas (`app/schemas/auth.py`)
- [ ] Implement `app/api/routes/auth.py` with all 6 endpoints:
  - `POST /api/auth/login`
  - `POST /api/auth/register`
  - `POST /api/auth/verify-Otp`
  - `POST /api/auth/confirm-password`
  - `POST /api/auth/logout`
  - `GET /api/auth/auth-check`
- [ ] Implement OTP storage/service (`app/services/auth_service.py`)
- [ ] Implement email queue integration (`enqueue_otp_email`)
- [ ] Port email templates (`app/core/templates.py`)
- [ ] Write unit tests for token creation/verification
- [ ] Write integration tests for full auth flow

#### Key Compatibility Requirements
- ✅ Exact JWT payload structure
- ✅ Exact cookie names (`accessToken`, `refreshToken`)
- ✅ Exact cookie options (HttpOnly, Secure, SameSite, max-age)
- ✅ Exact refresh flow (auto-refresh on expired access token)
- ✅ Exact OTP flow (register → verify-Otp → confirm-password)
- ✅ Exact error messages and codes

#### Deliverables
- Working auth endpoints
- OpenAPI spec includes auth endpoints
- All auth tests passing

#### Acceptance Criteria
- Frontend login works against FastAPI (cookies set correctly)
- Token refresh works transparently
- OTP registration → verification → password set works
- Logout clears cookies
- `/api/auth/auth-check` returns user data

---

### Phase 3: Canonical Taxonomy & Parsers (3-4 days)

#### Tasks
- [ ] Port `canonicalEvents.ts` → `app/parsers/canonical.py` (1:1)
- [ ] Port `helpers.ts` → `app/parsers/helpers.py`
- [ ] Port `structured.ts` → `app/parsers/structured.py` (3 normalizers)
- [ ] Port `cloud.ts` → `app/parsers/cloud.py` (2 normalizers)
- [ ] Port `identity.ts` → `app/parsers/identity.py` (2 normalizers)
- [ ] Create `NormalizationService` router (`app/parsers/router.py`)
- [ ] Write unit tests for all 7 normalizers (port existing tests)
- [ ] Write tests for canonical mapping
- [ ] Verify test parity with Express test suite

#### Test Coverage Targets
| Parser | Tests Ported |
|--------|--------------|
| Firewall/Syslog | 2+ |
| Network/Router | 1+ |
| Generic API | 1+ |
| CrowdStrike | 1+ |
| AWS CloudTrail | 1+ |
| Microsoft 365 | 1+ |
| Active Directory | 2+ |
| Canonical mapping | 5+ |
| Batch parsing | 3+ |

#### Deliverables
- `app/parsers/` with all modules
- Full parser test suite passing
- NormalizationService integrated

#### Acceptance Criteria
- All existing parser tests pass (ported 1:1)
- Sample log files from `samples/` parse correctly
- Canonical event types match Express output exactly

---

### Phase 4: Ingestion Pipeline (3-4 days)

#### Tasks
- [ ] Implement `app/services/ingest_service.py` (orchestration)
- [ ] Implement `app/api/routes/ingest.py`:
  - `POST /api/ingest` (single)
  - `POST /api/ingest/batch` (array + file upload)
- [ ] Implement API key auth dependency (`verify_api_key`)
- [ ] Implement Syslog UDP listener (`app/integrations/syslog.py`)
- [ ] Implement Syslog TCP listener
- [ ] Integrate normalization → DB insert → alert evaluation → cache invalidation
- [ ] Port batch parsing (`app/integrations/batch.py`)
- [ ] Write ingestion integration tests

#### Key Compatibility Requirements
- ✅ Same response format: `{ success, ingested, rejected, results[] }`
- ✅ Same tenant resolution (API key bound tenant, never trust event.tenant)
- ✅ Same source inference logic
- ✅ Same file format support (JSON, JSONL, CSV)
- ✅ Same validation errors
- ✅ Syslog on container port 5514 (host 514 → 5514)

#### Deliverables
- Working ingestion endpoints
- Syslog listeners running
- Batch/file upload working

#### Acceptance Criteria
- `samples/post_logs.py` works against FastAPI
- `samples/send_syslog.sh` works (UDP + TCP)
- All 7 source types ingest correctly
- Events appear in database with correct normalization
- Alert evaluation triggers on ingestion

---

### Phase 5: Search & Dashboard APIs (2-3 days)

#### Tasks
- [ ] Implement `app/api/routes/search.py` → `GET /api/get-logs`
- [ ] Implement `app/api/routes/dashboard.py`:
  - `GET /api/dashboard` (admin)
  - `GET /api/user-dashboard/{userId}` (viewer)
- [ ] Implement `app/services/log_service.py` (queries)
- [ ] Port all 18 dashboard aggregations
- [ ] Implement cursor pagination
- [ ] Implement tenant scoping (VIEWER locked to own tenant)
- [ ] Write integration tests for search and dashboard

#### Key Compatibility Requirements
- ✅ Exact query parameter names
- ✅ Exact response JSON structure
- ✅ Same cursor pagination format
- ✅ Same severity → severityLevel mapping
- ✅ Same tenant scoping behavior

#### Deliverables
- Working search and dashboard endpoints
- Dashboard returns all 18 data sections

#### Acceptance Criteria
- Frontend Dashboard loads with real data
- LogsPage infinite scroll works
- Filters (source, severity, eventType, date, search) work
- VIEWER sees only own tenant data

---

### Phase 6: Alert Engine & Rules (3-4 days)

#### Tasks
- [ ] Implement `app/services/alert_service.py` (evaluation engine)
- [ ] Implement `app/api/routes/rules.py` (CRUD)
- [ ] Implement `app/api/routes/alerts.py`:
  - `GET /api/get-alerts`
  - `PATCH /api/alerts/{id}`
- [ ] Port all 5 condition types:
  - `event_type` (canonicalEventType matching)
  - `severity_min`
  - `field_value`
  - `threshold_count`
  - `repeated_failures` (cross-source)
- [ ] Implement deduplication (dedupeKey + window)
- [ ] Implement email queueing on alert creation
- [ ] Write alert engine tests (port existing + new)

#### Key Compatibility Requirements
- ✅ `repeated_failures` counts across AD, API, M365 failure types
- ✅ Same dedupeKey format
- ✅ Same cooldown window behavior
- ✅ Same alert response structure with rule join
- ✅ Rule CRUD validation identical

#### Deliverables
- Working alert engine
- Working rule CRUD
- Alert listing with pagination

#### Acceptance Criteria
- Brute-force rule triggers on 5 failures in 5 min
- Malware detection (severity >= 8) triggers
- Cooldown prevents duplicate alerts
- Frontend AlertsPage loads and resolves alerts
- RulesPage CRUD works

---

### Phase 7: Email & Background Workers (2-3 days)

#### Tasks
- [ ] Implement `app/integrations/email.py` (aiosmtplib) with separate toggles
- [ ] Implement `app/workers/email_worker.py` (arq) with idempotent tracking
- [ ] Implement email notification tracking model (`email_notifications`) with stable IDs + unique constraint
- [ ] Add notification record creation in alert service
- [ ] Configure arq worker settings
- [ ] Test email delivery (Gmail SMTP)
- [ ] Test retry behavior and idempotency
- [ ] Verify email templates match Express

#### Key Compatibility Requirements
- ✅ Same HTML email templates
- ✅ Same subject lines
- ✅ Same recipient logic (event user → tenant admin)
- ✅ Same retry policy (3 attempts, exponential backoff)
- ✅ Email failure doesn't block ingestion/alert creation
- ✅ **Separate toggles**: `SMTP_ENABLED`, `OTP_EMAIL_ENABLED`, `ALERT_EMAIL_ENABLED`
- ✅ **Idempotent notifications**: stable IDs, unique constraint, no duplicate emails on retry

#### Deliverables
- Email worker running
- Notification tracking in DB with stable IDs
- Emails delivered via Gmail SMTP

#### Acceptance Criteria
- OTP emails sent on registration
- Alert emails sent on trigger
- Failed emails retry and log errors
- Notification records created with status
- No duplicate emails on worker retry
- Each email type independently toggleable

---

### Phase 8: Retention & Cache Workers (1-2 days)

#### Tasks
- [ ] Create `ingested_at` migration (multi-step, after Phase 1 baseline confirmed):
  1. Add column nullable, no default
  2. Backfill using `created_at` (migration-time fallback for edge cases)
  3. `ALTER COLUMN` add DEFAULT now() + NOT NULL
  4. Create index
- [ ] Implement `app/workers/retention_worker.py` (APScheduler)
- [ ] Implement `app/workers/cache_worker.py` (arq)
- [ ] Update retention to use `ingested_at`
- [ ] Test retention cleanup
- [ ] Test cache invalidation

#### Migration for `ingested_at`
```bash
# After Phase 1 baseline is confirmed
alembic revision -m "add_ingested_at_to_security_logs"
# Edit generated migration with multi-step approach:
# 1. op.add_column(nullable=True, no default)
# 2. op.execute("UPDATE ... SET ingested_at = COALESCE(created_at, <migration_time>) WHERE ingested_at IS NULL")
# 3. op.alter_column(server_default=sa.text('now()'), nullable=False)
# 4. op.create_index(...)
alembic upgrade head
```

#### Acceptance Criteria
- Retention job runs daily at 05:00
- Deletes events where `ingested_at > 7 days`
- Sample data with old timestamps not deleted (expires 7 days after `created_at`)
- Cache invalidation works on ingestion

---

### Phase 9: Frontend Integration & Testing (2-3 days)

#### Tasks
- [ ] Update `frontend/lms/.env` → `VITE_API_URL=http://localhost:4500/api`
- [ ] Generate TypeScript types from OpenAPI: `npx openapi-typescript http://localhost:4500/openapi.json -o src/types/api.generated.ts`
- [ ] Update frontend API hooks to use generated types
- [ ] Run full frontend against FastAPI backend
- [ ] Fix any contract mismatches
- [ ] Run smoke tests (`tests/smoke.sh`)
- [ ] Run integration test suite
- [ ] Run parser tests
- [ ] Run tenant isolation tests
- [ ] Run alert engine tests

#### Test Execution
```bash
# Backend tests
cd backend && pytest -v --tb=short

# Frontend tests
cd frontend/lms && npm run test

# Smoke tests
cd tests && ./smoke.sh

# Integration tests (full stack)
docker compose -f docker-compose.test.yml up --abort-on-container-exit
```

#### Acceptance Criteria
- All frontend pages load and function
- Login/logout works
- Dashboard shows real data
- Log ingestion → search → alert → email flow works
- Tenant isolation enforced
- All automated tests pass

---

### Phase 10: Docker, Deploy, Documentation (2-3 days)

#### Tasks
- [ ] Finalize `docker-compose.yml` with all services
- [ ] Add Caddy reverse proxy for HTTPS (SaaS)
- [ ] Configure health checks for all services
- [ ] Write `docs/setup_appliance.md` (local deployment)
- [ ] Write `docs/setup_saas.md` (cloud deployment)
- [ ] Write `docs/api_documentation.md` (from OpenAPI)
- [ ] Write `docs/email_configuration.md`
- [ ] Write `docs/testing.md`
- [ ] Create Postman collection
- [ ] Create demo scripts (`scripts/demo.sh`)
- [ ] Verify appliance deployment: `docker compose up --build -d`
- [ ] Verify SaaS deployment with real domain + TLS

#### Deliverables
- Production-ready Docker Compose
- Complete documentation set
- Working demo scripts

#### Acceptance Criteria
- `docker compose up --build -d` starts all services healthy
- Appliance accessible on port 8080
- SaaS deployment serves HTTPS on custom domain
- Health checks pass for all services
- Documentation complete and accurate

---

## 3. Dependency Graph

```
Phase 0
    │
    ├──► Phase 1 (Database Models)
    │         │
    │         ├──► Phase 2 (Auth) ◄──┐
    │         │                      │
    │         ├──► Phase 3 (Parsers) │
    │         │                      │
    │         └──► Phase 4 (Ingest)──┤
    │                   │            │
    │                   ├──► Phase 5 (Search/Dashboard)
    │                   │
    │                   ├──► Phase 6 (Alerts/Rules)
    │                   │            │
    │                   │            └──► Phase 7 (Email/Workers)
    │                   │                        │
    │                   └──► Phase 8 (Retention)──┘
    │                                    │
    └────────────────────────────────────┴──► Phase 9 (Frontend Integration)
                                                  │
                                                  └──► Phase 10 (Deploy/Docs)
```

---

## 4. Risk Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Database schema drift | High | High | Baseline migration verification; test DB restore in CI |
| Auth cookie mismatch | High | High | Side-by-side testing with Express; exact cookie inspection |
| Parser behavior divergence | Medium | High | 1:1 test port; sample log validation |
| Alert engine logic change | Medium | High | Port tests first; property-based testing |
| Frontend API contract break | Medium | High | OpenAPI type generation; contract tests |
| Syslog port permissions | Low | Medium | Container port 5514; host mapping |
| Email delivery failures | Low | Low | Retry + dead letter logging; async queue |
| Migration data loss | Low | Critical | Backup before each migration; test rollback |

---

## 5. Go/No-Go Criteria Per Phase

| Phase | Go Criteria |
|-------|-------------|
| Phase 1 | Baseline migration empty; models match DB; tests pass |
| Phase 2 | Frontend login works; cookies set; refresh works; OTP flow works |
| Phase 3 | All parser tests pass; sample logs parse identically |
| Phase 4 | `post_logs.py` + `send_syslog.sh` work; events in DB; alerts trigger |
| Phase 5 | Dashboard loads; LogsPage works; filters work; tenant scoping correct |
| Phase 6 | Brute-force triggers; malware triggers; cooldown works; rules CRUD works |
| Phase 7 | OTP emails arrive; alert emails arrive; retries work; notifications tracked |
| Phase 8 | Retention deletes by `ingested_at`; cache invalidates |
| Phase 9 | All frontend features work; smoke tests pass; all tests green |
| Phase 10 | `docker compose up` works; appliance + SaaS deploy; docs complete |

---

## 6. Rollback Plan

If any phase fails critically:

1. **Stop** — Don't proceed to next phase
2. **Analyze** — Root cause in isolation
3. **Fix** — In current phase branch
4. **Re-test** — Full phase test suite
5. **Only then proceed**

**Emergency Rollback (Production):**
```bash
# Database
alembic downgrade -1  # or specific revision
pg_restore -d logs_manager backup.dump

# Application
docker compose pull  # previous image tags
docker compose up -d
```

---

**End of Migration Roadmap**