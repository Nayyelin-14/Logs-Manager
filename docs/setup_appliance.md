# Self-Hosted Docker Setup Guide (Laptop, Appliance, or VM)

This guide covers running the complete application with `docker-compose.yml` on
a single machine. The same file works on a laptop, an appliance host, or a VM;
only environment settings such as `CADDY_BIND_IP`, `DOMAIN`, ports, and secrets
change. `docker-compose.vm.yml` is an internal image-based deployment artifact
and is not part of the self-hosting path.
 
 ## System Requirements
 
 | Component | Minimum | Recommended |
 |-----------|---------|-------------|
 | CPU | 2 vCPU | 4 vCPU |
 | Memory | 4 GB | 8 GB |
 | Disk | 20 GB | 40 GB |
 | OS | Ubuntu 22.04/24.04 LTS | Ubuntu 24.04 LTS |
 | Ports | 80, 443, 514, 4500 | 80, 443, 514, 4500 |

### Host sizing reality check

The full stack runs PostgreSQL, Redis, the API, the worker, the ingest listener,
and Caddy together, so 4 GB of RAM is a real minimum. A 1 GB VM will swap
heavily even when it appears to start.

For reference, an Azure for Students `Standard_B2ats_v2` has 2 vCPU and only
1 GB of RAM and costs roughly $10-16/month equivalent. Resizing it to a 4 GB
size (`B2pls_v2` or `B2als_v2`) costs roughly $34-38/month, which is far above
a $5/month budget. If your VM has 1 GB, use it only when it is dedicated and
you accept swap, or use the SaaS mode in `docs/setup_saas.md` instead.

## Prerequisites
 
 - Docker Engine 24.x or later
 - Docker Compose plugin
 - 2-4 GB disk space for images
 
## Quick Start

```bash
# Clone the repository
git clone https://github.com/Nayyelin-14/Logs-Manager.git
cd Logs-Manager

# Copy environment template
cp .env.example .env
# Edit .env with your settings (passwords, secrets, DOMAIN, CADDY_BIND_IP)

# Start the stack (standalone local Compose file)
make up

# Wait for the backend readiness check, then seed
make seed

# Access the system
#   UI:        https://localhost/
#   API:       http://localhost:4500
#   Syslog:    UDP/TCP <host-ip>:514 (default; container listens on 5514)
#   API docs:  http://localhost:4500/docs
```

> **Syslog port note:** The host port defaults to **514**, the standard
> firewall/router syslog port, and Compose binds it on **0.0.0.0** by default so
> remote devices on the LAN can reach the appliance. The container always
> listens internally on 5514; only the host mapping changes. Binding 514
> requires the Docker daemon to have permission for low ports (normally true
> when Docker runs as root).
>
> **Never expose port 514 directly to the public Internet.** Syslog UDP/TCP is
> unauthenticated and unencrypted. On an Internet-facing host bind only a
> private interface and allowlist the forwarding devices in the host firewall:
> ```
> # .env — bind the published port to a LAN address, not 0.0.0.0
> SYSLOG_BIND_IP=10.0.0.5
> # Optional application-level allowlist (comma-separated CIDRs)
> SYSLOG_ALLOWED_CIDRS=10.0.0.0/8,192.168.10.0/24
> ```
> Devices outside those CIDRs are rejected before parsing. For ingestion from
> untrusted networks use the HTTPS endpoint (`POST /api/ingest/syslog`) with a
> Vector/rsyslog forwarder instead. See the forwarder docs for retry and
> durability behavior.
>
> Use **5514** instead on Docker Desktop/WSL2, where low-port forwarding can
> fail, or if host port 514 is already in use. Set the override in your local
> `.env` (never commit it):
> ```
> SYSLOG_HOST_PORT=5514
> ```
> Then send with `logger -n <host> -P 5514`.

> **Port conflicts:** If ports 80 or 443 are already in use on your host, override them in `.env`:
> ```
> HTTP_PORT=8088
> HTTPS_PORT=8443
> ```
> Then access the UI at `https://localhost:8443/` and the HTTP redirect at `http://localhost:8088/`.

> **LAN or VM access:** Caddy binds to `127.0.0.1` by default so a laptop is not
> exposed to the network. To reach the UI/API from another machine, set
> `CADDY_BIND_IP=0.0.0.0` and open ports 80/443. For public HTTPS, also set
> `DOMAIN` to a DNS name that points at the host; Caddy obtains the certificate.
> A LAN-only hostname/IP will use Caddy's internal certificate and show a browser
> warning. The same `docker-compose.yml` is used in every case.
 
 ## Manual Deployment
 
 ### 1. Create Environment File
 
 ```bash
 # Copy example
 cp .env.example .env
 
 # Edit for your environment
 nano .env
 ```
 
### 2. Start Services

```bash
# Build and start (using standalone local Compose file)
make up
# Or directly:
docker compose -p lms_local -f docker-compose.yml up -d --build
```

### 3. Verify Health

```bash
# Check container status
docker compose -p lms_local -f docker-compose.yml ps

# Check API health
curl -sk https://localhost/healthz

# Or HTTP redirect to check Caddy
curl -sI http://localhost:80/
```
 
 ## Seed Demo Data
  
 ```bash
 make seed
 # Or:
 docker compose -p lms_local -f docker-compose.yml exec -T backend python scripts/seed_demo_data.py
 ```
 
 This creates:
 - **Tenant `demoA`**: firewall, network, aws sample events
 - **Tenant `demoB`**: additional AWS events
 
 Demo users (after seeding):
 
 | Email | Password | Role | Tenant |
 |-------|----------|------|--------|
 | admin@demo.local | (seed prints on startup) | ADMIN | (all) |
 | viewerA@demo.local | (see seed output) | VIEWER | demoA |
 | viewerB@demo.local | (see seed output) | VIEWER | demoB |
 
## Access URLs

After startup:

| Service | URL |
|---------|-----|
| UI Dashboard | https://localhost/ |
| API | http://localhost:4500 |
| Swagger Docs | http://localhost:4500/docs |
| Syslog UDP | <host-ip>:514 (default; container 5514) |
| Syslog TCP | <host-ip>:514 (default; container 5514) |
 
 ## Environment Variables
 
 Required variables (in `.env`):
 
 ```dotenv
 # Database connection
 DATABASE_URL=postgresql+asyncpg://logs:postgres_pass@db:5432/logs_manager?sslmode=disable
 
 # Authentication
 ACCESS_TOKEN_SECRET=<64-char random string>
 REFRESH_TOKEN_SECRET=<64-char random string>
 
 # Ingestion
 INGEST_API_KEY=<32-char API key>
 INGEST_DEFAULT_TENANT=demoA
 
 # Self-hosted edge binding (127.0.0.1 for laptop, 0.0.0.0 for LAN/VM)
 CADDY_BIND_IP=127.0.0.1
 DOMAIN=localhost

 # Syslog (solely handled by the dedicated ingest container)
 SYSLOG_ENABLED=true
 # Set to a private/LAN address; never publish 514 on a public interface.
 SYSLOG_BIND_IP=0.0.0.0
 SYSLOG_HOST_PORT=514
 SYSLOG_TENANT=demoA
 SYSLOG_SOURCE=firewall
 SYSLOG_UDP_PORT=5514
 SYSLOG_TCP_PORT=5514
 # Optional comma-separated source CIDRs (empty = no app-level filter).
 SYSLOG_ALLOWED_CIDRS=
 SYSLOG_DB_RETRY_ATTEMPTS=3
 SYSLOG_DB_RETRY_BACKOFF_SECS=0.25
 SYSLOG_MAX_INFLIGHT=1000
 INGEST_HEALTH_PORT=8090
 
# Retention
RETENTION_DAYS=7

# Rate limiting (login brute-force protection)
LOGIN_RATE_LIMIT=5/minute
LOGIN_LOCKOUT_ATTEMPTS=5
LOGIN_LOCKOUT_MINUTES=15
```
 
 ## Ingestion Methods
 
 ### HTTP API (Single Event)
 
 ```bash
 curl -X POST http://localhost:4500/ingest \
   -H "Content-Type: application/json" \
   -H "X-API-Key: $INGEST_API_KEY" \
   -d '{
     "tenant": "demoA",
     "source": "api",
     "event_type": "app_login_failed",
     "user": "alice",
     "src_ip": "203.0.113.7",
     "severity": 5
   }'
 ```
 
 ### Syslog (Firewall Sample)
 
 ```bash
 # Send sample syslog
 ./samples/send_syslog.sh udp samples/syslog_firewall.log
 
 # Or use logger (host port 514 by default; use -P 5514 for the Docker Desktop override)
 logger -n 127.0.0.1 -P 514 \
   '<134>Oct 30 22:14:15 fw01 vendor=Demo product=Firewall action=DENY src=10.0.0.5 dst=8.8.8.8 spt=54321 dpt=53 proto=UDP msg="Blocked DNS query"'
 ```
 
 ### File Batch Upload
 
 ```bash
 # JSON array or CSV
 curl -X POST http://localhost:4500/ingest/file \
   -H "X-API-Key: $INGEST_API_KEY" \
   -F "file=@samples/crowdstrike.json"
 ```
 
## Stopping Services

```bash
# Stop but keep data
docker compose -p lms_local -f docker-compose.yml stop

# Stop and remove containers (keeps volumes)
docker compose -p lms_local -f docker-compose.yml down

# Remove all data (including PostgreSQL volumes)
docker compose -p lms_local -f docker-compose.yml down -v
```
  
 ## Viewing Logs
  
 ```bash
 # Follow all logs
 docker compose -p lms_local -f docker-compose.yml logs -f

 # Follow specific service
 docker compose -p lms_local -f docker-compose.yml logs -f backend

# Recent logs only
docker compose -p lms_local -f docker-compose.yml logs --tail=100
```

## Retention Demo

The 7-day retention policy can be demonstrated without touching seed data:

```bash
make demo-retention
```

This inserts an 8-day-old event (purged) and a 6-day-old event (kept) into a
dedicated `retention_test` tenant, runs the retention purge, and prints
before/after counts.

## Data Persistence

PostgreSQL data is persisted in Docker volumes:

```bash
# List volumes
docker volume ls

# Backup database
docker compose -p lms_local -f docker-compose.yml exec db pg_dump -U logs logs_manager > backup.sql

# Restore database
docker compose -p lms_local -f docker-compose.yml exec -T db psql -U logs -d logs_manager < backup.sql
```
  
 ## Troubleshooting
  
 ### API not responding
 ```bash
 # Check if containers are running
 docker compose -p lms_local -f docker-compose.yml ps

 # Check logs
 docker compose -p lms_local -f docker-compose.yml logs backend

 # Restart
 docker compose -p lms_local -f docker-compose.yml restart
 ```

 ### Syslog not working
 ```bash
 # Check the dedicated ingest container (the API does not open a Syslog port)
 docker compose -p lms_local -f docker-compose.yml logs ingest

 # Verify port is listening (514 default, 5514 override)
 ss -tuln | grep -E ':(514|5514)\b'

 # Health: checks SELECT 1 on PostgreSQL and every enabled listener.
 # A socket alone is not considered healthy when the database is down.
 docker inspect --format '{{json .State.Health}}' lms_local-ingest-1 | python3 -m json.tool

 # Counters (received/accepted/invalid/denied/retried/dropped)
 docker compose -p lms_local -f docker-compose.yml exec -T ingest \
   python3 -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8090/healthz').read().decode())"

 # If SYSLOG_ENABLED=false, neither UDP nor TCP is expected to listen.
 docker compose -p lms_local -f docker-compose.yml exec -T ingest \
   python3 -c "import os; print('SYSLOG_ENABLED=' + os.environ.get('SYSLOG_ENABLED',''))"
 ```

 > The listener retries only transient database errors (bounded, exponential
 > backoff). Validation errors and messages from disallowed source CIDRs are
 > dropped and counted; they are never retried. See `ingest/README.md` for the
 > counter names and tenant limitation.

 ### Database connection issues
 ```bash
 # Check PostgreSQL
 docker compose -p lms_local -f docker-compose.yml logs db

 # Connect manually
 docker compose -p lms_local -f docker-compose.yml exec db psql -U logs -c "SELECT 1"
 ```

 ### Need to reseed
 ```bash
 docker compose -p lms_local -f docker-compose.yml exec -T backend python scripts/seed_demo_data.py
 ```