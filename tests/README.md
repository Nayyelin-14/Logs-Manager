# Tests

The backend acceptance suite lives in `backend/tests/` and runs with **pytest**.
It is intentionally curated: **61 test functions / 71 parametrized cases across
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
| `test_alerting.py` | 7 | Threshold trigger + aggregation, below-threshold/per-IP isolation, five-minute window edge, notification delivery (webhook/email), tenant evidence, rule validation/lifecycle, idempotent upsert and cooldown |
| `test_retention.py` | 1 | Seven-day default, purge only expired rows, dry run is read-only |
| `test_dashboard.py` | 4 | Top widgets, viewer tenant scoping, platform-admin multi-tenant view, stats endpoints |
| `test_health.py` | 3 | Liveness, readiness (DB + Redis), version, feature flags |
| `test_search_pagination.py` | 5 | Opaque `(ts, id)` keyset cursors, timestamp ties, real totals, invalid cursor |
| `test_dashboard_source_filter.py` | 3 | Dashboard and stats source filters, unknown source -> 422 |
| `test_api_contract.py` | 4 | OpenAPI/effective-route and frontend request-shape guard |

## Assignment requirement -> test mapping

| Assignment requirement | Test file::function |
| --- | --- |
| >=4 working ingest sources (HTTP JSON, batch/file, HTTP syslog, simulator/API key) | `test_ingest_api.py::test_single_event_ingest_normalizes_and_scopes_to_api_key`; `test_ingest_api.py::test_batch_ingest_counts_per_record_and_keeps_good_rows`; `test_ingest_api.py::test_file_upload_parses_jsonl_and_csv`; `test_ingest_api.py::test_http_syslog_accepts_rfc3164_and_rfc5424` |
| 7 source types normalized (firewall, network, api, crowdstrike, aws, m365, ad) | `test_normalization.py::test_firewall_normalizer_and_shared_parser_helpers`; `test_normalization.py::test_cloud_and_identity_normalizers_share_field_names`; `test_normalization.py::test_network_normalizer_uses_network_source_and_ports`; `test_normalization.py::test_canonical_helpers_describe_known_events` |
| Common schema: `@timestamp`, tenant, source, severity 0-10, action, raw, `_tags` | `test_normalization.py::test_normalized_event_validators_and_deterministic_id`; `test_normalization.py::test_tenant_is_never_trusted_from_the_payload` |
| Postgres JSONB storage + dashboard Top IP/User/Event Type + timeline | `test_dashboard.py::test_dashboard_returns_top_widgets_and_timeline`; `test_dashboard.py::test_stats_endpoints_are_scoped_and_shaped` |
| >=1 alert rule with UI + webhook notification | `test_alerting.py::test_threshold_rule_triggers_one_alert_and_aggregates`; `test_alerting.py::test_alert_records_a_notification`; `test_alerting.py::test_rule_validation_and_viewer_boundary` |
| Five failed logins from one IP: alert inside 5 minutes, none when spread beyond 5 minutes | `test_alerting.py::test_five_failures_only_alert_when_inside_five_minute_window` |
| Admin/Viewer RBAC with tenant data isolation | `test_security_rbac.py::test_admin_routes_require_admin_and_authentication`; `test_security_rbac.py::test_viewer_reads_are_tenant_scoped`; `test_security_rbac.py::test_viewer_cannot_mutate_alerts_rules_logs_or_users`; `test_alerting.py::test_alert_evidence_stays_within_tenant` |
| API key secrecy, tenant binding and rotation | `test_security_rbac.py::test_api_key_tenant_binding_secrecy_and_rotation`; `test_ingest_api.py::test_ingest_enforces_api_keys_and_tenant_binding` |
| Login/session security, lockout, CSRF/CORS, SSRF | `test_security_rbac.py::test_login_sets_cookies_and_logout_invalidates_the_session`; `test_security_rbac.py::test_login_rejects_bad_credentials_and_inactive_users`; `test_security_rbac.py::test_csrf_and_cors_boundaries`; `test_security_rbac.py::test_webhook_ssrf_blocks_internal_targets` |
| Search, filters, time range and pagination | `test_search_filters.py::test_free_text_user_and_ip_search`; `test_search_filters.py::test_time_range_filters_use_from_and_to`; `test_search_pagination.py::test_cursor_pagination_covers_every_row_once_with_timestamp_ties` |
| Retention >=7 days (purge + dry run) | `test_retention.py::test_purge_removes_only_expired_events_and_dry_run_is_safe` |
| Self-hosted Docker / SaaS readiness + frontend API contract | `test_health.py::test_readiness_checks_database_and_redis`; `test_api_contract.py::test_every_frontend_route_is_declared`; `test_api_contract.py::test_frontend_query_parameters_are_declared` |
| HTTPS / managed TLS | Manual smoke check (`tests/smoke.sh` against the deployed HTTPS URL); no unit test can assert managed certificates |

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

The old 577-test-function suite was removed in a separate commit. The full
per-function KEEP/MERGE/DELETE ledger (`file::function` plus reason) is recorded
in `/tmp/test_deletion_manifest.md` during the cleanup run.

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
