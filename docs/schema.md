# Event Schema Reference

This document describes the common normalized event schema used across all log sources in the SIEM system. Every log entry, regardless of origin, is normalized to this schema for unified search, dashboards, and alerting.

## Field Table

| Field | SQL Column | Type | Required | Description | Sources |
|-------|------------|------|----------|-------------|---------|
| **id** | `id` | VARCHAR(64) | ✓ | Deterministic SHA256 hash for deduplication | All |
| **@timestamp / ts** | `ts` | TIMESTAMPTZ | ✓ | Event timestamp (UTC) | All |
| **tenant** | `tenant` | VARCHAR(100) | ✓ | Tenant identifier (demoA, demoB, etc.) | All |
| **source** | `source` | ENUM | ✓ | Source system type | All |
| **vendor** | `vendor` | VARCHAR(100) | ✗ | Vendor name | Firewall, AWS, M365, AD |
| **product** | `product` | VARCHAR(100) | ✗ | Product name | Firewall, AWS, M365, AD |
| **event_type** | `event_type` | VARCHAR(200) | ✓ | Canonical event type | All |
| **event_subtype** | `event_subtype` | VARCHAR(200) | ✗ | Subclassification | API, Crowdstrike |
| **severity** | `severity` | INT | ✓ | 0-10 scale (10 = most severe) | All |
| **action** | `action` | ENUM | ✗ | Action taken (allow/deny/login/etc) | Firewall, API, AWS, AD |
| **action_detail** | `action_detail` | VARCHAR(255) | ✗ | Original vendor action | Crowdstrike |
| **outcome** | `outcome` | ENUM | ✗ | Result (success/failure/unknown) | API, M365, AD |
| **src_ip** | `src_ip` | VARCHAR(45) | ✗ | Source IP address | Firewall, API, AWS, M365, AD |
| **src_port** | `src_port` | INT | ✗ | Source port | Firewall |
| **dst_ip** | `dst_ip` | VARCHAR(45) | ✗ | Destination IP address | Firewall |
| **dst_port** | `dst_port` | INT | ✗ | Destination port | Firewall |
| **protocol** | `protocol` | VARCHAR(20) | ✗ | Network protocol | Firewall |
| **user_name** | `user_name` | VARCHAR(255) | ✗ | User identifier | API, AWS, M365, AD |
| **host** | `host` | VARCHAR(255) | ✗ | Hostname/device | Crowdstrike, AD |
| **process** | `process` | VARCHAR(255) | ✗ | Process name | Crowdstrike |
| **url** | `url` | TEXT | ✗ | Requested URL | API |
| **http_method** | `http_method` | VARCHAR(10) | ✗ | HTTP method | API |
| **status_code** | `status_code` | INT | ✗ | HTTP status | API |
| **rule_name** | `rule_name` | VARCHAR(255) | ✗ | Firewall rule name | Firewall |
| **rule_id** | `rule_id` | VARCHAR(255) | ✗ | Firewall rule ID | Firewall |
| **cloud_account_id** | `cloud_account_id` | VARCHAR(100) | ✗ | AWS account ID | AWS |
| **cloud_region** | `cloud_region` | VARCHAR(100) | ✗ | AWS region | AWS |
| **cloud_service** | `cloud_service` | VARCHAR(100) | ✗ | AWS service | AWS |
| **event_id** | `event_id` | INT | ✗ | Windows event ID | AD |
| **logon_type** | `logon_type` | INT | ✗ | Windows logon type | AD |
| **raw** | `raw` | JSONB | ✓ | Original raw data | All |
| **_tags** | `_tags` | TEXT[] | ✓ | Search tags | All |
| **ingested_at** | `ingested_at` | TIMESTAMPTZ | ✓ | Server ingest time | All |

## Source Field Mappings

### 1. Firewall/Syslog

| Syslog Field | Normalized Field | Notes |
|--------------|------------------|-------|
| `src` | `src_ip` | Source IP |
| `dst` | `dst_ip` | Destination IP |
| `spt` | `src_port` | Source port |
| `dpt` | `dst_port` | Destination port |
| `proto` | `protocol` | UDP/TCP/etc |
| `policy` | `rule_name` | Firewall rule/policy name |
| PRI (severity) | `severity` | Production derives severity as `PRI % 8`, so PRI 134 → `134 % 8` = **6**. The low three PRI bits are the RFC 5424 severity code (0-7) used directly on the 0-10 scale; the facility bits are discarded. |
| `action` (key=value) | `action` | deny→denied, allow→allowed |
| `msg` | `raw` | Preserved in raw JSON |

### 2. Network Router

| Syslog Field | Normalized Field | Notes |
|--------------|------------------|-------|
| `event` | `event_type` | link-down, etc. |
| `if` | `tags` | Interface name |
| `reason` | `raw` | Preserved |
| `mac` | `raw` | Preserved |
| PRI (severity) | `severity` | `PRI % 8` (PRI 190 → **6**); see the firewall row above. |
| `event_type` | `network` | Source enum |

### 3. HTTP API

| Input Field | Normalized Field | Notes |
|-------------|------------------|-------|
| `ip` | `src_ip` | |
| `user` | `user_name` | |
| `event_type` | `event_type` | |
| `reason` | `event_subtype` | |
| `@timestamp` | `ts` | RFC3339 parsing |
| `tenant` | `tenant` | From API key/JWT |
| `action` (derived) | `action` | app_login_failed → login, failed → failure |

### 4. CrowdStrike

| Input Field | Normalized Field | Notes |
|-------------|------------------|-------|
| `host` | `host` | |
| `process` | `process` | |
| `severity` | `severity` | 0-10 scale |
| `action` | `action_detail` | Original action preserved |
| `event_type` | `event_type` | malware_detected |
| `action` (derived) | `action` | malware_detected → alert |
| `sha256` | `tags`/`raw` | Preserved |

### 5. AWS CloudTrail

| Input Field | Normalized Field | Notes |
|-------------|------------------|-------|
| `eventName` | `event_type` | CreateUser, DeleteUser, etc. |
| `sourceIPAddress` | `src_ip` | |
| `userIdentity.arn` / `userName` | `user_name` | |
| `awsRegion` | `cloud_region` | |
| `eventSource` | `cloud_service` | |
| `recipientAccountId` | `cloud_account_id` | |
| `action` (derived) | `action` | Create* → create, Delete* → delete |
| `eventId` | `event_id` | CloudTrail event ID |

### 6. Microsoft 365

| Input Field | Normalized Field | Notes |
|-------------|------------------|-------|
| `Operation` | `event_type` | UserLoggedIn, etc. |
| `ClientIP` | `src_ip` | |
| `UserId` | `user_name` | |
| `ResultStatus` | `outcome` | Success/Failure |
| `Workload` | `tags` | Exchange, SharePoint, etc. |
| `action` (derived) | `action` | UserLoggedIn → login |

### 7. Microsoft AD/Windows Security

| Input Field | Normalized Field | Notes |
|-------------|------------------|-------|
| `event_id` (4624/4625) | `event_id` | Windows event ID |
| `TargetUserName` | `user_name` | |
| `IpAddress` | `src_ip` | |
| `Computer` | `host` | |
| `LogonType` | `logon_type` | |
| `action` (derived) | `action` | 4624 → login, 4625 → login, 4634 → logout |
| `outcome` (derived) | `outcome` | 4624 → success, 4625 → failure |

## ID Generation

The `id` field is a deterministic SHA256 hash computed as:
```
hash = SHA256(tenant + "|" + source + "|" + ts.isoformat() + "|" + sorted(raw.items()))
```

This enables:
- Deduplication of identical events
- Idempotent inserts
- Correlation across systems

## Timestamps

- All timestamps are stored in UTC with timezone
- Syslog timestamps without year assume current year (with Jan/Dec rollover handling)
- Multiple input formats are parsed and normalized to ISO8601

## Severity Mapping

Syslog severity (0=worst, 7=best) → Normalized (0-10, 10=worst):

| Syslog | Normalized | Meaning |
|--------|------------|---------|
| 0 | 10 | Emergency |
| 1 | 9 | Alert |
| 2 | 8 | Critical |
| 3 | 7 | Error |
| 4 | 5 | Warning |
| 5 | 4 | Notice |
| 6 | 2 | Informational |
| 7 | 1 | Debug |

## Database Storage

The `events` table is a single Postgres table (no declarative partitioning). Retention is deletion-based: the worker deletes events older than `RETENTION_DAYS` (default 7). See `docs/schema.png` for the current schema diagram.

### Deduplication

JSON events are deduplicated on the `(id, ts)` tuple: re-sending the same JSON
event returns the same `eventId` and stores a single row. Native syslog events
(UDP/TCP 514) are **not** deduplicated: each identical line is treated as a
separate event, because repeated identical syslog lines are real events and the
threshold alert rules depend on counting them. Do not enable content-hash
dedupe for syslog without accounting for this.

### Indexes

| Index | Columns | Purpose |
|-------|---------|---------|
| `ix_events_tenant_ts_desc` | tenant, ts DESC | Main query pattern (viewer isolation) |
| `ix_events_tenant_source_ts` | tenant, source, ts | Source-filtered queries |
| `ix_events_tenant_src_ip_ts` | tenant, src_ip, ts | IP-based alerting |
| `ix_events_tenant_user_name_ts` | tenant, user_name, ts | User-based queries |
| `ix_events_raw_gin` | raw GIN | Raw JSON search |
| `ix_events_gin_tsvector` | gin__tsvector GIN | Full-text search |