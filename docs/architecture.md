# Log Manager / Mini SIEM — Architecture

## Overview

A log management system that ingests, normalizes, searches, visualizes, and alerts
on events from multiple sources. Deployable as a self-hosted Docker distribution
on one machine or VM, or as a zero-cost SaaS.

## Deployment modes

| Mode | Hosting | Public entry point | Ingestion |
|---|---|---|---|
| Appliance / self-hosted Docker | One machine or VM, `docker-compose.yml` | **Caddy** on 80/443 (loopback by default; `CADDY_BIND_IP=0.0.0.0` for LAN/VM) | Native UDP/TCP Syslog via the `ingest` service, plus HTTP `/api/ingest` |
| SaaS | Vercel (SPA) + Render (API) + Neon + Upstash | Vercel HTTPS, `/api/*` proxied to Render | HTTP `/api/ingest` and HTTPS `/api/ingest/syslog` only |
| Local frontend dev | Vite dev server on 5173 | Vite proxy `/api` → local FastAPI | Same API as the appliance |

Both modes run the same backend code. The self-hosted Docker distribution runs
PostgreSQL, Redis, the worker, the dedicated Syslog listener, and the webhook
receiver as separate Compose services. SaaS mode uses managed Neon and Upstash,
embeds the worker in the web process, and disables raw Syslog because Render and
Vercel are HTTP-only.

`docker-compose.yml` is the only supported self-hosting entry point. A VM is
just another machine running that same file with different environment values
(`CADDY_BIND_IP`, `DOMAIN`, ports, secrets). `docker-compose.vm.yml` is an
internal image-based deployment artifact and is not part of the user-facing
self-hosting path.

## Syslog: self-hosted Docker vs SaaS

| | Self-hosted Docker | SaaS |
|---|---|---|
| Transport | UDP/TCP syslog | HTTPS `POST /api/ingest/syslog` |
| Host port | **514** by default (container 5514); set `SYSLOG_HOST_PORT=5514` on Docker Desktop/WSL2 | 443 only |
| Listener | `SYSLOG_ENABLED=true` starts the native listener in the dedicated `ingest` container; the API container has it disabled | `SYSLOG_ENABLED=false` |
| Auth | tenant implied by the listener config | `X-API-Key` header scoped to one tenant |
| Normalization | `parse_syslog_message` → `IngestionService`/`NormalizationService` | same parser and service path |
| Event tag | none | `transport=http-syslog` |

The HTTPS endpoint accepts either newline-delimited text:

```http
POST /api/ingest/syslog
Content-Type: text/plain
X-API-Key: <tenant key>

<134>Oct 30 22:14:15 fw01 vendor=Fortinet ... msg="DNS query blocked"
```

or a JSON envelope:

```json
{"lines": ["<134>Oct 30 22:14:15 fw01 ...", "<190>Oct 30 22:15:01 router01 ..."]}
```

The tenant comes from the API key. If `tenant` is supplied in the query string
or JSON body and does not match the key, the request returns **403**. Limits
default to 1 MiB of body and 1000 lines; oversized requests return **413**.
Successful requests return **202** with `{"accepted", "rejected", "errors"}`.

The HTTPS batch is committed in **one transaction**. Parse/validation errors
are isolated per line (valid lines are stored, invalid lines are reported in
`errors`), but an infrastructure failure rolls the whole batch back and returns
**503** (unexpected failures return **500**). Nothing is acknowledged as 202
when the database failed, so a forwarder can safely retry a 5xx. Messages that
carry no timestamp are stamped at ingestion time (existing semantics); retain
the device timestamp in the forwarder (`%rawmsg%`, Vector's raw message) to keep
retries idempotent. See `samples/forwarder/README.md`.

Use `samples/forwarder/` (Vector or rsyslog) to forward device syslog to the
SaaS endpoint. Vector sends newline-delimited text, uses a bounded disk buffer,
and retries 429/5xx/transport failures.

Native port **514 must never be exposed to the public Internet**. Bind it to a
private interface (`SYSLOG_BIND_IP`), allowlist sources in the host firewall,
and optionally set `SYSLOG_ALLOWED_CIDRS`. The ingest container health check
runs `SELECT 1` and verifies every enabled listener; a socket alone is not
healthy when the database is unavailable.

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
    DB[(PostgreSQL 18<br/>events table<br/>JSONB + GIN indexes<br/>Retention ≥7 days)]

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
4. **Store → Search/Stats**: The FastAPI API serves GET /api/events with keyset
   pagination on `(ts, id)` (opaque cursor; changing `sort_by` with an old cursor
   returns 400) and GET /api/stats/* with tenant-scoped, parameterized SQL
   queries. The dashboard filters events by time range, tenant and source; the
   source condition is applied to every event aggregate so the top lists,
   timeline and source distribution describe the same scope.
5. **Store → Alert Worker**: Every 30 seconds, the worker evaluates all enabled alert rules
   via a single GROUP BY ... HAVING query per rule. Evidence collection uses the same
   tenant, filter, and `ts >= window_start` predicate as the aggregate (no `ts <= now`
   bound), so `count` and `eventIds` stay consistent even for future-dated events.
   Alerts are idempotent (dedupe key).
6. **Alert → Notify**: Webhook POST with 3 retries + exponential backoff; optional SMTP.
   Results stored in `alerts.notifications`.
7. **UI**: React dashboard displays Top IP/User/Event Type, timeline and source
   distribution, with filters for time range, tenant (admins) and source; alerts and
   rules are managed from the same shell. Source values match the backend exactly
   (`firewall`, `network`, `api`, `crowdstrike`, `aws`, `m365`, `ad`).

## Tenant model

**Tenant resolution:**
- **HTTP API / file upload**: Tenant derived from the X-API-Key (hashed, mapped to a tenant)
  or JWT claim. Body `tenant` must match the credential's tenant (403 if mismatch, unless
  admin). API keys are created per tenant by admins and shown once.
- **Syslog**: No tenant field in syslog. Tenant resolved via `SYSLOG_TENANT` env var
  (default `demoA`) and `SYSLOG_SOURCE` env var (default `firewall`). This is a
  single-tenant mapping for the whole native listener: every device reaching one
  ingest container lands in the same tenant. Run separate containers with
  different `SYSLOG_TENANT` values for multiple native-Syslog tenants.
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

**Tenant-bound admins:** An ADMIN created with a non-NULL `tenant` is bound to
that tenant. It can manage rules, users, alerts, and logs for its own tenant
only; cross-tenant reads/writes and `/api/tenants*` management return 403/404.
The seeded `admin@demo.local` account is a platform ADMIN (`tenant = NULL`).

The frontend uses the same canonical values, `ADMIN` and `VIEWER`. Management
routes (`/`, `/rules`, `/users`) redirect non-admin sessions to `/dashboard`;
the backend remains the authorization boundary.

## Technology choices

| Component | Choice | Rationale |
|---|---|---|
| Backend API | FastAPI (Python) | Type safety, auto OpenAPI docs, async, easy testing |
| Database | PostgreSQL 18 | JSONB + GIN indexes, mature, single DB to operate |
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

- JWT access tokens (15 min) + refresh tokens (30 days) in HttpOnly,
  SameSite=Lax cookies (`Secure` when `COOKIE_SECURE=true`). SaaS mode serves
  the API through a same-origin Vercel proxy, so cross-site cookie rules do not
  apply.
- Passwords hashed with bcrypt.
- API keys stored as SHA-256 hashes; plaintext shown once at creation.
- Login rate limiting (slowapi), CORS restricted to configured origins.
- No secrets logged; all config via environment variables.
- SaaS mode backend rejects empty JWT secrets at settings validation. The
  Render Blueprint generates strong values for both secrets; if you configure
  Render manually, set them yourself.

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
demo appliance (4 vCPU / 8 GB) than a Java-heavy search cluster. PostgreSQL 18
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
