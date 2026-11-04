# Logs Manager — Mini SIEM (FastAPI + React)

A complete log management appliance with multi-source ingestion, normalization, search, dashboard, alerting, and 7-day retention.

## Architecture

```
┌─────────────┐      ┌────────────────┐      ┌──────────────┐
│  Browser    │ ◄──► │  Nginx (8081)  │ ◄──► │ FastAPI      │
│  React 19   │      │  /api proxy    │      │ :4500        │
└─────────────┘      └────────────────┘      └──────┬───────┘
                                                    │
                         ┌────────────────┐        │
                         │  Syslog UDP/TCP │        ▼
                         │  :5514          │      ┌────────┐
                         └────────────────┘      │Postgres│
                                                 │  16    │
                         ┌────────────────┐      │        │
                         │  File/Batch     │      └────┬───┘
                         │  HTTP JSON      │           │
                         └────────────────┘      ┌────┴────┐
                                                 │  Redis  │
                                                 │   7     │
                                                 └─────────┘
```

- **Frontend**: React 19 + TypeScript + Vite, built into nginx (port 8081)
- **Backend**: FastAPI (Python 3.12) on port 4500, uvicorn
- **Database**: PostgreSQL 16 (SQLAlchemy 2 + Alembic)
- **Cache/Queue**: Redis 7 (arq for email enqueue)
- **Ingestion**: HTTP (single/batch/file) + Syslog RFC3164/5424 (UDP/TCP 5514)
- **Auth**: JWT in HttpOnly cookies (access 15m, refresh 30d), role-based (ADMIN/VIEWER), multi-tenant
- **Alerting**: Threshold rules, source-IP grouping, dedupe cooldown, email enqueued (SMTP disabled by default)
- **Retention**: 7-day raw log purge, daily cron `0 5 * * *`, CLI + scheduler

## Repo layout

```
backend-fastapi/       # FastAPI application (canonical)
  app/                 # source: routes, services, models, integrations
  migrations/          # Alembic versions (head: a1b2c3d4e5f6_fresh_baseline)
  tests/               # 109 pytest tests
  docker-compose.yml   # canonical appliance stack
  Dockerfile           # multi-stage build
frontend/lms/          # React 19 + Vite + nginx
docs/                  # architecture, API contract, security, migration plan
samples/               # 14 sample log files (JSON/CSV/JSONL/syslog)
tests/                 # smoke.sh, README
postman/               # API collection + environment
run.sh                 # one-shot appliance startup
Makefile               # helper targets (up, down, test, seed, validate)
```

## Quick start (Docker appliance)

```bash
git clone <this-repo>
cd Logs-Manager
./run.sh
```

`run.sh` creates `backend-fastapi/.env` from template if missing, builds, and starts the stack. After ~30s:

- UI:        http://localhost:8081
- API:       http://localhost:4500
- Syslog:    udp/5514, tcp/5514
- Health:    http://localhost:4500/healthz
- Readiness: http://localhost:4500/ready

Seed demo data:

```bash
make seed
```

Demo logins (after seeding):
| Email | Password | Role | Tenant |
|-------|----------|------|--------|
| admin@demo.local | Admin123! | ADMIN | demoA |
| viewerA@demo.local | ViewerA123! | VIEWER | demoA |
| viewerB@demo.local | ViewerB123! | VIEWER | demoB |

## Local development

### Backend (FastAPI)

```bash
cd backend-fastapi
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit DATABASE_URL/REDIS_URL if not using Docker
alembic upgrade head
python scripts/seed_demo_data.py
uvicorn app.main:app --host 0.0.0.0 --port 4501 --reload
```

Runs on port 4501 to avoid conflict with Docker appliance on 4500.

### Frontend (React/Vite)

```bash
cd frontend/lms
npm install
# VITE_API_URL=/api  (uses nginx proxy in Docker)
# For dev against local backend:
VITE_API_URL=http://localhost:4500/api npm run dev
```

Runs on port 5173.

## Ingestion API

All ingestion endpoints require `X-API-Key` header (default `ingest-key-dev`). The key is bound to `INGEST_API_TENANT` (`demoA`).

| Method | Path | Body | Notes |
|--------|------|------|-------|
| POST | `/api/ingest` | `{source, event_type?, tenant?, ...}` | Single event; extra fields allowed |
| POST | `/api/ingest/batch` | `{events: [...], source?, tenant?}` | Up to 1000 events; per-record reject |
| POST | `/api/ingest/file` | multipart `file` (JSON/JSONL/CSV/syslog) | 10 MB limit; summary response |
| UDP/TCP | `:5514` | RFC3164 / RFC5424 lines | `SYSLOG_TENANT` / `SYSLOG_SOURCE` defaults |

Sources: `firewall`, `network`, `api`, `aws`, `crowdstrike`, `m365`, `ad` (+ `o365` alias).

## Multi-tenant isolation

- **VIEWER**: sees only events in their own tenant (enforced by query + API)
- **ADMIN**: sees all tenants; can override with `?tenant=` on list endpoints
- Admin-only: `/api/get-all-data`, `/api/get-rules`, `/api/get-users`, user/rule CRUD

## Alerting

- Rules: source + severity threshold + window + cooldown (default 86400s per `src_ip`)
- Dedupe: stable `dedupe_key` per rule + group + window
- Severity: derived from triggering event (fallback `medium`)
- Email: enqueued to Redis via `arq`; **no worker runs by default** (`SMTP_ENABLED=false`); `email_notifications` table tracks status

## Retention

- Raw events older than `RETENTION_DAYS` (default 7) purged daily at 05:00 UTC
- CLI: `python -m app.services.retention [--days N] [--dry-run]`
- Scheduler: APScheduler cron inside FastAPI lifespan (no separate worker)

## Health & readiness

| Endpoint | Purpose |
|----------|---------|
| `/healthz` | Liveness (HTTP 200); static body (uptime=0, fixed timestamp) |
| `/ready`   | Readiness; checks DB + Redis connectivity |

## Tests

```bash
make test          # 109 pytest tests
./tests/smoke.sh   # end-to-end against running appliance
```

## Ports

| Service | Port | Protocol | Notes |
|---------|------|----------|-------|
| Frontend (nginx) | 8081 | HTTP | Docker appliance |
| API (FastAPI) | 4500 | HTTP | Docker appliance |
| API (dev) | 4501 | HTTP | `uvicorn --reload` |
| Frontend (dev) | 5173 | HTTP | Vite |
| PostgreSQL | 5432 | TCP | Docker / local |
| Redis | 6379 | TCP | Docker / local |
| Syslog | 5514 | UDP/TCP | Docker appliance (514 needs root) |

## Environment variables

See `.env.example` for the full list. Key variables consumed by `backend-fastapi/`:
- `DATABASE_URL`, `REDIS_URL`
- `ACCESS_TOKEN_SECRET`, `REFRESH_TOKEN_SECRET`, `COOKIE_SECURE`, `COOKIE_SAME_SITE`
- `INGEST_API_KEY`, `INGEST_API_TENANT`, `INGEST_BATCH_MAX_EVENTS`, `INGEST_MAX_FILE_BYTES`
- `SYSLOG_ENABLED`, `SYSLOG_TENANT`, `SYSLOG_SOURCE`, `SYSLOG_UDP_PORT`, `SYSLOG_TCP_PORT`, `SYSLOG_TIMEZONE`
- `RETENTION_DAYS`, `RETENTION_SCHEDULE`
- `SMTP_ENABLED`, `OTP_EMAIL_ENABLED`, `ALERT_EMAIL_ENABLED` (email disabled by default)
- `CORS_ORIGINS`

Frontend: `VITE_API_URL` (defaults to `/api` behind nginx proxy).

## Documentation

- `docs/API_CONTRACT.md` — endpoint contract (paths, JSON, errors, cookies)
- `docs/ARCHITECTURE_DECISIONS.md` — ADRs (FastAPI, auth, tenancy, email, workers)
- `docs/SECURITY_DESIGN.md` — JWT, cookies, bcrypt, rate limiting, tenant isolation
- `docs/DATABASE_MIGRATION_PLAN.md` — Prisma→SQLAlchemy/Alembic transition
- `docs/WORKER_AND_EMAIL_DESIGN.md` — in-process workers, email queue, no external workers
- `docs/archive/PROJECT_AUDIT.md` — historical audit of the legacy backend
- `docs/archive/MIGRATION_ROADMAP.md` — legacy migration roadmap
- `docs/archive/PRISMA_MIGRATIONS.md` — legacy Prisma migration history

## Known limitations

- **Email not enabled**: `SMTP_ENABLED=false`, no SMTP credentials, no `arq` worker runs. OTP/alert emails are enqueued to Redis but never consumed; `email_notifications` stays empty. Alerting logic is unaffected.
- **No cache consumer**: Cache-invalidation jobs accumulate in Redis (`arq:job:cache:*`); no code reads a cache, so no correctness impact.
- **RFC3164 naive timestamps**: Default timezone `UTC`. Lines written in local wall-clock without offset land in the future. Set `SYSLOG_TIMEZONE=local` or `Asia/Bangkok` to interpret as host/IANA time. RFC5424 offsets are always preserved.
- **`/healthz` static fields**: Returns `uptime: 0` and a fixed timestamp (pre-existing; used only for HTTP-200 healthcheck). Use `/ready` for real status.
- **Host Nginx on 8080**: Unrelated `jtrack` site occupies port 8080 on the host. Appliance UI is on 8081.

## License

Full-Stack Developer (Intern) practical assignment.