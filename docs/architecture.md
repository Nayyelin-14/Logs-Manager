# Log Manager / Mini SIEM — Architecture

## Overview

A log management system that ingests, normalizes, searches, visualizes, and alerts
on events from multiple sources. Deployable as a single-node appliance (Docker
Compose) or as a zero-cost SaaS.

## Deployment modes

| Mode | Hosting | Public entry point | Ingestion |
|---|---|---|---|
| Appliance | One VM or machine, Docker Compose | Caddy on 80/443 | Syslog 514 (container 5514) and HTTP `/api/ingest` |
| SaaS | Vercel (SPA) + Render (API) + Neon + Upstash | Vercel HTTPS, `/api/*` proxied to Render | HTTP `/api/ingest` only |

Both modes run the same backend code. The appliance runs PostgreSQL, Redis,
the worker, the syslog listener, and the webhook receiver as separate Compose
services. SaaS mode uses managed Neon and Upstash, embeds the worker in the web
process, and disables raw syslog because Render and Vercel are HTTP-only.

## Mermaid architecture diagram

```mermaid
graph TB
    %% Sources
    FW[Firewall Syslog<br/>UDP/TCP 514]
    RT[Router Syslog<br/>UDP/TCP 514]
    API[HTTP API<br/>POST /ingest]
    CS[CrowdStrike<br/>JSON sample]
    AW[AWS CloudTrail<br/>JSON sample]
    M3[Microsoft 365<br/>Audit sample]
    AD[Active Directory<br/>Event 4624/4625]

    %% Ingest
    ING[/ingest<br/>Syslog Listener<br/>UDP/TCP 514 host<br/>(5514 container)]
    HTTP[FastAPI<br/>POST /ingest<br/>X-API-Key / JWT]

    %% Normalize
    NORM[Normalization Layer<br/>Pydantic NormalizedEvent<br/>7 source mappers]

    %% Store
    DB[(PostgreSQL 16<br/>events table<br/>JSONB + GIN indexes<br/>Retention ≥7 days)]

    %% Alert worker
    WORKER[Worker<br/>Alert sweep every 30s<br/>Retention hourly]

    %% Search/API
    SEARCH[FastAPI Search/Stats<br/>GET /api/events<br/>GET /api/stats/*]

    %% UI
    UI[React Dashboard<br/>Top IP/User/Event Type<br/>Timeline, filters]

    %% Alerts/notifications
    ALERT[Alerts Page<br/>ACK/Close]
    WEB[Webhook Receiver<br/>Logs alerts]
    MAIL[(SMTP<br/>optional)]

    %% Data flow
    FW --> ING
    RT --> ING
    API --> HTTP
    CS --> HTTP
    AW --> HTTP
    M3 --> HTTP
    AD --> HTTP

    ING --> NORM
    HTTP --> NORM

    NORM --> DB

    DB --> SEARCH
    DB --> WORKER

    WORKER --> DB
    WORKER --> ALERT
    WORKER --> WEB
    WORKER --> MAIL

    SEARCH --> UI
    ALERT --> UI
    WEB --> UI

    %% Caddy / TLS
    CADDY[Caddy Web Server<br/>80/443, TLS, serves SPA<br/>Let's Encrypt or self-signed]
    CADDY --> UI
    CADDY --> SEARCH
    CADDY --> HTTP
```

## Data flow

1. **Sources → Ingest**: Firewall/router syslog arrives via UDP/TCP 514 (mapped to container 5514).
   HTTP API events arrive via POST /ingest or POST /ingest/file. The simulator generates
   live traffic for demos.
2. **Ingest → Normalize**: Every source is parsed by a source-specific normalizer and
   validated through the Pydantic `NormalizedEvent` model. The original payload is always
   preserved in the `raw` JSONB column.
3. **Normalize → Store**: Normalized events are inserted into PostgreSQL with deterministic
   SHA256 IDs for deduplication. JSONB `raw` + GIN indexes enable full-text search.
4. **Store → Search/Stats**: The FastAPI API serves GET /api/events and GET /api/stats/*
   with tenant-scoped, parameterized SQL queries.
5. **Store → Alert Worker**: Every 30 seconds, the worker evaluates all enabled alert rules
   via a single GROUP BY ... HAVING query per rule. Evidence collection uses the same
   tenant, filter, and `ts >= window_start` predicate as the aggregate (no `ts <= now`
   bound), so `count` and `eventIds` stay consistent even for future-dated events.
   Alerts are idempotent (dedupe key).
6. **Alert → Notify**: Webhook POST with 3 retries + exponential backoff; optional SMTP.
   Results stored in `alerts.notifications`.
7. **UI**: React dashboard displays Top IP/User/Event Type, timeline, filters, alerts, rules.

## Tenant model

**Tenant resolution:**
- **HTTP API / file upload**: Tenant derived from the X-API-Key (hashed, mapped to a tenant)
  or JWT claim. Body `tenant` must match the credential's tenant (403 if mismatch, unless
  admin). API keys are created per tenant by admins and shown once.
- **Syslog**: No tenant field in syslog. Tenant resolved via `SYSLOG_TENANT` env var
  (default `demoA`) and `SYSLOG_SOURCE` env var (default `firewall`).
- **Simulator**: Uses `--tenants` flag and API key per tenant.

**Query-time enforcement:**
- `get_tenant_scope()` dependency runs on every `/api/*` endpoint.
- **VIEWER**: Forced to `current_user.tenant`; any `tenant=` param is ignored.
- **ADMIN**: May pass `tenant=` or `all` for cross-tenant queries.
- All SQL uses parameterized queries only; no dynamic SQL from user input.

**Roles:**
| Role | Capabilities |
|---|---|
| ADMIN | Platform administrator: all tenants, manage rules/users/API keys, upload files, view all alerts. `tenant=NULL` enables cross-tenant queries via `tenant=all` or omitting the `tenant` parameter. |
| VIEWER | Own tenant only, read-only, no rule editing. `tenant` is forced to `user.tenant`; any `tenant=` query param is ignored. |

**ADMIN cross-tenant access:** The ADMIN role is a platform-level role (not a tenant-level admin). Cross-tenant data access by ADMIN is intentional by design — the ADMIN's `tenant` is `NULL`, which enables querying all tenants. VIEWERs are strictly scoped to their own tenant and cannot bypass this restriction via query parameters, headers, or request bodies. The backend enforces this on every `/api/*` endpoint; frontend filters alone are not sufficient for tenant isolation.

The frontend uses the same canonical values, `ADMIN` and `VIEWER`. Management
routes (`/`, `/rules`, `/users`) redirect non-admin sessions to `/dashboard`;
the backend remains the authorization boundary.

## Technology choices

| Component | Choice | Rationale |
|---|---|---|
| Backend API | FastAPI (Python) | Type safety, auto OpenAPI docs, async, easy testing |
| Database | PostgreSQL 16 | JSONB + GIN indexes, mature, single DB to operate |
| Syslog collector | Custom Python asyncio | Full control over parsing, easy to explain in interview |
| Frontend | React 19 + Vite + TypeScript + Recharts | Modern, well-documented, chart library included |
| Web server / reverse proxy / TLS | Caddy (appliance); Vercel + Render (SaaS) | Caddy serves the SPA and terminates TLS on one machine; Vercel serves the SPA and proxies `/api/*` to Render |
| Packaging | Docker Compose (appliance); Render Blueprint + Vercel (SaaS) | One-command appliance start; zero-cost managed SaaS |

**Considered alternatives:**
- **OpenSearch/Elasticsearch**: More powerful search but higher operational complexity
  (Java heap, cluster management). Rejected for a demo appliance — PostgreSQL is
  sufficient and easier to run on 4 vCPU / 8 GB.
- **ClickHouse**: Excellent for time-series analytics but less flexible for
  relational tenant/isolation queries. Rejected for simplicity.

## Schema overview

The common schema covers all assignment fields plus additions:
`@timestamp` (ts), `tenant`, `source`, `vendor`, `product`, `event_type`,
`event_subtype`, `severity` (0–10), `action`, `action_detail`, `outcome`,
`src_ip`, `src_port`, `dst_ip`, `dst_port`, `protocol`, `user`, `host`,
`process`, `url`, `http_method`, `status_code`, `rule_name`, `rule_id`,
`cloud.account_id`, `cloud.region`, `cloud.service`, `raw` (JSONB), `_tags`
(array), `ingested_at`, deterministic `id` (SHA256).

See `docs/schema.md` for the full field table and per-source mappings.

## Retention strategy

- Default `RETENTION_DAYS=7` (minimum 7 enforced).
- **Deletion-based retention** on `ingested_at` column: the retention job runs hourly and
  executes `DELETE FROM events WHERE ingested_at < cutoff`. This satisfies the assignment's
  "deletion" option for retention.
- **Why not partitioning or rollover?**
  - Partitioning requires PostgreSQL 11+ and adds complexity (partition management,
    constraint exclusion tuning). For a demo appliance with expected volumes <1M events/day,
    simple DELETE with proper indexes (ix_events_ingested_at) is sufficient.
  - Partitioning would still require periodic DROP/DETACH of old partitions, which is
    essentially a more complex form of deletion. We chose simplicity.
  - The events table has an `ix_events_ingested_at` index to make the WHERE clause fast.
  - For production at scale (>10K events/sec), consider: hourly partitioning by ingested_at,
    or ClickHouse for append-only analytics.
- Retention runs hourly via the worker and is also invocable via `make maintenance` or
  `python -m app.services.retention --dry-run`.
- A demo script `scripts/demo_retention.sh` (and `make demo-retention`) inserts an 8-day-old
  and a 6-day-old event into a dedicated `retention_test` tenant, runs the purge, and
  verifies the 8-day-old event is deleted while the 6-day-old event is kept.
- **Idempotency note**: Deleted rows are not recoverable. For production, implement
  archival backup before deletion.

## Alert engine design

- Rules are stored data (not code): `alert_rules` with `filter` (jsonb),
  `group_by` (whitelist: src_ip, user_name, host), `threshold`,
  `window_minutes`, `cooldown_minutes`, `notify` (jsonb: webhook_url, email).
- The worker runs `evaluate_all_rules()` every 30 seconds. Each rule executes
  ONE parameterized `GROUP BY ... HAVING count(*) >= threshold` query scoped to
  the rule's tenant and time window.
- Idempotent via `dedupe_key = rule_id:tenant:group_value`. Open alerts within
  cooldown are updated (count/last_seen) without re-notification. `count` is the
  aggregate count for the window; `eventIds` is collected with the identical
  predicate, so the two cannot diverge.
- Tenant `*` rules are evaluated per tenant so demoB events never count toward
  demoA.

## Security

- JWT access tokens (15 min) + refresh tokens (30 days) in HttpOnly, Secure,
  SameSite=Lax cookies. SaaS mode serves the API through a same-origin Vercel
  proxy, so cross-site cookie rules do not apply.
- Passwords hashed with bcrypt.
- API keys stored as SHA-256 hashes; plaintext shown once at creation.
- Login rate limiting (slowapi), CORS restricted to configured origins.
- No secrets logged; all config via environment variables.
- SaaS mode backend refuses to start with default/empty JWT secrets.

## Scaling limits and future work

- Single-node PostgreSQL limits write throughput (~10k events/second on
  4 vCPU / 8 GB). For higher volume, consider read replicas or ClickHouse.
- True multi-tenancy (separate schemas/tables per tenant) is a bonus feature.
- Enrichment (GeoIP, reverse DNS) can be added behind a feature flag.
- CI/CD is implemented with GitHub Actions (test, smoke, GHCR, Render, Vercel).
  IaC (Terraform/Helm) is not implemented; Docker Compose and `render.yaml`
  are the deployment definitions.

## Design decisions and trade-offs

### PostgreSQL + JSONB/GIN instead of OpenSearch/ClickHouse

**Why PostgreSQL:** A single relational database is far simpler to operate on a
demo appliance (4 vCPU / 8 GB) than a Java-heavy search cluster. PostgreSQL 16
provides JSONB storage, GIN indexes for full-text search, and parameterized
queries for tenant isolation—all sufficient for the assignment's scale
(<1M events/day).

**Trade-offs:** Search is less powerful than OpenSearch (no aggregations pipeline,
no distributed search). Write throughput is limited to ~10k events/second on
the reference hardware. For production scale, read replicas or ClickHouse would
be needed.

### Single events table with tenant-scoped queries instead of per-tenant tables

**Why a single table:** Simpler schema, simpler queries, simpler retention
(one DELETE statement). Tenant isolation is enforced server-side via `WHERE
tenant = :tenant` on every query—VIEWERs can never cross tenants, ADMINs can
opt into cross-tenant views.

**Trade-offs:** No physical separation between tenants (a buggy query could
theoretically leak data if tenant filtering is omitted). True multi-tenancy
(separate tables/indexes per tenant) is a documented bonus feature for later.

### Deletion-based retention instead of partitioning or rollover

**Why DELETE:** Simple, easy to understand, easy to demonstrate. An hourly job
deletes events older than `RETENTION_DAYS` from `ingested_at`.

**Trade-offs:** Deleted rows are not recoverable without backup. Partitioning
(DROP/DETACH) would be more complex for similar operational benefit at demo
scale.

## Known limitations

- **Email delivery:** SMTP is disabled by default; alert emails are not
  delivered. Webhook is the working notification channel. Configure SMTP or
  use the webhook receiver for email-like notifications.
- **No per-tenant tables:** All tenants share the same `events` table.
  Isolation is server-side, not physical.
- **No GeoIP/reverse-DNS enrichment:** Source IPs are stored as-is without
  enrichment.
- **No Helm/Terraform IaC:** Docker Compose is the deployment mechanism.
  Terraform/Helm are bonus items not implemented.
- **Test database:** Tests require Docker PostgreSQL + Redis. They cannot run
  against Neon or production databases.

## Folder mapping

| Assignment | Repo |
|---|---|
| `/backend/` | `backend/` |
| `/frontend/` | `frontend/` |
| `/ingest/` | `ingest/` |
