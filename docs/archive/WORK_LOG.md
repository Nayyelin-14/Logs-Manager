# Work Log — Log Manager Assignment Implementation

## Step 1 — Foundation & Tests (DONE)
- Fixed alembic migration chain: single head `a7b8c9d0e1f2`, verified upgrade/downgrade on empty throwaway DB
- Fixed `app/schemas/normalized_event.py`: Pydantic v2 NormalizedEvent with enums, UTC enforcement, deterministic ID
- Fixed `app/services/ingest_service.py`: tenant resolution before validation, enum handling for action field
- Fixed `app/models/alert.py`: added alert_rules/alerts first-class columns
- Fixed `app/migrations/versions/a7b8c9d0e1f2_alerting_schema.py`: migration of conditions -> structured columns
- Fixed `app/services/alerting/evaluator.py`: tenant='*' handling, GROUP BY with tenant, filter from legacy conditions
- Fixed `app/services/alerting/alerter.py`: timedelta import, tag handling on new alerts
- Fixed `app/models/events.py`: `default=func.now()` + `server_default=func.now()` on ingested_at
- Fixed `app/api/routes/dashboard.py`: handle string source values (not just enum)

## Step 2 — SSL Fix (DONE)
- Created `backend-fastapi/app/core/db_engine.py`: centralized SSL handling helper used by app, alembic, worker, ingest, scripts
- Fixed `app/core/database.py`: uses shared `create_engine()` from `db_engine.py`
- Fixed `migrations/env.py`: uses shared `create_engine()` from `db_engine.py`
- Fixed `scripts/verify_schema.py`: uses shared `create_engine()` from `db_engine.py`
- Root cause: migration/verify code had their own engine args and did not pass `ssl=False` for `sslmode=disable`

## Step 3 — Seed Passwords (DONE)
- `scripts/seed_demo_data.py` reads passwords from `SEED_ADMIN_PASSWORD`, `SEED_VIEWER_A_PASSWORD`, `SEED_VIEWER_B_PASSWORD`
- SaaS mode refuses to seed without explicit passwords; appliance mode can generate random passwords and prints them once

## Step 4 — Worker Embedding (DONE)
- Added `WORKER_EMBEDDED: bool = False` and `SAAS_MODE: bool = False` to config
- Backend starts the worker loop only when `WORKER_EMBEDDED=true`

## Step 5 — Event IDs and Idempotent Ingestion (DONE)
- Deterministic event ID includes tenant, source, timestamp, event type, src/dst IP and port, user, host, event_id, sorted raw
- Duplicate ingestion returns existing `(id, ts)` without creating new row

## Step 6 — .dockerignore (VERIFIED)
- All 4 `.dockerignore` files exist and exclude `.env.local` and `.venv`

## Step 7 — Gate A: Boot Stack and Health (DONE)
- Generated local `.env` from `.env.example` with random secrets

## Step 8 — Gate B: Acceptance Checklist (DONE)
- All 16 acceptance tests PASS

## Step 9 — Additional Fixes (DONE)
- Caddy: replaced directive placeholder with `{$DOMAIN:localhost}`
- Worker healthcheck fixed
- `ingest_service.resolve_source`: source=auto now infers per record
- `stats.py`: fixed undefined `from_str`
- `search.py`: non-admin cross-tenant query returns 403
- `evaluator.py`: aggregate threshold query applies rule's filter
- `helpers.map_aws_verb`: returns valid `CREATE`
- `helpers.map_ad_action`: Windows event 4720 returns valid `CREATE`

## Step 10 — File Size and Image Hygiene (DONE)
- `scripts/check_file_sizes.sh` -> `File size check PASSED`
- Image search for `.env.local` and `.venv` returned no matches
- Frontend build uses `VITE_API_URL=/api`

## Item 1 — Doc Cleanup Verification (COMPLETED)
- Verified no COMPOSE_PROJECT_NAME in user-facing docs
- Verified docker compose commands use correct `-f` flags
- Verified backup/restore uses pg_dump/psql with db service
- Verified no password literals (Admin123/ViewerA123/ViewerB123)
- `/healthz` returns real uptime and database status

## Item 2 — Test Suite (BLOCKED)
- Docker Desktop WSL2 cannot bind to localhost:5432
- Fixed `tests/unit/conftest.py` pytest_plugins error

## Item 3 — Frontend (COMPLETE)
```
$ cd frontend/lms && npm run build
✓ built in 10.59s
# TypeScript compile: 0 errors
```

## Item 4 — Seed, Postman, docs (COMPLETE)
- Updated Postman collection with correct API endpoints
- Updated architecture.md with retention explanation
- All README files verified

## Item 5 — Final Proof (BLOCKED)
- Docker WSL2 port 5432 binding fails
- See docs/FINAL_REPORT.md for details

## Verification Commands

```bash
# No COMPOSE_PROJECT_NAME in user-facing docs:
grep -r "COMPOSE_PROJECT_NAME" docs/setup_appliance.md docs/setup_saas.md README.md DEMO_GUIDE.md
# No output - clean

# No password literals:
grep -rniE "Admin123|ViewerA123|ViewerB123" . --exclude-dir=node_modules --exclude-dir=.venv --exclude-dir=.git
# No output - clean

# healthz returns real uptime:
# Code verified in backend-fastapi/app/api/routes/health.py
# Returns: {"status":"ok","uptime":<seconds>,"timestamp":"<ISO>","database":"connected"}

# Frontend build:
cd frontend/lms && npm run build
# ✓ built in 10.59s, 0 TypeScript errors
```

## Cleanup Verified

```bash
$ docker volume ls --filter 'name=logs_verify' --format '{{.Name}}'
# No output - clean
```