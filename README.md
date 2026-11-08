# Logs Manager — Mini SIEM (FastAPI + React + PostgreSQL)

A complete log management appliance with multi-source ingestion, normalization,
search, dashboard, alerting, and 7-day retention. Built for the
Full-Stack Developer (Intern) practical assignment.

## Assignment compliance

| Requirement | Status |
|---|---|
| ≥4 working ingest sources (syslog UDP/TCP 514, HTTP POST /ingest, file batch, simulator) | ✅ |
| 7 source types normalized (firewall, network, api, crowdstrike, aws, m365, ad) | ✅ |
| Common schema with @timestamp, tenant, source, severity 0-10, action, raw, _tags | ✅ |
| Postgres JSONB + GIN storage, dashboard with Top IP/User/Event Type, timeline | ✅ |
| ≥1 alert rule with UI + webhook notification | ✅ |
| Admin/Viewer RBAC with tenant data isolation | Implemented |
| Appliance (Docker Compose) + SaaS (Render + Vercel + Neon + Upstash) | Implemented |
| HTTPS (Caddy on the appliance; managed TLS on Vercel/Render) | Implemented |
| Retention ≥7 days (deletion + cleanup-ready) | Implemented |
| Tests, docs, Postman collection, samples + sender scripts | Implemented |

Statuses above mean the feature is implemented in code. Runtime/SSL/end-to-end
verification requires a live stack; some items are marked manual because they
need Docker PostgreSQL/Redis and a running Compose stack.

## Repo folder mapping (to assignment paths)

| Assignment path | Repo path | Description |
|---|---|---|
| `/backend/` | `backend/` | FastAPI API, parsers, normalizers, models, migrations |
| `/frontend/` | `frontend/` | React 19 + Vite + TypeScript + Recharts UI |
| `/ingest/` | `ingest/` | Standalone syslog UDP/TCP listener service |
| `/docs/` | `docs/` | Architecture, setup guides, schema, demo guide |
| `/samples/` | `samples/` | Sample log files + sender scripts (send_syslog.sh, post_logs.py, simulator.py) |
| `/tests/` | `tests/` + `backend/tests/` | Acceptance check + pytest suite |
| `docker-compose.yml` | `docker-compose.yml` | Root compose: caddy (serves the built SPA), backend, ingest, worker, db, redis, webhook-receiver |
| `.env.example` | `.env.example` | All required settings |
| `Makefile` | `Makefile` | up, down, seed, demo, test, lint, verify, reset |

## Quick start (Docker appliance)

```bash
# Clone the repository
git clone <this-repo>
cd Logs-Manager

# Create .env from template
cp .env.example .env
# Edit .env with your settings (passwords, secrets, DOMAIN)

# Start the stack (one command)
make up

# Wait ~30s for services to become healthy, then seed demo data
make seed

# Access the system
#   UI:        https://localhost:443/ (via Caddy, self-signed cert locally)
#   API:       http://localhost:4500 (direct) or https://localhost:443/api/ (via Caddy)
#   Syslog:    udp/tcp 127.0.0.1:514
#   API docs:  http://localhost:4500/docs
```

Demo logins (after `make seed`):

| Email | Password | Role |
|---|---|---|
| admin@demo.local | (seed prints on startup) | ADMIN | all tenants |
| viewerA@demo.local | (see seed output) | VIEWER | demoA |
| viewerB@demo.local | (see seed output) | VIEWER | demoB |

## Quick start (zero-cost SaaS)

The SaaS mode runs the SPA on Vercel, the API and embedded worker on Render,
PostgreSQL on Neon, and Redis on Upstash. It costs $0/month on free tiers and
does not need a VM.

```
Browser → Vercel (SPA + /api/* proxy) → Render (FastAPI + worker)
                                           ├── Neon PostgreSQL
                                           └── Upstash Redis
```

1. Create the Neon database and Upstash Redis; copy the pooled Neon URL
   (`postgresql+asyncpg://...?sslmode=require`) and the Upstash `rediss://` URL.
2. In Render, **New → Blueprint**, select this repo and the `dev` branch, and
   fill in `DATABASE_URL`, `REDIS_URL`, `INGEST_API_KEY`, and `CORS_ORIGINS`.
3. In Vercel, import the repo, set **Root Directory** to `frontend`, and add
   `VITE_API_URL=/api`.
4. Point `frontend/vercel.json` at the Render service URL, deploy, then seed or
   reset users from your laptop.

Full click-by-click instructions, CI/CD secrets, and troubleshooting:
`docs/setup_saas.md`.

SaaS limitations: the free Render service sleeps after 15 minutes idle, raw
syslog is unavailable (use `POST /api/ingest`), and the worker pauses while the
service is asleep.

## Key endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/ingest` | Ingest single event (exact assignment path) |
| POST | `/ingest/batch` | Ingest batch of events |
| POST | `/ingest/file` | File upload (JSON, NDJSON, CSV, CloudTrail) |
| GET | `/api/events` | Search events with filters (from,to,tenant,source,q,...) |
| GET | `/api/stats/top` | Top N values for a field |
| GET | `/api/stats/timeline` | Event counts over time, split by source |
| GET | `/api/stats/summary` | Dashboard KPIs |
| GET | `/api/sources/health` | Per-source health (admin only) |
| GET | `/api/get-alerts` | List alerts (tenant-scoped) |
| POST | `/api/rules/{id}/test` | Dry-run alert rule evaluation |
| POST | `/api/auth/login` | JWT login (HttpOnly cookie) |

## Makefile targets

| Target | Description |
|---|---|
| `make up` | Start all services (appliance mode) |
| `make down` | Stop and remove Docker Compose stack |
| `make seed` | Seed tenants, users, logs, alert rules |
| `make demo` | Run bruteforce simulator (triggers alerts) |
| `make test` | Run backend pytest suite (uses TEST_DB_PORT if set) |
| `make lint` | File size check + validation |
| `make verify` | Run acceptance checklist (PASS/FAIL per item) |
| `make maintenance` | Run retention maintenance once |
| `make shell` | Shell into backend container |
| `make saas-check` | Validate `render.yaml` and `frontend/vercel.json` |
| `make saas-smoke` | Smoke test a deployed SaaS URL |
| `make set-password` | Set an existing user password against any database |
| `make set-api-key` | Rotate a tenant ingestion API key against any database |

### Running Tests

#### Inside Docker container (recommended)
```bash
docker compose -p lms_local -f docker-compose.yml up -d
docker compose -p lms_local -f docker-compose.yml exec -T backend pytest -v
```

#### On host with alternate ports
```bash
# Start stack with alternate ports (avoiding 5432/6379 conflicts)
DB_HOST_PORT=55432 REDIS_HOST_PORT=56379 \
  docker compose -p lms_local -f docker-compose.yml up -d

# Run tests pointing to the alternate port
cd backend && TEST_DB_PORT=55432 TEST_REDIS_PORT=56379 \
  ./.venv/bin/python -m pytest -v
```

### Port Configuration (default settings)

| Service | Host Port | Internal Port |
|---|---|---|
| Caddy HTTP | 127.0.0.1:80 | 80 |
| Caddy HTTPS | 127.0.0.1:443 | 443 (TCP/UDP) |
| Backend API | 127.0.0.1:4500 | 4500 |
| PostgreSQL | 127.0.0.1:55432 | 5432 |
| Redis | 127.0.0.1:56379 | 6379 |
| Syslog (UDP/TCP) | 127.0.0.1:514 | 5514 |
| Webhook receiver | 127.0.0.1:8008 | 8000 |

The React SPA is built into the Caddy image and served by Caddy at `/`; there is
no separate frontend container or nginx process.

Set `DB_HOST_PORT=5432` etc. to use standard ports if available.

## Acceptance checklist (`make verify`)

1. `make up && make seed` starts from a clean clone
2. `logger -n <host> -P 514` syslog visible in UI within 60s
3. `POST /ingest` sample JSON → searchable
4. Upload AWS/M365/AD sample files → normalized
5. Dashboard Top N, timeline, tenant/source/time filters
6. Bruteforce simulator → alert + webhook notification
7. viewer-a cannot see demoB (RBAC)
8. HTTPS on SaaS URL
9. Retention drops data older than 7 days

## Documentation

- `docs/README.md` — Documentation index and navigation
- `docs/architecture.md` — Mermaid diagram, data flow, tenant model, tech choices
- `docs/setup_appliance.md` — Appliance deployment steps
- `docs/setup_saas.md` — Zero-cost SaaS deployment (Render + Vercel + Neon + Upstash)
- `docs/DEMO_GUIDE.md` — 30-minute demo script
- `docs/schema.md` — Common schema field reference
- `docs/API_CONTRACT.md` — API route and response contract
- `docs/SECURITY_DESIGN.md` — Auth, RBAC, tenant isolation, and rate limits
- `postman/Logs-Manager.postman_collection.json` + `postman/Logs-Manager.postman_environment.json` — canonical Postman collection validated against actual routes

Canonical workflow: `make up` → `make seed` → `make verify`. `run.sh` is a thin wrapper around `make up`.

## Security

- JWT access (15 min) + refresh (30 day) tokens in HttpOnly cookies
- bcrypt password hashing
- API keys stored as SHA-256 hashes, shown once at creation
- Login rate limiting, restricted CORS, security headers
- Tenant isolation enforced server-side (VIEWER = own tenant only)


