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

Host port 514 is bound by Docker and must be free on the host. On Docker
Desktop/WSL2, or if another service already uses 514, use
`SYSLOG_HOST_PORT=5514` and send to 5514 instead.

> **Security:** Syslog on 514 is unauthenticated and unencrypted. Never expose
> it directly to the public Internet. Bind the host port to a private/LAN
> address (`SYSLOG_BIND_IP=10.0.0.5`), restrict the source networks in the host
> firewall, and optionally set `SYSLOG_ALLOWED_CIDRS` for an application-level
> allowlist. For Internet-facing ingestion use the HTTPS endpoint instead.
>
> Docker Desktop/WSL2 may SNAT forwarded packets, in which case the listener
> sees the Docker VM/gateway address rather than the device address. Use the
> host firewall for source filtering there; `SYSLOG_ALLOWED_CIDRS` is reliable
> when the original peer address survives port forwarding (typical on a Linux
> Docker host).

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `SYSLOG_ENABLED` | true | Master switch; `false` starts neither UDP nor TCP |
| `SYSLOG_UDP_PORT` | 5514 | UDP listen port (container); `0` disables UDP |
| `SYSLOG_TCP_PORT` | 5514 | TCP listen port (container); `0` disables TCP |
| `SYSLOG_BIND_IP` | 0.0.0.0 | Interface the listener binds to inside the container |
| `SYSLOG_ALLOWED_CIDRS` | (empty) | Optional comma-separated source CIDRs; empty = allow all (firewall still required) |
| `SYSLOG_DB_RETRY_ATTEMPTS` | 3 | Bounded retries for transient database errors |
| `SYSLOG_DB_RETRY_BACKOFF_SECS` | 0.25 | Initial exponential backoff between retries |
| `SYSLOG_MAX_INFLIGHT` | 1000 | Max concurrent in-flight UDP datagrams |
| `INGEST_HEALTH_PORT` | 8090 | Loopback-only health endpoint port |
| `SYSLOG_TENANT` | demoA | Tenant for all native Syslog messages |
| `SYSLOG_SOURCE` | firewall | Default source when the message has no `source=` |
| `DATABASE_URL` | required | PostgreSQL connection string |
| `REDIS_URL` | redis://redis:6379 | Redis for cache invalidation |
| `INGEST_DEFAULT_TENANT` | demoA | Pipeline fallback tenant |

## Health check

The container exposes `GET http://127.0.0.1:8090/healthz` (never published).
It runs `SELECT 1` against PostgreSQL, verifies every *enabled* listener is
still serving, and reports counters (`received`, `accepted`, `invalid`,
`denied`, `overloaded`, `retried`, `retry_exhausted`, `dropped`). It returns
`200` only when the database is reachable and all enabled listeners are up;
`503` otherwise. A UDP-only deployment (`SYSLOG_TCP_PORT=0`) is healthy
without TCP.

## Failure handling

- Transient database errors are retried a bounded number of times with
  exponential backoff, then counted and logged as dropped.
- Validation errors are never retried; they are counted/logged and dropped.
- Source addresses outside `SYSLOG_ALLOWED_CIDRS` are rejected before parsing.
- No Kafka/RabbitMQ/broker is involved: the listener writes through the same
  `IngestionService` as the HTTP and file ingestion paths.

## Tenant resolution

Syslog has no tenant field. Every message received by this listener is written
to the tenant configured by `SYSLOG_TENANT`, with `INGEST_DEFAULT_TENANT` as the
pipeline fallback. The source comes from a message-level `source=` field when
present, otherwise from `SYSLOG_SOURCE`. This deployment is single-tenant for
native Syslog; run separate ingest containers with different `SYSLOG_TENANT`
values if you need multiple native-Syslog tenants.

The listener does not accept a tenant from the sending device, so a device
cannot write into another tenant. The limitation is that every device reaching
one container lands in the same tenant: there is no per-device or per-source
tenant mapping.


## Running standalone

```bash
# Build from the repository root (the image includes shared backend code)
docker build -f ingest/Dockerfile -t lms-ingest .

# Run (bind host port 514 to a private interface only)
docker run -d \
  --name lms-ingest \
  -p 10.0.0.5:514:5514/udp -p 10.0.0.5:514:5514/tcp \
  -e DATABASE_URL=postgresql+asyncpg://logs:pass@db:5432/logs_manager \
  -e SYSLOG_TENANT=demoA \
  -e SYSLOG_ALLOWED_CIDRS=10.0.0.0/8 \
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
