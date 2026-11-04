# Log Manager / Mini SIEM - Architecture

## Data Flow

```
Sources → Ingest → Normalize → Postgres → Search/Dashboard → Alert
```

### Ingestion Paths

1. **Syslog (UDP/TCP port 514)**
   - Listens on port 514 (host: 5514 in Docker)
   - Parses RFC3164/RFC5424 messages
   - Maps facility/severity from PRI field
   - Routes by content: firewall → `firewall` parser, network → `network` parser
   - Tenant mapping: default from `.env` SYSLOG_TENANT or by source IP

2. **HTTP API (POST /ingest)**
   - Accepts single JSON object or batch array
   - Header `X-API-Key` identifies tenant (prevents spoofing)
   - Routes by `source` field to correct mapper
   - Supports `--rewrite-now` flag to replace `@timestamp` with current time

3. **File Batch Upload**
   - POST /ingest/file endpoint
   - Supports JSON/NDJSON files (AWS CloudTrail, M365 Unified Audit Log, AD Event Export)
   - Same mappers as HTTP API, applied iteratively

### Normalization

Each source has a dedicated mapper producing a common schema:

| Field | Description |
|-------|-------------|
| `@timestamp` | RFC3339 timestamp (current year + UTC if not specified) |
| `tenant` | Tenant identifier (demoA, demoB, etc.) |
| `source` | firewall \| crowdstrike \| aws \| m365 \| ad \| api \| network |
| `vendor` | Vendor name (demo, microsoft, crowdstrike, aws) |
| `product` | Product name (ngfw, falcon, Exchange, etc.) |
| `event_type` | Normalized canonical event type |
| `event_subtype` | Additional event classification |
| `severity` (0-10) | Numeric severity score |
| `action` | allow \| deny \| create \| delete \| login \| logout \| alert |
| `src_ip` | Source IP address |
| `src_port` | Source port |
| `dst_ip` | Destination IP address |
| `dst_port` | Destination port |
| `protocol` | Network protocol (tcp, udp, icmp, etc.) |
| `user` | User identifier |
| `host` | Hostname or device ID |
| `process` | Process name |
| `url` | Requested URL |
| `http_method` | HTTP method (GET, POST, etc.) |
| `status_code` | HTTP status code |
| `rule_name` | Alert rule name (if applicable) |
| `rule_id` | Alert rule identifier |
| `cloud.account_id` | AWS account ID / AD domain ID |
| `cloud.region` | AWS region / AD site |
| `cloud.service` | AWS service / M365 workload |
| `raw` | Original raw message/JSON (preserved exactly) |
| `_tags` | Array of tags (e.g., `["malware"]`, `["parse_error"]`) |

### Storage

- **PostgreSQL 16** with JSONB `raw` column
- Table `security_logs` partitioned by `@timestamp` (daily partitions)
- Key indexes: `(tenant, "@timestamp" DESC)`, `src_ip`, `event_type`, `GIN` on `attributes`
- `ingested_at` column records ingestion time (used for 7-day retention)

### Alert Engine

- Background worker evaluates rules every 30-60 seconds
- Brute-force rule: ≥5 failed logins from same `src_ip` within 5 min + 10-min cooldown
- Malware rule: severity ≥ 8 (or event_type = malware_detected)
- Deduplication via `dedupe_key` + cooldown window
- Notification channels: Alerts page (UI), webhook POST, SMTP email (optional)

### Security

- **AuthN**: JWT access/refresh tokens via FastAPI
- **AuthZ**: Admin (all tenants) / Viewer (own tenant only)
- **Tenant isolation**: Middleware enforces `WHERE tenant = jwt.tenant` for Viewers
- **HTTPS**: Caddy reverse proxy with Let's Encrypt (SaaS) or self-signed (appliance)
- **Input validation**: Pydantic models for all request/response schemas
- **Rate limiting**: slowapi with IP-based key function

### Tenant Model

- **Admin**: role=ADMIN, tenant=NULL (access to all tenants)
- **Viewer**: role=VIEWER, tenant=demoA/demoB (isolated to own tenant)
- **JWT claims**: `{sub, role, tenant}`
- **Ingest API key**: Maps to tenant (e.g., demoA-key → demoA, demoB-key → demoB)
- **Syslog tenant**: Mapped by listener configuration or default from .env

### Technology Choices

- **FastAPI (Python)**: Fast development, automatic OpenAPI docs, enum validation, async IO for syslog
- **PostgreSQL (JSONB)**: Single-node sufficient (4GB RAM), partitioning for 7-day retention, GIN indexes for attributes
- **Docker Compose**: Same compose file for appliance (local VM) and SaaS (cloud VM)
- **Caddy reverse proxy**: Automatic Let's Encrypt for SaaS, self-signed fallback for appliance
- **Redis + arq**: Email queue with retry/retry-backoff, cache invalidation
- **Pytest**: 44 tests verified against Neon database
