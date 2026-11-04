# Architecture Decision Records (ADRs)

**Version:** 1.0  
**Date:** 2026-11-03  
**Status:** Design Phase

---

## ADR-001: FastAPI over Other Python Frameworks

**Status:** Accepted  
**Date:** 2026-11-03

### Context
Replace the legacy Node.js/TypeScript backend with Python. Options considered:
- FastAPI
- Starlette (lower level)
- Litestar
- Django REST Framework
- Flask + extensions

### Decision
Use **FastAPI** as the web framework.

### Rationale
| Factor | FastAPI | Alternatives |
|--------|---------|--------------|
| **Async Native** | ✅ First-class | Flask: ❌, Django: ⚠️ |
| **OpenAPI Auto-gen** | ✅ Built-in | Others: manual/extensions |
| **Pydantic Integration** | ✅ Core | Others: add-on |
| **Performance** | Top tier (uvicorn) | Comparable to Starlette |
| **Type Safety** | Excellent | Good |
| **Ecosystem** | Growing fast | Django: mature but sync-first |
| **Migration Effort** | Low (similar routing model) | Higher for Django/Flask |

### Consequences
- **Positive:** Fast development, automatic API docs, type-safe requests/responses, high performance
- **Negative:** Less mature than Django; fewer built-in admin/auth (but we build custom anyway)
- **Mitigation:** Use `python-jose` + `passlib` for auth; `arq` for workers

---

## ADR-002: SQLAlchemy 2.x + Alembic over Other ORMs

**Status:** Accepted  
**Date:** 2026-11-03

### Context
Need Python ORM compatible with existing PostgreSQL schema (created by Prisma).

### Decision
Use **SQLAlchemy 2.x (async)** with **Alembic** for migrations.

### Rationale
| Factor | SQLAlchemy 2.x | Alternatives |
|--------|----------------|--------------|
| **Prisma Compatibility** | ✅ Full control over mapping | Tortoise/Prisma Python: limited |
| **Async Support** | ✅ Native `asyncio` | Peewee: ⚠️, Django ORM: sync |
| **Migration Tool** | ✅ Alembic (industry standard) | Others: custom/none |
| **Schema Control** | ✅ Exact table/column names | ActiveRecord-style: opinionated |
| **Existing Knowledge** | Team familiarity | New learning curve |

### Consequences
- **Positive:** Exact schema preservation, powerful query builder, mature migration system
- **Negative:** More verbose than Prisma; manual model maintenance
- **Mitigation:** Generate initial models from Prisma schema; use `sqlacodegen` for reference

---

## ADR-003: `arq` over Dramatiq/Celery for Background Jobs

**Status:** Accepted  
**Date:** 2026-11-03

### Context
Need Python replacement for BullMQ (Redis-based queue) used for email and cache invalidation workers.

### Decision
Use **`arq`** (Async Redis Queue) for all background workers.

### Rationale
| Factor | `arq` | Dramatiq | Celery |
|--------|-------|----------|--------|
| **Async Native** | ✅ | ✅ | ⚠️ (prefork) |
| **Redis Only** | ✅ | ✅ | ❌ (needs broker) |
| **Built-in Cron** | ✅ | ❌ | ✅ (beat) |
| **Deployment** | Single process | Single process | Multiple |
| **Dependencies** | Minimal | Redis only | Broker + result backend |
| **Monitoring** | Basic | Dashboard | Flower |
| **FastAPI Integration** | Native | Good | Good |

### Consequences
- **Positive:** Simplest deployment (one Python process per worker type), async-native, built-in cron for retention, minimal dependencies
- **Negative:** Less monitoring UI than Celery Flower; smaller community
- **Mitigation:** Structured logging + Prometheus metrics; `arq` dashboard if needed later

---

## ADR-004: `aiosmtplib` for Email over `smtplib`/Django Email

**Status:** Accepted  
**Date:** 2026-11-03

### Context
Need async email sending for OTP and alert notifications.

### Decision
Use **`aiosmtplib`** for async SMTP delivery.

### Rationale
| Factor | `aiosmtplib` | `smtplib` (sync) | Django Email |
|--------|--------------|------------------|--------------|
| **Async** | ✅ | ❌ | ❌ |
| **STARTTLS** | ✅ | ✅ | ✅ |
| **Dependencies** | Minimal | Stdlib | Django |
| **Integration** | Direct | Thread pool | Framework |

### Consequences
- **Positive:** Non-blocking email sends, works perfectly with `arq` workers, supports Gmail STARTTLS
- **Negative:** Less familiar than `smtplib`
- **Mitigation:** Thin wrapper with same interface as the legacy Nodemailer

---

## ADR-005: Preserve Exact Database Schema (No Renaming)

**Status:** Accepted  
**Date:** 2026-11-03

### Context
Existing PostgreSQL database has tables, columns, indexes, enums created by Prisma. Migration must not lose data.

### Decision
**Preserve exact schema** — table names, column names, enum names, indexes, constraints. No renaming to Python conventions.

### Rationale
| Approach | Pros | Cons |
|----------|------|------|
| **Exact Preservation** | Zero data risk; frontend expects exact column names | Non-Pythonic names (`@timestamp`, `createAt`) |
| **Rename to snake_case** | Pythonic | **Destructive**; breaks frontend; data migration risk |

### Consequences
- **Models use quoted table names:** `__tablename__ = '"User"'`
- **Column names match Prisma `@map`:** `create_at` for `createAt`, `timestamp` for `@timestamp`
- **Enums use native PostgreSQL enums** with same names: `"Role"`, `"Status"`, `"Action"`, `"Source"`
- **All indexes replicated exactly** from Prisma schema

### Mitigation
- Document non-Pythonic names in model docstrings
- Use Pydantic schemas with `alias` for clean Python API

---

## ADR-006: Exact Authentication Contract Preservation

**Status:** Accepted  
**Date:** 2026-11-03

### Context
React frontend uses JWT in HttpOnly cookies with automatic refresh. Changing auth breaks frontend.

### Decision
**Replicate the legacy auth behavior exactly** — JWT payload, cookie names, refresh flow, error messages.

### Specifics Preserved
| Element | Value |
|---------|-------|
| **Algorithm** | HS256 |
| **Access Token TTL** | 15 minutes |
| **Refresh Token TTL** | 30 days |
| **Access Cookie Name** | `accessToken` |
| **Refresh Cookie Name** | `refreshToken` |
| **Cookie Options** | `HttpOnly`, `Secure` (prod), `SameSite=lax/none` |
| **JWT Payload** | `{userId, username, email, tenant, role}` |
| **Auto-Refresh** | On expired access token, use refresh token |
| **OTP Flow** | Register → verify-Otp → confirm-password |
| **Error Codes** | `unthenticated`, `unauthorized`, `Invalid_Error`, etc. |

### Consequences
- **Positive:** Frontend works without changes
- **Negative:** Cannot improve auth design (e.g., refresh token rotation)
- **Mitigation:** Document as compatibility layer; future v2 can redesign

---

## ADR-007: Container Port 5514 for Syslog (Host 514 → 5514)

**Status:** Accepted  
**Date:** 2026-11-03

### Context
Syslog traditionally uses privileged port 514. Containers shouldn't run as root.

### Decision
**Listen on container port 5514**, map host port 514 → 5514 in Docker Compose.

### Rationale
| Approach | Pros | Cons |
|----------|------|------|
| **Container 5514** | Non-root; standard Docker practice | Port mapping required |
| **Container 514** | No mapping | Requires `CAP_NET_BIND_SERVICE` or root |

### Consequences
- Docker Compose: `ports: ["514:5514/udp", "514:5514/tcp"]`
- Syslog config uses `SYSLOG_UDP_PORT=5514`, `SYSLOG_TCP_PORT=5514`
- External senders use host:514 (standard)

---

## ADR-008: `ingested_at` Column for Retention (Not Original Timestamp)

**Status:** Accepted  
**Date:** 2026-11-03

### Context
Assignment requires 7-day retention. Existing system deletes by original `timestamp` which breaks for historical sample data.

### Decision
**Add `ingested_at` column** (timestamp when event was ingested). Retention uses `ingested_at`. Original `timestamp` preserved for analysis.

### Implementation
```sql
-- Step 1: Add column nullable, no default
ALTER TABLE "security_logs" ADD COLUMN ingested_at TIMESTAMPTZ;

-- Step 2: Backfill using created_at (actual ingestion time)
-- Migration-time fallback for any edge cases without created_at
UPDATE "security_logs" 
SET ingested_at = COALESCE(created_at, '<migration_timestamp>');

-- Step 3: Add DEFAULT now() and NOT NULL
ALTER TABLE "security_logs" ALTER COLUMN ingested_at SET DEFAULT now();
ALTER TABLE "security_logs" ALTER COLUMN ingested_at SET NOT NULL;

-- Step 4: Create index
CREATE INDEX ix_security_logs_ingested_at ON "security_logs" (ingested_at);
```

### Consequences
- **Positive:** Sample data with old timestamps retained for 7 days after ingestion; new events correctly expire
- **Negative:** Schema change (mitigated via Alembic migration)
- **Migration:** Multi-step: nullable column → backfill using `created_at` → add default + NOT NULL → index

---

## ADR-016: Strict Tenant Isolation (ADMIN Scoped to Own Tenant)

**Status:** Accepted  
**Date:** 2026-11-03

### Context
Assignment specifies roles: Admin, Viewer. Existing system uses USER, ADMIN. The legacy implementation allowed ADMIN to access all tenants via query parameter.

### Decision
**Both VIEWER (USER) and ADMIN are scoped to their own tenant by default.** Cross-tenant access is prohibited unless a separate platform-level role (e.g., SUPER_ADMIN) is introduced.

### Rationale
| Approach | Pros | Cons |
|----------|------|------|
| **Strict per-tenant** | Zero data leakage; simple mental model; audit-friendly | ADMIN cannot view other tenants' data |
| **ADMIN cross-tenant** | Convenient for multi-tenant admins | Data leakage risk; complex authorization |

### Consequences
- `get_effective_tenant()` always returns `user.tenant` for both roles
- All queries (events, alerts, rules, users, dashboard) scoped to `user.tenant`
- ADMIN user management (create/update/delete users) limited to own tenant
- Future cross-tenant access requires explicit SUPER_ADMIN role

---

## ADR-017: Separate Email Feature Toggles

**Status:** Accepted  
**Date:** 2026-11-03

### Context
The legacy backend used a single `ALERT_EMAIL_ENABLED` for all email. Need independent control over OTP emails, alert emails, and SMTP connectivity.

### Decision
Use **three independent environment variables**:
- `SMTP_ENABLED` — master switch for SMTP connectivity
- `OTP_EMAIL_ENABLED` — enable/disable OTP verification emails
- `ALERT_EMAIL_ENABLED` — enable/disable alert notification emails

All share same SMTP credentials when enabled.

### Consequences
- OTP emails can work while alert emails disabled (or vice versa)
- SMTP can be disabled entirely without code changes
- Clear separation of concerns for testing and production

---

## ADR-018: Email Idempotency via Stable Notification IDs

**Status:** Accepted  
**Date:** 2026-11-03

### Context
Email retries must not create duplicate notifications or send duplicate emails. The legacy backend had no persistent email tracking.

### Decision
**Three-layer idempotency:**
1. **Stable notification ID**: `alert:{alert_id}:type:{email_type}:to:{email}` — retries update same record
2. **Database unique constraint**: `(alert_id, recipient_email)` — prevents duplicate notifications per alert per recipient
3. **Alert deduplication**: Existing `dedupeKey` + cooldown prevents duplicate alerts

Notification records created/updated asynchronously; alert creation never blocked by SMTP.

---

## ADR-009: Pydantic v2 for All Request/Response Validation

**Status:** Accepted  
**Date:** 2026-11-03

### Context
Need request validation, response serialization, OpenAPI schema generation.

### Decision
Use **Pydantic v2** for all schemas (`app/schemas/`).

### Rationale
| Feature | Pydantic v2 | Alternatives |
|---------|-------------|--------------|
| **Performance** | 5-50x faster v1 | marshmallow: slower |
| **FastAPI Integration** | Native | Manual |
| **OpenAPI Generation** | Automatic | Manual |
| **Type Safety** | Excellent | Good |
| **Alias Support** | ✅ | ⚠️ |

### Consequences
- All request bodies validated automatically
- Response models serialize with aliases (e.g., `create_at` → `createAt`)
- OpenAPI spec at `/openapi.json` drives frontend type generation

---

## ADR-010: Role Mapping — USER = VIEWER, ADMIN = ADMIN

**Status:** Accepted  
**Date:** 2026-11-03

### Context
Assignment specifies roles: Admin, Viewer. Existing system uses: USER, ADMIN.

### Decision
**Map directly:** `USER` role = Viewer permissions, `ADMIN` role = Admin permissions. No schema change.

### Rationale
| Option | Pros | Cons |
|--------|------|------|
| **Direct Mapping** | Zero DB changes; existing data works | Name mismatch with assignment |
| **Rename Roles** | Matches assignment | Destructive migration; breaks existing auth |

### Consequences
- Authorization checks use `role == "ADMIN"` for admin, `role == "USER"` for viewer
- Documentation notes the mapping
- Frontend already uses `role === "ADMIN"` checks

---

## ADR-011: OpenAPI-Driven Frontend Type Generation

**Status:** Accepted  
**Date:** 2026-11-03

### Context
Frontend has manual TypeScript types for API. Keeping them in sync is error-prone.

### Decision
**Generate TypeScript types from FastAPI OpenAPI spec** in CI.

### Implementation
```bash
# Frontend CI step
npx openapi-typescript http://backend:4500/openapi.json -o src/types/api.generated.ts
# Or use orval for React Query hooks
npx orval --input http://backend:4500/openapi.json --output src/api/generated
```

### Consequences
- **Positive:** Contract drift impossible; types always match backend
- **Negative:** Build dependency on running backend (or static spec)
- **Mitigation:** Commit generated types; update on backend changes

---

## ADR-012: Separate Worker Processes (Not In-Process)

**Status:** Accepted  
**Date:** 2026-11-03

### Context
The legacy backend ran BullMQ workers in separate processes (`email-worker`, `cache-worker`).

### Decision
**Run each worker as separate Docker service** (separate Python process).

### Rationale
| Approach | Pros | Cons |
|----------|------|------|
| **Separate Processes** | Isolation; independent scaling; crash containment | More containers |
| **In-Process** | Simpler deployment | Blocks API; shared memory; crash = API down |

### Consequences
- `email-worker`: `python -m app.workers.email_worker`
- `retention-worker`: `python -m app.workers.retention_worker`
- `cache-worker`: `python -m app.workers.cache_worker`
- Each has own resource limits in Docker Compose

---

## ADR-013: Email Notification Tracking Table

**Status:** Accepted  
**Date:** 2026-11-03

### Context
The legacy backend had no persistent email delivery tracking (only console logs). Assignment requires email notifications.

### Decision
**Add `email_notifications` table** to track delivery status, retries, failures.

### Schema
```sql
CREATE TABLE "email_notifications" (
    id VARCHAR(25) PRIMARY KEY,
    alert_id VARCHAR(25) REFERENCES "alerts"(id),
    tenant VARCHAR(100) NOT NULL,
    recipient_email VARCHAR(255) NOT NULL,
    subject VARCHAR(500) NOT NULL,
    status "EmailStatus" DEFAULT 'pending',
    attempts INT DEFAULT 0,
    last_attempt_at TIMESTAMPTZ,
    last_error TEXT,
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

### Consequences
- **Positive:** Visibility into email delivery; debugging; compliance
- **Negative:** New table (non-destructive)
- **Migration:** Simple `CREATE TABLE` via Alembic

---

## ADR-014: Structured JSON Logging (structlog)

**Status:** Accepted  
**Date:** 2026-11-03

### Context
Need production-grade observability for debugging and monitoring.

### Decision
Use **`structlog`** with JSON output for all logging.

### Configuration
```python
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
)
```

### Consequences
- All logs are parseable JSON
- Consistent fields: `timestamp`, `level`, `logger`, `event`, `context...`
- Compatible with Loki, Datadog, Elasticsearch

---

## ADR-015: No ORM-Generated Migrations for Baseline

**Status:** Accepted  
**Date:** 2026-11-03

### Context
Alembic autogenerate compares models to DB. Since DB already has Prisma schema, first migration must be a **baseline** (empty).

### Decision
**Verify baseline is empty** before stamping. Never apply autogenerate that creates tables.

### Process
```bash
# 1. Write models matching Prisma exactly
# 2. Generate baseline
alembic revision --autogenerate -m "baseline_from_prisma"
# 3. INSPECT — must be empty upgrade/downgrade
cat migrations/versions/xxx_baseline_from_prisma.py
# 4. If empty: stamp
alembic stamp head
# 5. If NOT empty: fix models, repeat
```

### Consequences
- Prevents accidental `DROP TABLE` / `CREATE TABLE`
- Ensures models match reality before any real migrations
- Baseline becomes starting point for `ingested_at` and future changes

---

## Summary of Key Decisions

| ADR | Decision | Impact |
|-----|----------|--------|
| 001 | FastAPI | Framework foundation |
| 002 | SQLAlchemy + Alembic | Database layer |
| 003 | `arq` | Background jobs |
| 004 | `aiosmtplib` | Email |
| 005 | Exact Schema Preservation | Zero data risk |
| 006 | Exact Auth Contract | Frontend compatibility |
| 007 | Container Port 5514 | Security + standards |
| 008 | `ingested_at` for Retention | Correct retention behavior |
| 009 | Pydantic v2 | Validation + OpenAPI |
| 010 | USER=Viewer, ADMIN=Admin | Zero migration |
| 011 | OpenAPI → TypeScript | Contract sync |
| 012 | Separate Worker Processes | Reliability |
| 013 | Email Notification Table | Observability |
| 014 | structlog JSON | Observability |
| 015 | Empty Baseline Verification | Migration safety |

---

**End of Architecture Decisions**