# API Contract — FastAPI Backend

**Version:** 1.0  
**Date:** 2026-11-03  
**Status:** Active (implemented and covered by the pytest suite)

---

## 1. Overview

This document describes the HTTP contract of the FastAPI backend. Paths, methods, JSON shapes, status codes, error format, and cookie-based authentication are the contract the React frontend consumes (and remain compatible with the original API the frontend was built against).

All endpoints preserve:
- URL paths
- HTTP methods
- Request/response JSON structure
- Query parameters
- Status codes
- Error response format
- Cookie-based authentication

---

## 2. Authentication Endpoints (`/api/auth`)

### 2.1 POST `/api/auth/login`

| Aspect | Contract |
|--------|---------|
| **Method** | POST |
| **Path** | `/api/auth/login` |
| **Auth** | None |
| **Request Body** | `{ email: string, password: string }` |
| **Response (200)** | `{ message: string, userData: UserPublic }` |
| **Cookies Set** | `accessToken` (15m), `refreshToken` (30d) HttpOnly; `XSRF-TOKEN` (30d, readable by JS for double-submit CSRF) |
| **Errors** | 401 (invalid credentials), 403 (inactive account or tenant), 422 (invalid body/email), 429 (lockout), 500 |

**UserPublic** (no password):
```json
{
  "id": 1,
  "username": "admin",
  "email": "admin@demo.local",
  "role": "ADMIN",
  "tenant": "demoa",
  "status": "ACTIVE",
  "createAt": "2026-01-01T00:00:00.000Z",
  "updatedAt": "2026-01-01T00:00:00.000Z"
}
```

**Registration / OTP / password recovery:** `POST /api/auth/register`, `POST /api/auth/verify-Otp`, and `POST /api/auth/confirm-password` are **not implemented**. Accounts are admin-provisioned with `POST /api/create-user`; there is no public self-registration or OTP flow.

### 2.5 POST `/api/auth/logout`

| Aspect | Contract |
|--------|---------|
| **Method** | POST |
| **Path** | `/api/auth/logout` |
| **Auth** | Required |
| **Response (200)** | `{ message: "Loggedout successfully" }` |
| **Cookies** | Clear `accessToken`, `refreshToken` |

### 2.6 GET `/api/auth/auth-check`

| Aspect | Contract |
|--------|---------|
| **Method** | GET |
| **Path** | `/api/auth/auth-check` |
| **Auth** | Required |
| **Response (200)** | `{ message, user: { id, username, email, role, tenant, status } }` |
| **Errors** | 401 (unauthenticated) |

---

## 3. Ingestion Endpoints (`/api`)

### 3.1 POST `/api/ingest` (Single Event)

| Aspect | Contract |
|--------|---------|
| **Method** | POST |
| **Path** | `/api/ingest` |
| **Auth** | API Key (`X-API-Key`) |
| **Request Body** | Single event object |
| **Response (200/400/422)** | `{ success: boolean, eventId?: string, message?: string, alerts?: Alert[], ingested?: number, rejected?: number }` |
| **Rate Limit** | `INGEST_RATE_LIMIT` per authenticated session or client IP (default `600/minute`) |

**Event Object Example:**
```json
{
  "source": "api",
  "tenant": "demoA",
  "event_type": "login_failed",
  "user": "alice",
  "src_ip": "203.0.113.77",
  "severity": 7,
  "action": "LOGIN",
  "description": "Failed password for alice"
}
```

### 3.2 POST `/api/ingest/batch` (Batch)

| Aspect | Contract |
|--------|---------|
| **Method** | POST |
| **Path** | `/api/ingest/batch` |
| **Auth** | API Key (`X-API-Key`) |
| **Content-Type** | `application/json` |
| **JSON Body** | Array OR `{ events: [], source?, tenant? }` |
| **Response (200/400)** | `{ success, ingested, rejected, parsed, errors, alerts }` |
| **Max Events** | `INGEST_BATCH_MAX_EVENTS` (1000) |
| **Rate Limit** | `INGEST_RATE_LIMIT` per authenticated session or client IP (default `600/minute`) |

**Supported Formats:** JSON array, JSONL/NDJSON, CSV

### 3.2.1 POST `/api/ingest/file` (File Upload)

| Aspect | Contract |
|--------|---------|
| **Method** | POST |
| **Path** | `/api/ingest/file` |
| **Auth** | API Key (`X-API-Key`) |
| **Content-Type** | `multipart/form-data` |
| **File Field** | `file` (FastAPI `UploadFile`); optional form fields `source`, `tenant` |
| **Response (200/400)** | `{ success, ingested, rejected, parsed, format, errors, alerts }` |
| **Max File Size** | `INGEST_MAX_FILE_BYTES` (10MB) |
| **Supported Formats** | JSON array, JSONL/NDJSON, CSV, Syslog text, CloudTrail |

### 3.3 POST `/api/ingest/syslog` (HTTPS Syslog)

The HTTPS counterpart to the self-hosted native UDP/TCP listener. Hosted SaaS
uses this endpoint because Render/Vercel do not expose raw Syslog ports.

| Aspect | Contract |
|--------|---------|
| **Method** | POST |
| **Path** | `/api/ingest/syslog` |
| **Auth** | API Key (`X-API-Key`) only; JWT cookies are not accepted |
| **Content-Type** | `text/plain` (newline-delimited syslog) or `application/json` |
| **JSON Body** | `{ "lines": ["<syslog line>", "..."], "tenant": "optional" }` |
| **Tenant** | Taken from the API key. A `tenant` in the query string or JSON body must match the key or the request returns **403**. |
| **Response (202)** | `{ "accepted": number, "rejected": number, "errors": [{ "line": number, "error": string }] }` |
| **Limits** | `INGEST_HTTP_SYSLOG_MAX_BYTES` (1 MiB) and `INGEST_HTTP_SYSLOG_MAX_LINES` (1000); larger requests return **413** |
| **Rate Limit** | `INGEST_RATE_LIMIT` per authenticated session or client IP (default `600/minute`) |

Events are parsed with the same `parse_syslog_message` path as the native
listener and are tagged `transport=http-syslog`.

**Text example:**
```bash
curl -X POST https://<project>.vercel.app/api/ingest/syslog \
  -H "Content-Type: text/plain" \
  -H "X-API-Key: <tenant-api-key>" \
  --data-binary @samples/syslog_firewall.log
```

**JSON example:**
```json
{
  "lines": [
    "<190>Oct 30 22:15:01 router01 source=network action=ALLOW src=192.168.1.10 dst=1.1.1.1 msg=\"outbound https\""
  ]
}
```

Traditional devices that only speak Syslog can use the local Vector or rsyslog
forwarder in `samples/forwarder/` to post their messages to this endpoint.

---

## 4. Log Search Endpoint (`/api`)

### 4.1 GET `/api/get-logs`

| Aspect | Contract |
|--------|---------|
| **Method** | GET |
| **Path** | `/api/get-logs` |
| **Auth** | JWT required |
| **Query Params** | `tenant`, `source`, `action`, `severity`, `eventType`, `date`, `search`, `limit`, `cursor` |
| **Pagination** | Cursor-based (`cursor` = last event ID) |
| **Response (200)** | `{ logs: LogWithSeverityLevel[], newCursor: string|null, prevCursor: string|null, total: number }` |

**LogWithSeverityLevel:**
```json
{
  "id": "a1b2c3d4e5f67890...",
  "action": "DENY",
  "user": "alice",
  "srcIp": "203.0.113.77",
  "source": "FIREWALL",
  "tenant": "demoA",
  "eventType": "firewall_deny",
  "severity": 5,
  "timestamp": "2026-10-30T22:14:15.000Z",
  "severityLevel": "medium"
}
```

**Severity Mapping (backend):**
- `0-3` → `"low"`
- `4-6` → `"medium"`
- `7-8` → `"high"`
- `9-10` → `"critical"`

**Tenant Scoping:**
- `VIEWER` (role=VIEWER): Ignores `tenant` query param, forces `tenant = user.tenant`
- `ADMIN`: Can override `tenant` via query param, or see all tenants when empty
- Cross-tenant access: PROHIBITED for VIEWER, ALLOWED for ADMIN

### 4.2 DELETE `/api/delete-log/:logId`

| Aspect | Contract |
|--------|---------|
| **Method** | DELETE |
| **Path** | `/api/delete-log/{logId}` |
| **Auth** | ADMIN required |
| **Response** | 200 `{ message }` |

---

## 5. Dashboard Endpoints (`/api`)

### 5.1 GET `/api/dashboard` (Admin)

| Aspect | Contract |
|--------|---------|
| **Method** | GET |
| **Path** | `/api/dashboard` |
| **Auth** | JWT required |
| **Query Params** | `tenant` (optional). VIEWER is forced to `user.tenant`; ADMIN can request a tenant or use empty/`all` for all tenants |
| **Response (200)** | Same (tenant-scoped per rules above) |

**DashboardStats (Key Fields):**
```json
{
  "totalEvents": 1234,
  "topIPs": [{ "ip": "203.0.113.77", "count": 45 }],
  "topUsers": [{ "user": "alice", "count": 30 }],
  "topEventTypes": [{ "type": "firewall_deny", "count": 100 }],
  "eventsBySource": [{ "tenant": "demoA", "timestamp": "...", "_count": { "id": 50 }, "source": "FIREWALL" }],
  "alertsByDay": [{ "tenant": "demoA", "triggeredAt": "...", "_count": { "id": 3 } }],
  "alertsRuleByDay": [{ "tenant": "demoA", "createdAt": "...", "_count": { "id": 1 } }],
  "recentAlert": [AlertRecord...],
  "severityCounts": [{ "severity": 5, "count": 100 }],
  "sources": [{ "source": "FIREWALL", "_count": 500, "latestEventAt": "..." }],
  "eventsByTenant": [{ "tenant": "demoA", "count": 1000 }],
  "alertCountsByStatus": [{ "status": "open", "count": 5 }],
  "alertCountsBySeverity": [{ "severity": "high", "count": 3 }],
  "ruleCountsByEnabled": [{ "enabled": true, "count": 2 }],
  "tenants": [{ "tenant": "demoA" }]
}
```

**`/api/user-dashboard/:userId`:** not implemented; viewers use `GET /api/dashboard` scoped to their own tenant.

---

## 6. Alert Endpoints (`/api`)

### 6.1 GET `/api/get-alerts`

| Aspect | Contract |
|--------|---------|
| **Method** | GET |
| **Path** | `/api/get-alerts` |
| **Auth** | JWT required |
| **Query Params** | `tenant`, `status`, `severity`, `search`, `limit`, `cursor`. VIEWER is forced to `user.tenant`; ADMIN can request a tenant or use empty/`all` for all tenants |
| **Pagination** | Cursor-based (`newCursor`) |
| **Response (200)** | `{ alerts: AlertWithRule[], hasNextPage: boolean, newCursor: string|null }` |

**AlertWithRule:**
```json
{
  "id": "a1b2c3d4e5f67890...",
  "tenant": "demoA",
  "title": "Alert: Brute force - repeated failures",
  "description": "Repeated failed logins from 203.0.113.7 exceeded 5 attempts in 5 minutes.",
  "severity": "high",
  "status": "open",
  "triggeredAt": "2026-10-30T22:20:00.000Z",
  "eventIds": ["a1b2c3d4e5f67890...", "b2c3d4e5f67890a1..."],
  "rule": { "name": "Brute force - repeated failures", "description": "..." },
  "dedupeKey": "rule-id:repeated_failures:srcIp:203.0.113.7:ad_logon_failed"
}
```

### 6.2 PATCH `/api/alerts/:id`

| Aspect | Contract |
|--------|---------|
| **Method** | PATCH |
| **Path** | `/api/alerts/{id}` |
| **Auth** | ADMIN required |
| **Request Body** | `{ status: "open" \| "resolved" }` |
| **Response (200)** | `{ message, alert }` |
| **Validation** | status must be `open` or `resolved` |

---

## 7. Alert Rule Endpoints (`/api`)

### 7.1 GET `/api/get-rules`

| Aspect | Contract |
|--------|---------|
| **Method** | GET |
| **Path** | `/api/get-rules` |
| **Auth** | ADMIN required |
| **Query Params** | `tenant`, `search`, `limit`, `cursor`. VIEWER is forced to `user.tenant`; ADMIN can request a tenant or use empty/`all` for all tenants |
| **Response (200)** | `{ rules: AlertRule[], hasNextPage: boolean, newCursor: string|null }` |

**AlertRule:**
```json
{
  "id": "a1b2c3d4e5f67890...",
  "name": "Brute force - repeated failures",
  "description": "Triggers when one source IP fails to log in 5 times within 5 minutes.",
  "tenant": "demoA",
  "enabled": true,
  "severity": "medium",
  "conditions": [{ "type": "repeated_failures", "threshold": 5, "windowSeconds": 300 }],
  "createdAt": "2026-10-30T22:00:00.000Z",
  "updatedAt": "2026-10-30T22:00:00.000Z"
}
```

### 7.2 POST `/api/create-alertRule`

| Aspect | Contract |
|--------|---------|
| **Method** | POST |
| **Path** | `/api/create-alertRule` |
| **Auth** | ADMIN required |
| **Request Body** | `{ name, tenant, description?, conditions, enabled?, severity? }` |
| **Conditions Validation** | Exactly 1 condition, type-specific required fields |
| **Response (201)** | `{ message, createdRule }` |

### 7.3 PUT `/api/update-rule/:id`

| Aspect | Contract |
|--------|---------|
| **Method** | PUT |
| **Path** | `/api/update-rule/{id}` |
| **Auth** | ADMIN required |
| **Request Body** | Same as create |
| **Response (200)** | `{ message, rule }` |

### 7.4 PATCH `/api/rules/:id/enabled`

| Aspect | Contract |
|--------|---------|
| **Method** | PATCH |
| **Path** | `/api/rules/{id}/enabled?enabled=true` |
| **Auth** | ADMIN required |
| **Query Params** | `enabled` (boolean) |
| **Response (200)** | `{ message, rule }` |

### 7.5 DELETE `/api/delete-rule/:id`

| Aspect | Contract |
|--------|---------|
| **Method** | DELETE |
| **Path** | `/api/delete-rule/{id}` |
| **Auth** | ADMIN required |
| **Validation** | Cannot delete if alerts exist for rule |
| **Response (200)** | `{ message }` |

---

## 8. User Management Endpoints (`/api`)

### 8.1 GET `/api/get-users`

| Aspect | Contract |
|--------|---------|
| **Method** | GET |
| **Path** | `/api/get-users` |
| **Auth** | ADMIN required |
| **Query Params** | Same (scoped to admin's tenant) |
| **Response** | `{ usersList: User[], newCursor, prevCursor? }` |

### 8.2 GET `/api/users/:q` (Frontend infinite query)

| Aspect | Contract |
|--------|---------|
| **Method** | GET |
| **Path** | `/api/users/{q}` |
| **Auth** | ADMIN required |
| **Response** | Paginated users |

### 8.3 POST `/api/create-user`

| Aspect | Contract |
|--------|---------|
| **Method** | POST |
| **Path** | `/api/create-user` |
| **Auth** | ADMIN required |
| **Request Body** | `{ username, email, tenant, role, status, password }` |
| **Response** | Created user |

### 8.4 PUT `/api/update-user`

| Aspect | Contract |
|--------|---------|
| **Method** | PUT |
| **Path** | `/api/update-user` |
| **Auth** | ADMIN required |
| **Request Body** | `{ id, username?, email?, tenant?, role?, status? }` |
| **Response** | Updated user |

### 8.5 DELETE `/api/delete-user/:userId`

| Aspect | Contract |
|--------|---------|
| **Method** | DELETE |
| **Path** | `/api/delete-user/{userId}` |
| **Auth** | ADMIN required |
| **Response** | Success message |

### 8.6 GET `/api/get-all-data`

| Aspect | Contract |
|--------|---------|
| **Method** | GET |
| **Path** | `/api/get-all-data` |
| **Auth** | ADMIN required |
| **Query Params** | `tenant` (optional). Admin cross-tenant view when empty/`all`; otherwise scoped |
| **Response** | Counts for dashboard cards; includes `tenants` when viewing all tenants |

---

## 9. Health Endpoints

### 9.1 GET `/healthz`

| Aspect | Contract |
|--------|---------|
| **Method** | GET |
| **Path** | `/healthz` |
| **Auth** | None |
| **Response (200)** | `{ status: "ok", uptime, timestamp }` |
| **Response (503)** | `{ status: "degraded", database: "unreachable", timestamp }` |

### 9.2 GET `/ready` (New)

| Aspect | Contract |
|--------|---------|
| **Method** | GET |
| **Path** | `/ready` |
| **Auth** | None |
| **Response (200)** | `{ status: "ready", database: "connected", redis: "connected" }` |
| **Purpose** | Kubernetes readiness probe |

---

## 10. Event Detail Endpoint

### 10.1 Current State

**Frontend:** LogsTable row click → no detail view yet (the API is available for the future modal/page).

**Backend:** `GET /api/events/{event_id}` is implemented and tenant-scoped.

### 10.2 Endpoint

| Aspect | Design |
|--------|--------|
| **Method** | GET |
| **Path** | `/api/events/{event_id}` |
| **Auth** | JWT required |
| **Response (200)** | Full event object with all fields including `raw` |
| **Response (404)** | `{ detail: "Event not found" }` |
| **Tenant Scoping** | VIEWERs and tenant-bound ADMINs only see events in their tenant; a platform ADMIN (tenant `NULL`) sees any tenant |

**Frontend Integration:** Add detail modal/page in LogsPage (future enhancement).

---

## 11. Error Response Format

All error responses follow this format:

```json
// 4xx/5xx
{
  "message": "Human-readable error message",
  "error": "ERROR_CODE",  // e.g., "Invalid_Error", "unauthenticated", "unauthorized"
  "code": null,           // optional provider/database code when available
  "meta": {}              // optional context
}
```

**Common Error Codes:**
- `Invalid_Error` — Validation failed
- `unauthenticated` — Not authenticated / token invalid
- `unauthorized` — Insufficient permissions
- `userExist` — Email already registered
- `existedRule` — Alert rule name exists in tenant
- `overLimit` — Rate limit exceeded

---

## 12. Cookie Specification

| Cookie | Name | Max-Age | HttpOnly | Secure | SameSite | Path |
|--------|------|---------|----------|--------|----------|------|
| Access Token | `accessToken` | 900s (15m) | Yes | `COOKIE_SECURE` | `COOKIE_SAME_SITE` (lax/none) | `/` |
| Refresh Token | `refreshToken` | 2592000s (30d) | Yes | `COOKIE_SECURE` | `COOKIE_SAME_SITE` | `/` |
| CSRF Token | `XSRF-TOKEN` | 2592000s (30d) | No | `COOKIE_SECURE` | `COOKIE_SAME_SITE` | `/` |

**Production:** `COOKIE_SECURE=true`, `COOKIE_SAME_SITE=lax` for the same-origin
Vercel/Caddy proxy. Use `none` only when the browser calls the API directly
from a different site.
**Development:** `COOKIE_SECURE=false`, `COOKIE_SAME_SITE=lax`

---

## 13. CORS Configuration

```python
# FastAPI CORS middleware
allow_origins = settings.CORS_ORIGINS  # ["http://localhost:5173", "https://app.example.com"]
allow_credentials = True
allow_methods = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
allow_headers = ["Content-Type", "Authorization", "X-API-Key", "Cookie"]
expose_headers = ["Set-Cookie"]
```

---

## 14. OpenAPI / TypeScript Generation

### 14.1 FastAPI OpenAPI Spec

Available at: `GET /openapi.json`

Includes all endpoints, schemas, security schemes (cookie + API key).

### 14.2 Frontend Type Generation (CI Step)

```bash
# In frontend
npx openapi-typescript http://localhost:4500/openapi.json -o src/types/api.generated.ts
# OR using orval
npx orval --input http://localhost:4500/openapi.json --output src/api/generated
```

Generated types replace manual `types.ts` for API contracts.

---

## 15. Compatibility Checklist

For each endpoint, verify:

- [ ] Same URL path
- [ ] Same HTTP method
- [ ] Same query parameter names and types
- [ ] Same request body structure
- [ ] Same response JSON structure (field names, types, nesting)
- [ ] Same status codes for success/error
- [ ] Same error response format
- [ ] Same authentication behavior (cookies, API key, roles)
- [ ] Same tenant scoping logic
- [ ] Same pagination (cursor-based)
- [ ] Same cookie names, options, expiration
- [ ] Same CORS behavior

---

**End of API Contract**
