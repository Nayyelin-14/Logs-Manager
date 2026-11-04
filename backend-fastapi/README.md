# Log Manager / Mini SIEM - FastAPI Backend

## Important: This is the Python/FastAPI backend only.
# The Express backend at /backend is completely untouched and remains 
# the original submission backend. This directory contains the FastAPI 
# replacement that provides the complete log management pipeline.

## Overview

Log Manager is a mini SIEM system that supports multiple data sources,
normalization, search, dashboard, alerting, and deployment in both
appliance (Docker Compose) and SaaS (cloud VM with HTTPS) modes.

## Architecture

```
Sources → Ingest → Normalize → Postgres → Search/Dashboard → Alert
```

See docs/architecture.md for the full architecture diagram and tenant model.

## Quick Start (Development)

```bash
# 1. Install dependencies
cd backend-fastapi
make env       # copies .env.example to .env
# Edit .env with your settings (or use defaults)

# 2. Start the services
make backend-up

# 3. Wait for services to start (~30 seconds)

# 4. Seed the database
make backend-seed
# or: python scripts/seed_demo_data.py

# 5. Verify it's working
make backend-ps
```

## Available Services

| Service | Port | Description |
|---------|------|-------------|
| Backend API | 4500 | FastAPI app with all routes |
| Syslog Listener | 5514/UDP, 5514/TCP | RFC3164/RFC5424 syslog parser |
| PostgreSQL | 5432 (internal) | Events, users, rules, alerts |
| Redis | 6379 (internal) | Cache, email queue (arq) |
| Caddy | 443/HTTPS | Reverse proxy with TLS |
| Frontend | 8080 | React UI (separate service) |

## API Endpoints

### Authentication
- `POST /api/auth/login` - Login with username/password
- `POST /api/auth/register` - Register new user
- `POST /api/auth/otp` - OTP verification
- `POST /api/auth/logout` - Logout (clears cookies)

### Ingestion
- `POST /api/ingest` - Single event or batch
- `POST /api/ingest/file` - File upload (AWS, M365, AD JSON/NDJSON)
- `GET /api/search` - Search events with filters
- `GET /api/stats` - Dashboard statistics

### Alerts & Rules
- `GET /api/rules` - List alert rules
- `POST /api/rules` - Create rule (Admin)
- `PUT /api/rules/{id}` - Update rule (Admin)
- `PATCH /api/rules/{id}/enabled` - Enable/disable (Admin)
- `DELETE /api/rules/{id}` - Delete rule (Admin)
- `GET /api/alerts` - List alerts (tenant-scoped)
- `PATCH /api/alerts/{id}` - Update alert status (Admin)
- `POST /api/alerts/{id}/ack` - Acknowledge alert (Admin)

### Users
- `GET /api/users` - List users (Admin)
- `POST /api/users` - Create user (Admin)

## Environment Variables

See `.env.example` for all required settings. Key variables:

- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection for arq email queue
- `ACCESS_TOKEN_SECRET` - JWT access token signing key
- `REFRESH_TOKEN_SECRET` - JWT refresh token signing key
- `COOKIE_SECURE` - `true` for HTTPS SaaS, `false` for HTTP appliance
- `COOKIE_SAME_SITE` - `lax` for appliance, `none` for HTTPS SaaS
- `INGEST_API_KEY` - Machine ingestion API key prefix
- `INGEST_API_TENANT` - Default tenant for ingestion
- `SYSLOG_ENABLED` - `true`/`false` (start syslog listener)
- `SYSLOG_TENANT` - Default tenant for syslog messages
- `SYSLOG_SOURCE` - Default source for syslog messages
- `SYSLOG_TIMEZONE` - Timezone policy for naive RFC3164 syslog timestamps:
  `UTC` (default, historical behavior), `local`, or an IANA name such as
  `Asia/Bangkok`. Unknown values fall back to UTC with a warning. RFC5424
  messages carry their own offset and are never affected.
- `RETENTION_DAYS` - Raw-log retention window in days (default `7`)
- `RETENTION_SCHEDULE` - Cron expression for the retention job (default `0 5 * * *`)
- `SMTP_ENABLED` - `true`/`false` (email notifications)
- `CORS_ORIGINS` - Allowed origins for CORS

> **Email delivery status: not enabled.** `SMTP_ENABLED=false` in both
> `.env` and `docker-compose.yml`, no SMTP credentials are configured, and no
> arq worker process runs in the appliance. OTP/alert emails are written to
> the Redis `email_queue` but are never consumed or delivered; the
> `email_notifications` table stays empty. Alerting itself is unaffected.

## Development

### Running Tests

```bash
make test  # Runs pytest against the test database (tests/conftest.py)
# or: pytest tests/ -q
```

All 109 tests pass, including:
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

### Important: Express Backend

The original Express backend at `/backend` is **completely untouched**.
Do not modify any files in `/backend`. This FastAPI backend at
`/backend-fastapi` is the submission replacement.

### License

This project is for the Full-Stack Developer (Intern) practical assignment.
