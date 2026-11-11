# Tests

The backend test suite is in `backend/tests/` and runs with **pytest** (507 tests after moving the standalone `tests_unit/test_tenancy_isolation.py` suite into `backend/tests/unit/`).

## Quick start

```bash
# From repo root
make test          # runs pytest via backend/.venv
# or
cd backend
./.venv/bin/python -m pytest -q
```

## Test structure

| File | Scope |
|------|-------|
| `test_auth_compatibility.py` | JWT payload, bcrypt, cookie options match the legacy backend |
| `test_models.py` | SQLAlchemy models, table names, columns, constraints |
| `test_parsers.py` | Canonical event inference, source resolution |
| `test_http_routes.py` | Cookie auth, login, `/api/get-logs`, `/api/get-alerts`, tenant isolation, admin cross-tenant views |
| `test_ingest_api.py` | Single/batch/file ingestion, API-key auth, tenant enforcement, limits (400/401/403/413) |
| `test_syslog_and_batch.py` | RFC3164/RFC5424 parsing, source aliases, RFC3164 timezone policy, RFC5424 offsets untouched |
| `test_retention.py` | 7-day purge, dry-run, cron parsing, APScheduler integration |
| `test_tenant_isolation.py` | VIEWER sees only own tenant; ADMIN cross-tenant queries; forced tenant scoping |
| `tests/unit/test_tenancy_isolation.py` | Pure unit tests for `normalize_tenant`, `effective_tenant`, role/tenant consistency, and removed `/api/auth/register` route |
| `test_alert_rule.py` | Alert rule CRUD, threshold evaluation, dedupe cooldown |
| `test_functional.py` | End-to-end flow: login → ingest → alert → dashboard |

## Conftest

`backend/tests/conftest.py`:
- Forces a disposable test database `logs_manager_test` on Docker PostgreSQL (never Neon)
- Sets `NullPool` to avoid cross-event-loop connection reuse
- Forces Redis to local Docker Redis
- Disables Syslog listeners (`SYSLOG_ENABLED=false`)
- Runs alembic migrations + seed per test session
- Provides fixtures: `client`, `admin_client`, `viewer_a_client`, `viewer_b_client`, `api_key`, `login()`

## Smoke test

`tests/smoke.sh` exercises a running stack end to end (health, login, single/batch ingest, logs, alerts, dashboard, rules):

```bash
# Appliance defaults (FastAPI stack on 4500/8081)
./tests/smoke.sh

# Or against another deployment
BASE_URL=https://<service>.onrender.com \
INGEST_API_KEY=<key> \
ADMIN_EMAIL=admin@demo.local \
ADMIN_PASSWORD='$SEED_ADMIN_PASSWORD' \
./tests/smoke.sh
```

**Demo credentials (after `make seed`):**
- Printed to stdout during seeding
- Set via `SEED_ADMIN_PASSWORD`, `SEED_VIEWER_A_PASSWORD`, `SEED_VIEWER_B_PASSWORD` env vars

Run `make seed` first so the demo accounts and an alert rule exist.

## CI note

Tests require Docker PostgreSQL and Redis (provided by the root `docker-compose.yml`, not a backend-specific Compose file). A typical CI job would:

```yaml
services:
  postgres:
    image: postgres:18-alpine
    env: { POSTGRES_USER: logs, POSTGRES_PASSWORD: logs_dev_password, POSTGRES_DB: logs_manager_test }
    ports: ["5432:5432"]
  redis:
    image: redis:8-alpine
    ports: ["6379:6379"]
steps:
  - cd backend && pip install -r requirements.txt
  - TEST_DB_PORT=55432 TEST_REDIS_PORT=56379 .venv/bin/python -m pytest -q
```