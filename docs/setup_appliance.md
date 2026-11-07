# Appliance Setup Guide
 
 This guide covers deploying Log Manager as an appliance on a single machine or VM.
 
 ## System Requirements
 
 | Component | Minimum | Recommended |
 |-----------|---------|-------------|
 | CPU | 2 vCPU | 4 vCPU |
 | Memory | 4 GB | 8 GB |
 | Disk | 20 GB | 40 GB |
 | OS | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |
 | Ports | 80, 443, 514, 4500 | 80, 443, 514, 4500 |
 
 ## Prerequisites
 
 - Docker Engine 24.x or later
 - Docker Compose plugin
 - 2-4 GB disk space for images
 
## Quick Start

```bash
# Clone the repository
git clone https://github.com/your-org/logs-manager.git
cd logs-manager

# Copy environment template
cp .env.example .env
# Edit .env with your settings (passwords, secrets, DOMAIN)

# Start the stack (standalone local Compose file)
make up

# Wait ~30s for services to become healthy
make seed

# Access the system
#   UI:        https://localhost:443/  (Caddy, self-signed cert locally)
#   API:       http://localhost:4500
#   Syslog:    UDP/TCP 127.0.0.1:514
#   API docs:  http://localhost:4500/docs
```
 
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
curl -sk https://localhost:443/healthz

# Or HTTP redirect to check Caddy
curl -sI http://localhost:8088/
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
| UI Dashboard | https://localhost:443/ |
| API | http://localhost:4500 |
| Swagger Docs | http://localhost:4500/docs |
| Syslog UDP | 127.0.0.1:514 |
| Syslog TCP | 127.0.0.1:514 |
 
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
 INGEST_API_TENANT=demoA
 
 # Syslog (optional, for receiving logs)
 SYSLOG_ENABLED=true
 SYSLOG_UDP_PORT=5514
 SYSLOG_TCP_PORT=5514
 
 # Retention
 RETENTION_DAYS=7
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
 
 # Or use logger
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
 # Check syslog listener
 docker compose -p lms_local -f docker-compose.yml logs backend | grep syslog

 # Verify port is listening
 ss -tuln | grep 514
 ```

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