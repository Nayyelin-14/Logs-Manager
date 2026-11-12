# Tests

The backend acceptance suite lives in `backend/tests/` and runs with **pytest**.
It is intentionally curated: **60 test functions / 70 parametrized cases across
11 files**, each pinning a product or security boundary rather than duplicating
unit-level coverage.

## Quick start

```bash
# From repo root (starts nothing; expects the local db/redis from make up)
make test
# or
cd backend
./.venv/bin/python -m pytest -q
```

The suite always uses the disposable `logs_manager_test` database and never
Neon or the appliance database. `make test-deps` starts only PostgreSQL and
Redis.

## Suite layout

| File | Functions | Scope |
| --- | ---: | --- |
| `test_normalization.py` | 9 | Firewall, AWS, CrowdStrike, M365, AD, and network normalizers; canonical event names; outcome inference; syslog and shared parser helpers |
| `test_ingest_api.py` | 9 | Single, batch, file (JSON/JSONL/CSV/syslog), and HTTP syslog ingestion; malformed payloads (400/401/403/413/422); API-key tenant binding; batch format detection |
| `test_security_rbac.py` | 10 | Login/session/refresh, admin-only routes, viewer read/write boundaries, tenant isolation, API-key secrecy/rotation, CSRF/CORS, SSRF, tenant/user/rule lifecycle, per-email lockout |
| `test_search_filters.py` | 6 | Free text, source, event type, severity, time range (`from`/`to`), sort/limit, viewer scoping |
| `test_alerting.py` | 6 | Threshold trigger + aggregation, below-threshold/per-IP isolation, notification delivery (webhook/email), tenant evidence, rule validation/lifecycle, idempotent upsert and cooldown |
| `test_retention.py` | 1 | Seven-day default, purge only expired rows, dry run is read-only |
| `test_dashboard.py` | 4 | Top widgets, viewer tenant scoping, platform-admin multi-tenant view, stats endpoints |
| `test_health.py` | 3 | Liveness, readiness (DB + Redis), version, feature flags |
| `test_search_pagination.py` | 5 | Opaque `(ts, id)` keyset cursors, timestamp ties, real totals, invalid cursor |
| `test_dashboard_source_filter.py` | 3 | Dashboard and stats source filters, unknown source -> 422 |
| `test_api_contract.py` | 4 | OpenAPI/effective-route and frontend request-shape guard |

## Conftest

`backend/tests/conftest.py`:
- Forces the disposable `logs_manager_test` database on local Docker PostgreSQL
- Sets `NullPool` to avoid cross-event-loop connection reuse
- Forces Redis to local Docker Redis
- Disables the native syslog listener (`SYSLOG_ENABLED=false`); SaaS ingestion is tested over HTTP
- Runs Alembic migrations and `scripts/seed_demo_data.py` once per session
- Removes rows created by each module, driven by a baseline snapshot
- Provides `client`, `login()`, `api_key`, `api_key_demoa`, and `api_key_demob`

## Coverage

Run the same command with coverage:

```bash
cd backend
TEST_DATABASE_URL="postgresql+asyncpg://logs:postgres_pass@localhost:55432/logs_manager_test?sslmode=disable" \
TEST_REDIS_PORT=56379 \
./.venv/bin/python -m pytest --cov=app --cov-report=term-missing -q
```

The curated suite keeps overall coverage at ~74% and holds every critical module
within 10 points of the previous full suite (ingest, parsers, search, alerting,
security, dependencies, normalized schema).

## Deletion record

The old ~500-function suite was removed in a separate commit. The mapping from
each deleted file to its replacement coverage is recorded in
`/tmp/test_deletion_manifest.md` during the cleanup run.

## Smoke test

`tests/smoke.sh` exercises a running stack end to end (health, login,
single/batch ingest, logs, alerts, dashboard, rules):

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

Run `make seed` first so the demo accounts and an alert rule exist. Demo
credentials are printed during seeding and are controlled by
`SEED_ADMIN_PASSWORD`, `SEED_VIEWER_A_PASSWORD`, and
`SEED_VIEWER_B_PASSWORD`.

## CI note

Tests require PostgreSQL and Redis (provided by the root `docker-compose.yml`
locally and service containers in CI). CI runs `python -m pytest -q` from
`backend/`; no individual test paths are hard-coded.
