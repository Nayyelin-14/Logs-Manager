# Log Manager - SaaS/Cloud Deployment

## Prerequisites

- Cloud VM (AWS EC2, Oracle Free Tier, DigitalOcean, etc.)
- Domain name (recommended for Let's Encrypt) or use IP address
- Open ports: 22 (SSH), 80 (HTTP), 443 (HTTPS), 514 (Syslog UDP+TCP if needed)
- 4 GB RAM minimum, 2 vCPU minimum, 40 GB disk

## Deployment Steps

### 1. Provision the VM

```bash
# Example: AWS EC2
# - Select Ubuntu 22.04 AMI
# - t2.micro or larger (free tier eligible)
# - Open ports: 22, 80, 443 (and 514 for syslog)
# - Create a new volume (minimum 40 GB)
```

### 2. Install Docker and Docker Compose

```bash
# On Ubuntu
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin
sudo usermod -aG docker $USER
newgrp docker

# Verify
docker version
docker compose version
```

### 3. Clone and Configure

```bash
git clone <repository-url>
cd logs-manager
cp .env.example .env
```

Edit `.env` for SaaS production settings:

```
# Database
POSTGRES_USER=logs
POSTGRES_PASSWORD=change_this_strong_password
POSTGRES_DB=logs_manager

# Redis
REDIS_URL=redis://:change_this_strong_password@localhost:6379

# Auth secrets (generate strong secrets!)
ACCESS_TOKEN_SECRET=change_this_very_long_random_string
REFRESH_TOKEN_SECRET=change_this_very_long_random_string

# Cookie behavior for HTTPS SaaS
COOKIE_SECURE=true
COOKIE_SAME_SITE=none

# Ingestion (per-tenant API keys managed via /api/tenants)
INGEST_API_USERNAME=log-forwarder

# Syslog (optional)
SYSLOG_ENABLED=false  # Set to true if accepting external syslog
SYSLOG_TENANT=demoA
SYSLOG_SOURCE=firewall
SYSLOG_UDP_PORT=514
SYSLOG_TCP_PORT=514

# CORS for production domain
CORS_ORIGINS=https://your-domain.com

# SMTP for email notifications (optional)
SMTP_ENABLED=false  # Or true + configure SMTP_HOST, SMTP_PORT, etc.
GMAIL_USER=your@gmail.com
GMAIL_PASS=your_app_password

# Domain and HTTPS
DOMAIN=your-domain.com  # For Let's Encrypt
EMAIL_HOST=smtp.gmail.com
SMTP_PORT=587
```

### 3. Start the Stack

```bash
make up
```

Wait ~30-60 seconds for services to initialize.

### 4. Configure DNS and HTTPS

If you have a domain name:

```bash
# Ensure your domain's DNS A record points to the VM's IP address
# Then Caddy will automatically get Let's Encrypt certificates

# Or manually run:
docker exec -it caddy caddy adapt --config /etc/caddy/Caddyfile
```

If no domain name (IP only):

1. Caddy will start with a self-signed certificate
2. The frontend will show a "Your connection is not private" warning
3. Users must accept the risk to proceed
4. For production use, a real domain name is strongly recommended

### 5. Seed the Database

```bash
make seed
```

### 6. Access the System

- **Frontend**: `https://your-domain.com` (or `https://localhost` if using IP+self-signed)
- **Backend API**: `https://your-domain.com/api/` or `https://localhost:4500/`
- **API Docs**: `https://your-domain.com/docs`

## Sending Test Syslog Messages (SaaS)

### UDP
```bash
echo '<134>Oct 20 12:44:56 fw01 vendor=demo product=ngfw action=deny src=10.0.1.10 dst=8.8.8.8 spt=5353 dpt=53 proto=udp msg=DNS blocked policy=Block-DNS' | nc -u -w1 YOUR_VM_IP 514
```

### HTTP API
```bash
curl -X POST https://your-domain.com/ingest -H "X-API-Key: demoA-key" \
  -H "Content-Type: application/json" \
  -d @samples/api_login_failed.json
```

### File Upload
```bash
curl -F "file=@samples/aws_cloudtrail.json" -F "source=aws" https://your-domain.com/ingest/file
```

## SaaS vs Appliance Differences

| Feature | Appliance (Docker Compose) | SaaS (Cloud VM) |
|---------|---------------------------|-----------------|
| TLS | Self-signed cert (accept risk) | Let's Encrypt (via Caddy + domain) |
| CORS | `http://localhost:5173, http://localhost:8080` | `https://your-domain.com` |
| SMTP | Disabled (Mailpit for testing) | Configure via .env (SMTP_HOST, SMTP_PORT, etc.) |
| Syslog port | 514 (host mapped to 5514) | 514 (if firewall rules allow) |
| Domain | Not required | Recommended for Let's Encrypt |
| Data persistence | Host `pgdata` and `redisdata` volumes | Host volumes + backup strategy |
| Support | User-managed | User-managed + possible support options |

## Troubleshooting

### Common Issues

1. **Caddy can't get Let's Encrypt**
   - Ensure domain A record points to VM IP
   - Ensure ports 80/443 are open in firewall
   - Try using a self-signed cert instead

2. **Syslog not receiving messages**
   - Verify VM firewall allows UDP/TCP 514
   - Check `SYSLOG_ENABLED` is `true` in .env
   - Check container logs: `make logs`

3. **Authentication fails**
   - Verify `.env` secrets match between backend and frontend
   - Ensure API key is configured via `/api/tenants` and used in `X-API-Key` header
   - Check JWT token expiration

4. **No events appearing**
   - Check `make seed` ran successfully
   - Verify syslog messages are reaching the container
   - Search in UI: `source:firewall` or `tenant:demoA`

5. **Rate limiting blocks ingestion**
   - The rate limiter is currently a pass-through in development
   - For production, configure slowapi rate limits in `app/main.py`

## Making and Sending Sample Logs

Same commands as appliance mode, but replace `localhost:514` with your VM's IP address and `localhost:4500` with your domain or VM IP.

## Cleanup

```bash
make down   # Stop containers (keeps data volumes)
# Or manually:
docker compose down -v
```
