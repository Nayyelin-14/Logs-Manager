# Log Manager / Mini SIEM - FastAPI Backend

## Important: This is the Python/FastAPI backend only.
# The legacy Express backend at /backend has been removed.
# This directory contains the FastAPI implementation that provides
# the complete log management pipeline.

## Overview

Log Manager is a mini SIEM system that supports multiple data sources,
normalization, search, dashboard, alerting, and deployment in two independent
modes: self-hosted Docker (Caddy + local PostgreSQL/Redis) and hosted SaaS
(Vercel + Render + Neon + Upstash).

## Architecture

```
Sources → Ingest → Normalize → Postgres → Search/Dashboard → Alert
```

See docs/architecture.md for the full architecture diagram and tenant model.

## Quick Start (Development)

Use the root-level workflow (the canonical entry point):

```bash
# Clone the repository and create .env
cp .env.example .env
# Edit .env with your settings (or use defaults)

# 1. Start all services (appliance mode)
make up

# 2. Wait ~30s for services to become healthy, then seed demo data
make seed

# 3. Verify
make test            # backend pytest suite
make frontend-check  # frontend typecheck, lint, and build
```

For backend-only development, start `db` and `redis` with Compose and run the FastAPI app on port 4500. See `docs/setup_appliance.md` for detailed steps.

## Available Services

| Service | Port | Description |
|---------|------|-------------|
| Backend API | 4500 | FastAPI app with all routes |
| Syslog Ingest | 514 host (5514 container) UDP/TCP | Dedicated RFC3164/RFC5424 listener |
| PostgreSQL | 5432 (internal) | Events, users, rules, alerts |
| Redis | 6379 (internal) | Cache, email queue (arq) |
| Caddy | 80/443 | Serves the built React SPA, proxies API, terminates TLS |
| Worker | internal | Alert sweep and retention |

## API Endpoints

### Authentication
- `POST /api/auth/login` - Login (HttpOnly JWT cookies)
- `GET /api/auth/auth-check` - Verify session
- `POST /api/auth/logout` - Logout (clears cookies)
- Public registration, OTP verification, and password recovery are not implemented; users are admin-provisioned via `POST /api/create-user`.

### Ingestion
- `POST /ingest` / `POST /api/ingest` - Single event (exact assignment path)
- `POST /ingest/batch` / `POST /api/ingest/batch` - Batch events
- `POST /ingest/file` / `POST /api/ingest/file` - File upload (JSON, NDJSON, CSV, syslog text)
- `POST /api/ingest/syslog` - Syslog lines over HTTPS for SaaS (`text/plain` or `{"lines":[...]}`)
- `GET /api/events` / `GET /api/get-logs` - Search events with filters
- `GET /api/events/{event_id}` - Tenant-scoped event detail (includes `raw`)
- `GET /api/stats/summary` - Dashboard KPIs
- `GET /api/stats/top` - Top N values for a field
- `GET /api/stats/timeline` - Event counts over time, split by source
- `GET /api/sources/health` - Per-source health (admin only)
- `GET /api/dashboard` - Dashboard statistics

All ingestion routes are rate limited by session identity or client IP with
`INGEST_RATE_LIMIT` (default `600/minute`); exceeded requests return HTTP 429
with `Retry-After`.

### Alerts & Rules
- `GET /api/get-alerts` - List alerts (tenant-scoped)
- `PATCH /api/alerts/{id}` - Update alert status (Admin)
- `GET /api/get-rules` - List alert rules
- `POST /api/create-alertRule` - Create rule (Admin)
- `PUT /api/update-rule/{id}` - Update rule (Admin)
- `PATCH /api/rules/{id}/enabled` - Enable/disable rule (Admin)
- `DELETE /api/delete-rule/{id}` - Delete rule (Admin)
- `POST /api/rules/{id}/test` - Dry-run rule evaluation (Admin)

### Users & Tenants (Admin)
- `GET /api/get-users` - List users
- `POST /api/create-user` - Create user
- `PUT /api/update-user` - Update user
- `DELETE /api/delete-user/{user_id}` - Delete user
- `GET /api/get-all-data` - Aggregated dashboard counts
- `GET /api/tenants` - List tenants (platform admin only)
- `POST /api/tenants` - Create tenant (API key returned once)
- `PATCH /api/tenants/{name}` - Activate/deactivate tenant
- `POST /api/tenants/{name}/rotate-key` - Rotate tenant API key

Full details: `docs/API_CONTRACT.md` and `docs/SECURITY_DESIGN.md`.

## Environment Variables

See `.env.example` for all required settings. Key variables:

- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection for arq email queue
- `ACCESS_TOKEN_SECRET` - JWT access token signing key
- `REFRESH_TOKEN_SECRET` - JWT refresh token signing key
- `COOKIE_SECURE` - `true` for HTTPS-only access, `false` for direct local HTTP
- `COOKIE_SAME_SITE` - `lax` for same-origin Caddy/Vercel proxy
- `INGEST_API_KEY` - Machine ingestion API key used when seeding `demoa`
- `INGEST_DEFAULT_TENANT` - Fallback tenant for ingestion
- `SYSLOG_ENABLED` - `true`/`false` (start syslog listener)
- `SYSLOG_TENANT` - Default tenant for syslog messages
- `SYSLOG_SOURCE` - Default source for syslog messages
- `SYSLOG_TIMEZONE` - Timezone policy for naive RFC3164 syslog timestamps:
  `UTC` (default, historical behavior), `local`, or an IANA name such as
  `Asia/Bangkok`. Unknown values fall back to UTC with a warning. RFC5424
  messages carry their own offset and are never affected.
- `RETENTION_DAYS` - Raw-log retention window in days (default `7`)
- `RETENTION_INTERVAL_MINUTES` - Interval between retention runs (default `60`)
- `RETENTION_RUN_ON_STARTUP` - Run a purge when the app/worker starts (default `true`)
- `RETENTION_SCHEDULE` - Legacy cron expression, retained for compatibility
- `EMAIL_PROVIDER` - `resend` (recommended for SaaS) or `smtp`
- `EMAIL_ENABLED` - Master switch for alert email delivery
- `RESEND_API_KEY` / `ALERT_EMAIL_FROM` / `ALERT_EMAIL_TO` - Resend credentials
- `ALERT_WEBHOOK_URL` - Optional global webhook used when seeding rules
- `SMTP_ENABLED` - `true`/`false` (SMTP is skipped automatically on Render)
- `CORS_ORIGINS` - Allowed origins for CORS

> **Alert delivery.** Production uses Resend over HTTPS. Resend retries 429,
> 5xx, and timeouts up to three times; authentication/validation failures are
> not retried. Email failures never block alert creation or webhook delivery,
> and attempts are recorded in `email_notifications`. Admins can verify the
> configuration with `POST /api/alerts/test-notification`.
> Retention runs at startup and then every `RETENTION_INTERVAL_MINUTES` inside
> the embedded worker (or the web scheduler when no worker is embedded).

## Development

### Running Tests

```bash
make test  # Runs pytest against the test database (tests/conftest.py)
# or: pytest tests/ -q
```

The full suite passes (507 tests after consolidating the standalone tenancy tests), including:
- Ingestion API (single/batch/file, tenant enforcement, limits)
- Syslog + batch parsing and source resolution
- Retention (7-day purge, dry-run, cron parsing, timezone policy)
- Tenant isolation, alert threshold, auth, models, parsers

Tests always run against a disposable `logs_manager_test` database (see
`tests/conftest.py`); they never touch Neon or the appliance database.

### Adding New Sample Data

Place JSON/NDJSON files in `samples/` and they can be uploaded via:
```bash
curl -F "file=@samples/new_sample.json" -F "source=api" http://localhost:4500/ingest/file
```

### Custom Parsers

New source parsers can be added to `app/parsers/`:
- Add a new normalizer function in `app/parsers/structured.py`
- Add source inference logic in `app/parsers/canonical.py`
- Register the route in `app/parsers/router.py`

## Deployment

### Appliance Mode (Docker Compose)

```bash
make up          # Start all services
make seed        # Seed demo data
make up          # Full stack is running
```

See docs/setup_appliance.md for detailed steps.

### SaaS Mode (Cloud VM)

```bash
# 1. Provision a cloud VM
# 2. Install Docker + Docker Compose
# 3. Edit .env for production settings
# 4. make up
# 4. Configure DNS + Let's Encrypt (Caddy)
# 5. make seed
```

See docs/setup_saas.md for detailed steps.

### Legacy Backend

The original Express backend at `/backend` has been removed.
This FastAPI backend at `/backend` is the only API implementation.

### License

This project is for the Full-Stack Developer (Intern) practical assignment.
