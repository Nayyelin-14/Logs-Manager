# /ingest — Syslog Ingest Service

Standalone syslog listener (UDP/TCP) that receives firewall and network router
syslog messages, normalizes them using the backend parsers, and inserts
them into PostgreSQL via the shared ingestion pipeline.

## Purpose

The assignment requires syslog UDP/TCP on port 514 as a working ingest source.
This service runs as its own container/process, separate from the backend API,
so syslog traffic does not compete with API requests.

## Ports

| Container port | Host port (appliance) | Protocol |
|---|---|---|
| 5514 | 514 | UDP |
| 5514 | 514 | TCP |

Host port 514 requires root or `cap_net_bind_service`. For local testing without
root, map to a high port (e.g. 5514:5514) and set `SYSLOG_UDP_PORT=5514`.

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `SYSLOG_UDP_PORT` | 5514 | UDP listen port (container) |
| `SYSLOG_TCP_PORT` | 5514 | TCP listen port (container) |
| `SYSLOG_TENANT` | demoA | Default tenant for syslog messages |
| `SYSLOG_SOURCE` | firewall | Default source for syslog messages |
| `DATABASE_URL` | required | PostgreSQL connection string |
| `REDIS_URL` | redis://redis:6379 | Redis for cache invalidation |
| `INGEST_DEFAULT_TENANT` | demoA | Fallback tenant |

## Tenant resolution

Syslog has no tenant field. Tenant is resolved by:
1. `TENANT_PORT_MAP` env var: `port:tenant,port:tenant` (e.g. `5141:demoA,5142:demoB`)
2. Sender-IP → tenant mapping (documented in setup guides)
3. `SYSLOG_TENANT` / `DEFAULT_TENANT` fallback

## Running standalone

```bash
# Build
docker build -t lms-ingest ./ingest

# Run (host port 514 → container 5514)
docker run -d \
  --name lms-ingest \
  -p 514:5514/udp -p 514:5514/tcp \
  -e DATABASE_URL=postgresql+asyncpg://logs:pass@db:5432/logs_manager \
  -e SYSLOG_TENANT=demoA \
  lms-ingest
```

## Testing

Send a sample syslog message:

```bash
# UDP
logger --udp --server 127.0.0.1 --port 514 \
  '<134>Aug 20 12:44:56 fw01 vendor=demo product=ngfw action=deny src=10.0.1.10 dst=8.8.8.8 spt=5353 dpt=53 proto=udp msg="DNS blocked" policy=Block-DNS'

# TCP
echo '<134>Aug 20 12:44:56 fw01 vendor=demo product=ngfw action=deny src=10.0.1.10 dst=8.8.8.8 spt=5353 dpt=53 proto=udp msg="DNS blocked" policy=Block-DNS' | nc 127.0.0.1 514
```

Then query via the API:
```bash
curl -s "http://localhost:4500/api/get-logs?source=firewall&limit=5" -H "Cookie: ..."
```

## Reuse of backend code

This service imports normalizers, parsers, and the ingestion pipeline from
`backend/` (shared Python package). No logic is duplicated.

## Folder mapping

Assignment path `/ingest/` → repo path `ingest/` (this directory).
Backend path `/backend/` → repo path `backend/`.
Frontend path `/frontend/` → repo path `frontend/`.
