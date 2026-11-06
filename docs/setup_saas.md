# SaaS/Cloud Deployment Guide

This guide covers deploying Log Manager to a cloud VM with HTTPS/TLS.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Internet (HTTPS)                         │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│              Caddy Reverse Proxy (port 443/80)            │
│  - Automatic Let's Encrypt certificates                   │
│  - HTTP→HTTPS redirect                                     │
│  - /api/* → backend:4500                                   │
│  - /static/* → frontend (nginx)                            │
└──────────────────────┬──────────────────────────────────────┘
                       │
    ┌──────────────────┴──────────────────┐
    │                                     │
    ▼                                     ▼
┌──────────────┐                  ┌─────────────┐
│  Backend     │                  │  Frontend   │
│  FastAPI     │                  │  (nginx)    │
│  port 4500   │                  │  port 80    │
└──────────────┘                  └─────────────┘
       │                                 │
       │                                 ▼
       │                         ┌─────────────┐
       │                         │   Assets    │
       │                         │  (built-in) │
       │                         └─────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│  PostgreSQL (port 5432)             │
│  - Persistent volume                │
│  - Daily backups recommended      │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│  Redis (port 6379)                  │
│  - Cache + email queue              │
└─────────────────────────────────────┘
```

## Prerequisites

### Cloud VM Requirements

| Requirement | Details |
|-------------|---------|
| OS | Ubuntu 22.04 LTS (recommended) |
| CPU | 2 vCPU minimum |
| Memory | 4 GB minimum (8 GB recommended) |
| Disk | 30 GB (50 GB recommended with backups) |
| Network | Public IP, ports 80/443 open |

### DNS Configuration

Point your domain (e.g., `logs.example.com`) to your VM's public IP:

```
A record: logs.example.com → <VM_PUBLIC_IP>
```

## Deployment Steps

### 1. Provision VM

```bash
# Ubuntu 22.04
# SSH into your VM
ssh ubuntu@<VM_PUBLIC_IP>
```

### 2. Install Docker

```bash
# Install Docker and Compose
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Compose plugin
sudo apt-get update
sudo apt-get install -y docker-compose-plugin

# Logout and login again to apply group change
```

### 3. Clone Repository

```bash
git clone https://github.com/your-org/logs-manager.git
cd logs-manager
```

### 4. Configure Environment

```bash
# Copy example
cp backend-fastapi/.env.example backend-fastapi/.env

# Edit critical values
nano backend-fastapi/.env
```

**Key settings for SaaS:**

```dotenv
# Production environment
APP_ENV=production
COOKIE_SECURE=true
COOKIE_SAME_SITE=none

# External URL (for redirect after login)
CORS_ORIGINS=["https://logs.example.com"]
ALLOWED_HOSTS=["logs.example.com", "*.example.com"]

# Strong secrets
ACCESS_TOKEN_SECRET=<generate with: openssl rand -hex 32>
REFRESH_TOKEN_SECRET=<generate with: openssl rand -hex 32>

# Database
DATABASE_URL=postgresql+asyncpg://logs:your_password@db:5432/logs_manager

# Redis (internal Docker network)
REDIS_URL=redis://redis:6379

# Email (optional, for alerts/2FA)
SMTP_ENABLED=true
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=alert@example.com
SMTP_PASSWORD=<smtp_password>
ALERT_EMAIL_RECIPIENTS=security@example.com
```

### 5. HTTPS via Caddy (Recommended)

Create a Caddy configuration:

```bash
cat > Caddyfile << 'EOF'
logs.example.com {
    reverse_proxy /api/* backend:4500
    reverse_proxy /* frontend:80
    encode gzip
    
    # Security headers
    header {
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        X-XSS-Protection "1; mode=block"
        Referrer-Policy "strict-origin-when-cross-origin"
    }
}
EOF
```

Deploy with Caddy:

```bash
# Create caddy-docker-network
docker network create caddy

# Run Caddy with automatic HTTPS
docker run -d \
  --name caddy \
  --restart unless-stopped \
  --network caddy \
  --volume $PWD/Caddyfile:/etc/caddy/Caddyfile \
  --volume caddy_data:/data \
  --volume caddy_config:/config \
  caddy:2-alpine
```

### 6. Deploy Application Stack

```bash
# Set environment
export INGEST_API_KEY=$(openssl rand -hex 16)

# Deploy with docker compose using saas override file
docker compose -f docker-compose.yml -f docker-compose.saas.yml up -d --build
```

Alternatively, use the provided docker-compose.yml with modifications:

```yaml
# Add to docker-compose.yml under services:
  caddy:
    image: caddy:2-alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy_data:/data
      - caddy_config:/config
    depends_on:
      - backend
      - frontend

volumes:
  caddy_data:
  caddy_config:
```

### 7. Wait for Certificates

```bash
# Wait 1-2 minutes for Let's Encrypt verification
# Caddy logs will show certificate status

docker logs caddy | grep -i certificate
```

### 8. Seed Initial Data

```bash
# Create admin account and sample events
cd /path/to/logs-manager
docker compose -f docker-compose.yml -f docker-compose.saas.yml exec -T backend python scripts/seed_demo_data.py

# Save the API keys displayed
# They are required for ingestion
```

## Production Hardening

### 1. Firewall Rules

```bash
# Allow only necessary ports
sudo ufw enable
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP (for ACME challenge)
sudo ufw allow 443/tcp   # HTTPS
# IMPORTANT: Port 514 (syslog) must be restricted by IP in the cloud firewall
#   - Only allow trusted syslog sources to send to this port
#   - Example AWS Security Group rule: source = syslog server IPs only
# Block internal ports (5432, 6379, 4500, 8081 should NOT be exposed)
```

### 2. Database Backups

```bash
# Create backup script
cat > backup.sh << 'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/opt/backups"
mkdir -p $BACKUP_DIR

docker compose -f docker-compose.yml -f docker-compose.saas.yml exec -T db pg_dump -U logs logs_manager > $BACKUP_DIR/logs_$DATE.sql
gzip $BACKUP_DIR/logs_$DATE.sql

# Keep last 7 days
find $BACKUP_DIR -name "logs_*.sql.gz" -mtime +7 -delete
EOF

chmod +x backup.sh

# Add to crontab (daily at 2 AM)
echo "0 2 * * * /opt/logs-manager/backup.sh" | crontab -
```

### 3. Monitoring

```bash
# Enable monitoring label for Prometheus/Grafana
# Or use simple health check:
curl -sf http://localhost:4500/healthz || echo "ALERT: API down"
```

### 4. Log Rotation

```bash
# Docker logs are retained by Docker
# For application logs, configure:
sudo journalctl --vacuum-time=7d

# Or bind mount logs to host:
# In docker-compose.yml:
# volumes:
#   - /var/log/logs-manager:/app/logs
```

### 5. TLS Certificate Renewal

Caddy handles automatic renewal. Verify:

```bash
# Check certificate expiration
docker exec caddy caddy cert-info --domains logs.example.com

# Force renewal (if needed)
docker exec caddy caddy reload
```

## API Access

### Base URL
```
https://logs.example.com/api/
```

### Ingestion Endpoint
```bash
POST https://logs.example.com/api/ingest

Headers:
  Content-Type: application/json
  X-API-Key: <your-tenant-api-key>
```

### Example Request

```bash
curl -X POST https://logs.example.com/api/ingest \
  -H "Content-Type: application/json" \
  -H "X-API-Key: demoa-key-here" \
  -d '{
    "tenant": "demoa",
    "source": "api",
    "event_type": "user_login",
    "user": "admin",
    "src_ip": "203.0.113.42",
    "severity": 3
  }'
```

## Security Considerations

### 1. Admin Access
- Admin users have `tenant: NULL` for cross-tenant access
- CHANGE_default passwords immediately after seeding
- Use strong, unique passwords (min 12 chars, mixed case, numbers, symbols)

### 2. API Keys
- Generated during seeding
- Each tenant gets unique key
- Store securely - displayed only once
- Rotate periodically using `/api/tenants/{name}/rotate-key`

### 3. JWT Security
- Access tokens: 15 minute expiry
- Refresh tokens: 30 day expiry
- Cookies have HttpOnly and Secure flags

### 4. Network Security
- Internal services (PostgreSQL, Redis) not exposed
- All external access via Caddy reverse proxy
- Rate limiting enabled

### 5. Data Encryption
- TLS 1.3 for all external traffic
- PostgreSQL data at rest (configure PG settings)
- Consider encrypting backups

## Troubleshooting SaaS Deployment

### Certificate Issues
```bash
# Check Caddy logs
docker logs caddy

# Test HTTP challenge manually
curl -I http://logs.example.com/.well-known/acme-challenge/

# Force certificate renewal
docker restart caddy
```

### CORS Errors
```bash
# Check browser console for CORS errors
# Verify CORS_ORIGINS includes your domain exactly
# Ensure you restarted containers after changes
```

### Database Connection
 ```bash
 # Test connection
 docker compose -f docker-compose.yml -f docker-compose.saas.yml exec -T backend python -c "from app.core.database import engine; print(engine.url)"
 ```

### Email Not Working
```bash
# Check if SMTP credentials are correct
# Verify ALERT_EMAIL_RECIPIENTS is set
# Check spam folder
```

## Scaling Considerations

For higher load:
- Use external PostgreSQL (RDS, Cloud SQL)
- Use managed Redis (ElastiCache, MemoryDB)
- Run backend with multiple replicas behind load balancer
- Consider ClickHouse for higher volume logs

## Maintenance Tasks

 ```bash
 # Restart services
 docker compose -f docker-compose.yml -f docker-compose.saas.yml restart
 
 # Pull latest images
 docker compose -f docker-compose.yml -f docker-compose.saas.yml pull
 docker compose -f docker-compose.yml -f docker-compose.saas.yml down
 docker compose -f docker-compose.yml -f docker-compose.saas.yml up -d
 
 # Check resource usage
 docker stats
 
 # Database maintenance (backup first)
 docker compose -f docker-compose.yml -f docker-compose.saas.yml exec -T db pg_dump -U logs logs_manager > backup.sql
 ```