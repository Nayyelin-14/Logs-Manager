#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

COMPOSE_FILE="backend-fastapi/docker-compose.yml"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required. Install Docker Engine and the Compose plugin first." >&2
  exit 1
fi

# Local-development env for backend-fastapi: created ONLY when missing.
# An existing backend-fastapi/.env is never touched or overwritten.
if [ ! -f backend-fastapi/.env ]; then
  cp backend-fastapi/.env.example backend-fastapi/.env
  echo "Created backend-fastapi/.env from backend-fastapi/.env.example"
  echo "Review it before running the backend outside Docker."
fi

echo "Starting Logs Manager (FastAPI)..."
docker compose -f "$COMPOSE_FILE" up -d --build

echo "Waiting for the API to become healthy..."
for _ in $(seq 1 60); do
  if curl -fsS "http://localhost:4500/healthz" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

if ! curl -fsS "http://localhost:4500/healthz" >/dev/null 2>&1; then
  echo "API did not become healthy. Check logs with: docker compose -f $COMPOSE_FILE logs backend" >&2
  exit 1
fi

echo
echo "Logs Manager is running:"
echo "  UI:      http://localhost:8081"
echo "  API:     http://localhost:4500"
echo "  Syslog:  udp/5514 and tcp/5514"
echo
echo "Seed demo data with: make seed"
echo "Demo logins after seeding:"
echo "  admin@demo.local / Admin123!   (ADMIN, tenant demoA)"
echo "  viewerA@demo.local / ViewerA123!   (VIEWER, tenant demoA)"
echo "  viewerB@demo.local / ViewerB123!   (VIEWER, tenant demoB)"
