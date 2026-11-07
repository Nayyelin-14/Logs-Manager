# Final Report — Logs Manager Take-Home Assignment

## Status

| Area | Status | How verified |
|------|--------|--------------|
| Backend test suite | **PASS** | Automated: `pytest -q` against a disposable local PostgreSQL/Redis test stack (507 passed, 0 failed) |
| Backend alerting tests | **PASS** | Automated: `tests/test_alerting.py` |
| Users API / role isolation tests | **PASS** | Automated: included in the full suite, plus targeted tenancy unit tests |
| Frontend TypeScript typecheck | **PASS** | Automated: `npx tsc -b` after removing unused components |
| Frontend production build | **PASS** | Automated: `npm run build` (`tsc -b && vite build`) after removing unused components |
| Frontend ESLint | **PASS** | Automated: `npm run lint` (0 errors, 0 warnings) |
| Postman collection paths | **PASS** | Static JSON validation + request-path cross-check against actual FastAPI routes; live Postman run not performed |
| Docker Compose appliance runtime | **NOT VERIFIED** | Not run in this verification pass |
| SaaS HTTPS / Caddy TLS | **NOT VERIFIED** | Not run in this verification pass |
| End-to-end UI walkthrough | **NOT VERIFIED** | Not run in this verification pass |
| External syslog / webhook / SMTP delivery | **NOT VERIFIED** | Not run in this verification pass |

Automated checks pass. Manual acceptance is still required.

## Automated Verification

Environment used for the backend runs:

- Python 3.12, pytest 9.2.0
- Disposable local PostgreSQL 16 and Redis 7 started with a temporary Compose project (`lms_verify`)
- Database: `logs_manager_test` on `127.0.0.1:55432`; Redis on `127.0.0.1:56379`
- The temporary stack and its volumes were torn down after the runs
- No production database or existing production volume was used

The backend commands below use the repository's test-only credentials and database name. They are not application secrets.

### 1. Previously failing test: cross-tenant alert evidence

```bash
cd backend-fastapi
TEST_DATABASE_URL="postgresql+asyncpg://logs:postgres_pass@localhost:55432/logs_manager_test?sslmode=disable" \
TEST_REDIS_PORT=56379 ./.venv/bin/python -m pytest \
  tests/test_alerting.py::test_alerting_9_cross_tenant_isolation -q --durations=5
```

Result: **1 passed, 1 warning in 15.31s**

### 2. Previously failing test: 500-event batch benchmark

```bash
cd backend-fastapi
TEST_DATABASE_URL="postgresql+asyncpg://logs:postgres_pass@localhost:55432/logs_manager_test?sslmode=disable" \
TEST_REDIS_PORT=56379 ./.venv/bin/python -m pytest \
  tests/test_alerting.py::test_alerting_12_batch_500_events_completes -q --durations=5
```

Result: **1 passed, 1 warning in 10.01s** (measured test call: **2.62s**, under the unchanged 5-second assertion)

### 3. Full alerting test file

```bash
cd backend-fastapi
TEST_DATABASE_URL="postgresql+asyncpg://logs:postgres_pass@localhost:55432/logs_manager_test?sslmode=disable" \
TEST_REDIS_PORT=56379 ./.venv/bin/python -m pytest tests/test_alerting.py -q
```

Result: **19 passed, 1 warning in 55.05s**

### 4. Full backend test suite

```bash
cd backend-fastapi
TEST_DATABASE_URL="postgresql+asyncpg://logs:postgres_pass@localhost:55432/logs_manager_test?sslmode=disable" \
TEST_REDIS_PORT=56379 ./.venv/bin/python -m pytest -q
```

Result: **507 passed, 0 failed, 1 warning in 305.00s** (482 original tests + 25 tenancy unit tests moved from `tests_unit/` into the backend suite)

The only warning is:

```
StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated;
install `httpx2` instead.
```

There are no skipped or xfailed tests.

### 5. Frontend typecheck, build, and lint

```bash
cd frontend/lms
npx tsc -b
npm run build
npm run lint
```

Results:

- TypeScript typecheck: **passed** (`tsc -b` exited 0)
- Production build: **passed** (`vite build`, built in 7.10s in the final run after removing unused components and dependencies)
- ESLint: **0 errors, 0 warnings**

## Fixes Verified by Automation

### Alert timestamp/evidence double counting

The alert aggregate query counted every event with `ts >= window_start` (no upper
bound), while the evidence query also required `ts <= now`. For events whose
timestamps were a few seconds in the future, alert creation stored
`count=5` but fewer than five evidence IDs. A later evaluation treated the
already-counted events as new evidence and added them again, producing
`count=8`.

Fix: `_get_evidence_ids()` now uses the same predicate as the aggregate query
(`ts >= window_start`, no `ts <= now` bound), so the initial evidence set matches
the initial count and later evaluations only add genuinely new event IDs.

Regression coverage:

- `test_alerting_9_cross_tenant_isolation` now asserts
  `count == len(eventIds) == 5` for both tenants.
- `test_alerting_9b_alert_evidence_never_crosses_tenants` loads every evidence
  event ID from the database and asserts each demoa alert references only demoa
  events, each demob alert references only demob events, and the two ID sets are
  disjoint.

### Webhook benchmark isolation

The 500-event benchmark was measuring webhook delivery, not alert evaluation.
Batch ingestion created an alert, and the seeded rule attempted to POST to
`http://webhook-receiver:8000/webhook`. That hostname is unresolved in the test
environment, so three attempts with 1s + 2s backoff pushed the batch over 5s.

Fix: `test_alerting_12_batch_500_events_completes` replaces
`app.services.alerting.alerter.send_webhook` with a deterministic in-process
stub. The test still asserts the batch completes under 5 seconds and asserts the
stub was invoked, proving the alert path ran. Webhook retry behavior remains
covered by `tests/unit/test_notifier.py`; the threshold was not increased.

### User timestamp ordering

`backend-fastapi/app/api/routes/users.py` ordered users by `User.created_at`,
but the model and database column are `User.create_at` / `"createAt"`. Both user
listing endpoints now order by `desc(User.create_at)`. No migration was needed
because the column already existed.

Regression coverage: user listing is sorted by `createAt` descending, and a newly
created user appears first.

### Role alignment

The backend is the source of truth: `ADMIN` and `VIEWER`. The frontend previously
used `USER` in several places.

Updated:

- `Role` type is `"VIEWER" | "ADMIN"`
- `authStore` default role is `VIEWER`
- role filter options and role badges use `VIEWER`
- viewer scoping on the dashboard uses `VIEWER`
- sidebar/user-menu fallbacks use `VIEWER`
- `managementLoader` redirects non-admins away from `/`, `/rules`, and `/users`

Server-side authorization was unchanged; VIEWER permissions were not widened.

### Users API path standardization

The canonical user-list endpoint is `GET /api/get-users`. The unused frontend
helper previously called `users/{query}`. It now calls `/get-users` with an
optional `?search=` parameter.

The legacy `GET /api/users/{query}` endpoint remains in place because it is a
valid infinite-list endpoint and may have external callers. The backend has no
individual-user GET endpoint.

### Frontend lint cleanup

- `CreateForm.tsx`: replaced `any` with `CreateUserFormInput` /
  `CreateUserFormValues` derived from the existing Zod schema.
- `AnalyticsPage.tsx`: removed all `any` annotations; types now infer from
  `DashboardStats` and local types.
- Fixed an exposed runtime bug: analytics range buttons used `" value"` /
  `" label"` keys instead of `value` / `label`, so the range selector did not
  work.

## Cleanup performed in this verification pass

- Removed confirmed-unused frontend files and dependencies: 24 frontend files (unused cards/charts/footer/navbar/login form/alert table/sample data/auth root layout/auth store/UI components/assets/fonts) and dependencies `input-otp`, `@radix-ui/react-checkbox`, `lottie-react`, `next-themes`, `react-icons`, `sooner`, `date-fns`. Frontend lint/typecheck/build remain green.
- Consolidated Postman into `postman/Logs-Manager.postman_collection.json` + environment; corrected invalid `/api/alerts`/`/api/rules` paths, added missing users/tenants/dashboard/legacy-alias requests, and deleted `backend-fastapi/postman_collection.json`.
- Moved `tests_unit/test_tenancy_isolation.py` (25 tests) into `backend-fastapi/tests/unit/test_tenancy_isolation.py` and removed hardcoded `/home/nay/...` paths from five unit-test files. Full backend count is now 507 passed.
- Archived stale docs under `docs/archive/` and deleted `docs/PROGRESS.md` and `docs/stitch-redesign-prompt.md`. Corrected `docs/API_CONTRACT.md`, `docs/SECURITY_DESIGN.md`, `docs/schema.md`, `README.md`, `backend-fastapi/README.md`, `tests/README.md`, and `frontend/lms/README.md` for removed registration/OTP routes, `USER`→`VIEWER` role, false partitioning claim, and stale test counts.
- Simplified developer workflow: root `Makefile` is canonical; `run.sh` is a wrapper around `make up`; deleted `backend-fastapi/docker-compose.yml`; added `check`, `check-env`, `check-files`, `frontend-check`, and `compose-check` targets; patched `scripts/check_env_sync.py` to inspect example files only by default; updated CI to run environment sync and frontend checks.

## Manual Verification Still Required

The following were **not** performed in this verification pass and must not be
claimed as verified:

- Starting the full appliance stack with `make up` or
  `docker compose -f docker-compose.yml -f docker-compose.appliance.yml up -d`
- Running `make verify` / `scripts/acceptance_check.sh` against a live stack
- SaaS deployment with HTTPS, a real domain, and Caddy certificate issuance
- UI login and navigation through dashboard, analytics, logs, alerts, rules, and
  users pages
- Syslog ingestion over UDP/TCP 514 from an external sender
- Webhook delivery to a real receiver
- SMTP/email delivery
- Postman collection run against a live deployment
- 7-day retention behavior against a long-lived database
- Docker volume persistence, restart, and upgrade behavior

## Remaining Manual Acceptance Checklist

- [ ] `make up` starts db, redis, backend, worker, ingest, frontend, Caddy, and webhook
- [ ] Backend health endpoint responds on the expected port
- [ ] Login works for admin and both viewers
- [ ] Admin sees all tenants; viewer A sees only demoa; viewer B sees only demob
- [ ] Viewer is blocked from user management, rule editing, and other admin actions
- [ ] Dashboard renders Top IP/User/Event Type and timeline charts with real data
- [ ] Logs page search and filters return tenant-scoped results
- [ ] Alerts page lists, acknowledges/resolves, and links related logs
- [ ] Rules page creates, edits, enables/disables, and deletes rules
- [ ] Users page lists, creates, updates, and deletes users
- [ ] Syslog UDP and TCP ingestion work from an external sender
- [ ] HTTP `POST /ingest`, `/ingest/batch`, and `/ingest/file` work with an API key
- [ ] A threshold rule creates exactly one alert and sends one webhook
- [ ] Webhook receiver records delivery; retry behavior is observed on failure
- [ ] Optional SMTP notification works when configured
- [ ] Retention removes events older than `RETENTION_DAYS`
- [ ] SaaS mode exposes only 80/443 and 514 and serves HTTPS correctly
- [ ] No secrets are exposed in logs, API responses, or the repository

## Reproducing the Automated Checks

The disposable test stack can be started without touching production volumes:

```bash
POSTGRES_USER=logs POSTGRES_PASSWORD=postgres_pass POSTGRES_DB=logs_manager \
DB_HOST_PORT=55432 REDIS_HOST_PORT=56379 \
docker compose -p lms_verify -f docker-compose.yml -f docker-compose.appliance.yml up -d db redis

cd backend-fastapi
TEST_DATABASE_URL="postgresql+asyncpg://logs:postgres_pass@localhost:55432/logs_manager_test?sslmode=disable" \
TEST_REDIS_PORT=56379 ./.venv/bin/python -m pytest -q

cd ../frontend/lms
npx tsc -b
npm run build
npm run lint

cd ../..
docker compose -p lms_verify -f docker-compose.yml -f docker-compose.appliance.yml down -v
```

## Conclusion

Automated backend tests and frontend typecheck/build/lint are green. The
appliance runtime, SaaS HTTPS path, and end-to-end UI still require manual
acceptance testing on a real deployment.
