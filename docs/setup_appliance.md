# Log Manager - Appliance Deployment

## Prerequisites

- Ubuntu 22.04+ or any Linux/macOS with Docker and Docker Compose installed
- 4 vCPU, 8 GB RAM, 40 GB disk minimum
- Open ports: 80/443 (HTTP/HTTPS), 514 (Syslog UDP+TCP)

## Quick Start

```bash
# 1. Clone the repository
git clone <repository-url>
cd logs-manager

# 2. Copy environment file
cp .env.example .env
# Edit .env with your settings (or use defaults)

# 3. Start the stack
make up

# 4. Wait for services to start (~30 seconds)
make ps

# 5. Seed the database with demo data
make seed
```

## What `make seed` does

Creates:
- **Tenants**: demoA, demoB (implicit via user assignments)
- **Users**:
  - `admin` (password: `Admin123!`, role: ADMIN, all tenants)
  - `viewerA` (password: `ViewerA123!`, role: VIEWER, tenant: demoA)
  - `viewerB` (password: `ViewerB123!`, role: VIEWER, tenant: demoB)
- **Alert rule**: "Brute force: repeated failed logins" (enabled, threshold=5, window=300s)
- **Sample events**: Sends sample logs through the ingestion pipeline

## Sending Test Syslog Messages

### UDP
```bash
echo '<134>Oct 20 12:44:56 fw01 vendor=demo product=ngfw action=deny src=10.0.1.10 dst=8.8.8.8 spt=5353 dpt=53 proto=udp msg=DNS blocked policy=Block-DNS' | nc -u -w1 localhost 514
```

### TCP
```bash
echo '<134>Oct 20 12:44:56 fw01 vendor=demo product=ngfw action=deny src=10.0.1.10 dst=8.8.8.8 spt=5353 dpt=53 proto=udp msg=DNS blocked policy=Block-DNS' | nc localhost 514
```

### Using logger command
```bash
logger -n localhost -P 514 -d "134>Aug 20 12:44:56 fw01 vendor=demo product=ngfw action=deny src=10.0.1.10 dst=8.8.8.8 spt=5353 dpt=53 proto=udp msg=DNS blocked policy=Block-DNS"
```

## Verification

- **Check events in UI**: Visit `http://localhost:4500/search` and search for `source:firewall`
- **Check alerts**: Visit `http://localhost:4500/alerts` - should show any triggered alerts
- **Test RBAC**: Login as `viewerA` (`demoA-key` API key) and verify only demoA events are visible
- **Test ingestion**: `curl -X POST http://localhost:4500/ingest -H "X-API-Key: demoA-key" -H "Content-Type: application/json" -d @samples/api_login_failed.json`

## Service Ports

| Service | Host Port | Container Port |
|---------|-----------|----------------|
| Backend API | 4500 | 4500 |
| Syslog UDP | 514 | 514 |
| Syslog TCP | 514 | 514/TCP |
| Frontend | 8080 | 80 |
| PostgreSQL | (internal) | 5432 |
| Redis | (internal) | 6379 |
| Caddy HTTPS | (self-signed) | 443 |

## TLS (Self-Signed for Appliance)

The appliance runs HTTP only by default. To enable HTTPS:

1. Generate a self-signed certificate:
```bash
openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/CN=localhost"
```

2. Place cert.pem and key.pem in the appropriate directory (refer to Caddyfile or Nginx config)

3. Update the frontend VITE_API_URL to use `https://localhost:4500/api`

Note: Modern browsers will show a "Your connection is not private" warning for self-signed certs. Accept the risk to proceed.

## Default Logins

| Username | Password | Role | Tenant |
|----------|----------|------|--------|
| admin | Admin123! | ADMIN | All |
| viewerA | ViewerA123! | VIEWER | demoA |
| viewerB | ViewerB123! | VIEWER | demoB |

## Making and Sending Sample Logs

### Syslog messages (from samples/)
```bash
# Firewall syslog
bash samples/send_syslog.sh udp samples/syslog_firewall.log

# Router syslog  
bash samples/send_syslog.sh network samples/syslog_network.log

# Or use logger command
bash samples/send_syslog.sh logger samples/syslog_firewall.log
```

### HTTP API (from samples/)
```bash
curl -X POST http://localhost:4500/ingest -H "X-API-Key: demoA-key" \
  -H "Content-Type: application/json" \
  -d @samples/api_login_failed.json
```

### File upload (from samples/)
```bash
curl -F "file=@samples/aws_cloudtrail.json" -F "source=aws" http://localhost:4500/ingest/file
```

### Trigger alert (6 failed logins from same IP)
```bash
bash samples/trigger_alert.sh
```

## Cleanup

```bash
make down   # Stop containers (keeps data volumes)
make clean  # Stop containers AND delete data volumes
```
