#!/usr/bin/env bash
# deploy.sh — Production deployment to a single VM via docker compose.
#
# Modes:
#   forward   : origin/main is ancestor of SHA. Full flow, fast-forward main.
#   redeploy  : SHA == main. Re-run deploy without fast-forward.
#   rollback  : SHA is ancestor of origin/main. Skip migrations, never touch main.
#   diverged  : Abort (handled in deploy.yml plan job).
#
# Env files on the VM ($VM_COMPOSE_DIR/.deploy/):
#   current.env  — image refs currently running (used by compose)
#   previous.env — image refs before current deploy (rollback target)
#   next.env     — image refs being deployed (written before switch)
#
# Env (all required unless noted):
#   MODE                  forward | redeploy | rollback
#   SHA                   full git SHA of the deployment
#   BACKEND_DIGEST        sha256 digest of backend image
#   INGEST_DIGEST         sha256 digest of ingest image
#   FRONTEND_DIGEST       sha256 digest of frontend image
#   VM_HOST, VM_USER, VM_COMPOSE_DIR
#   SSH_PRIVATE_KEY, VM_SSH_HOST_KEY
#   GITHUB_TOKEN          packages: read, passed to VM over stdin for docker login
#   RUN_MIGRATIONS        "true" only after alembic stamp head has been run on prod

set -euo pipefail

MODE="${MODE:?MODE must be set}"
SHA="${SHA:?SHA must be set}"
BACKEND_DIGEST="${BACKEND_DIGEST:?BACKEND_DIGEST must be set}"
INGEST_DIGEST="${INGEST_DIGEST:?INGEST_DIGEST must be set}"
FRONTEND_DIGEST="${FRONTEND_DIGEST:?FRONTEND_DIGEST must be set}"
VM_HOST="${VM_HOST:?VM_HOST must be set}"
VM_USER="${VM_USER:?VM_USER must be set}"
VM_COMPOSE_DIR="${VM_COMPOSE_DIR:?VM_COMPOSE_DIR must be set}"
SSH_PRIVATE_KEY="${SSH_PRIVATE_KEY:?SSH_PRIVATE_KEY must be set}"
VM_SSH_HOST_KEY="${VM_SSH_HOST_KEY:?VM_SSH_HOST_KEY must be set}"
GITHUB_TOKEN="${GITHUB_TOKEN:?GITHUB_TOKEN must be set}"
RUN_MIGRATIONS="${RUN_MIGRATIONS:-false}"

IMAGE_REGISTRY="ghcr.io"
IMAGE_OWNER="${GITHUB_REPOSITORY_OWNER:-$(echo "${GITHUB_REPOSITORY}" | cut -d/ -f1)}"
IMAGE_OWNER="${IMAGE_OWNER,,}"
PKG_BACKEND="logs-manager-backend"
PKG_INGEST="logs-manager-ingest"
PKG_FRONTEND="logs-manager-frontend"

BACKEND_REF="${IMAGE_REGISTRY}/${IMAGE_OWNER}/${PKG_BACKEND}@${BACKEND_DIGEST}"
INGEST_REF="${IMAGE_REGISTRY}/${IMAGE_OWNER}/${PKG_INGEST}@${INGEST_DIGEST}"
FRONTEND_REF="${IMAGE_REGISTRY}/${IMAGE_OWNER}/${PKG_FRONTEND}@${FRONTEND_DIGEST}"

# SSH setup with pinned host key
SSH_KEY=$(mktemp)
printf '%s\n' "${SSH_PRIVATE_KEY}" > "${SSH_KEY}"
chmod 600 "${SSH_KEY}"

HOST_KEY_FILE=$(mktemp)
printf '%s\n' "${VM_SSH_HOST_KEY}" > "${HOST_KEY_FILE}"
chmod 600 "${HOST_KEY_FILE}"

trap 'rm -f "${SSH_KEY}" "${HOST_KEY_FILE}"' EXIT

SSH_OPTS=(-i "${SSH_KEY}" \
  -o UserKnownHostsFile="${HOST_KEY_FILE}" \
  -o StrictHostKeyChecking=yes \
  -o ConnectTimeout=15 \
  -o BatchMode=yes \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=10)

# Build the remote deploy script (no secrets embedded — token comes via stdin later)
REMOTE_SCRIPT=$(cat <<'REMOTE_EOF'
set -euo pipefail

cd '__VM_COMPOSE_DIR__'

DEPLOY_DIR='.deploy'
BACKUP_DIR="${DEPLOY_DIR}/backups"
CURRENT_ENV="${DEPLOY_DIR}/current.env"
PREVIOUS_ENV="${DEPLOY_DIR}/previous.env"
NEXT_ENV="${DEPLOY_DIR}/next.env"
FLAGS_ENV="${DEPLOY_DIR}/flags.env"

MODE='__MODE__'
SHA='__SHA__'
BACKEND_REF='__BACKEND_REF__'
INGEST_REF='__INGEST_REF__'
FRONTEND_REF='__FRONTEND_REF__'
RUN_MIGRATIONS='__RUN_MIGRATIONS__'

mkdir -p "${DEPLOY_DIR}" "${BACKUP_DIR}"

echo "=== Deploy mode: ${MODE} ==="
echo "SHA: ${SHA}"
echo "Backend: ${BACKEND_REF}"
echo "Ingest:  ${INGEST_REF}"
echo "Frontend: ${FRONTEND_REF}"

# ------------------------------------------------------------
# 1. Login to GHCR via stdin (token never in command args)
# ------------------------------------------------------------
echo '${GITHUB_TOKEN}' | docker login ghcr.io -u '${GITHUB_ACTOR}' --password-stdin

# ------------------------------------------------------------
# 2. Record current running image refs (if any)
# ------------------------------------------------------------
if [ -f "${CURRENT_ENV}" ]; then
  cp "${CURRENT_ENV}" "${PREVIOUS_ENV}"
  echo "Recorded previous.env from current.env."
else
  echo "No current.env found — first deploy. No rollback target yet."
fi

# ------------------------------------------------------------
# 3. Write next.env with new image refs
# ------------------------------------------------------------
cat > "${NEXT_ENV}" <<NEXT_ENV_EOF
BACKEND_IMAGE=${BACKEND_REF}
INGEST_IMAGE=${INGEST_REF}
FRONTEND_IMAGE=${FRONTEND_REF}
NEXT_ENV_EOF

echo "Wrote ${NEXT_ENV}."

# ------------------------------------------------------------
# 4. pg_dump backup (abort on failure, check free disk, keep last N)
# ------------------------------------------------------------
AVAILABLE_KB=$(df --output=avail / | tail -1)
REQUIRED_KB=1048576  # 1 GB minimum free
if [ "${AVAILABLE_KB}" -lt "${REQUIRED_KB}" ]; then
  echo "Insufficient disk space: ${AVAILABLE_KB} KB available, ${REQUIRED_KB} KB required." >&2
  exit 1
fi

BACKUP_FILE="${BACKUP_DIR}/pre_deploy_$(date -u +%Y%m%d-%H%M%S).sql"
docker compose -f docker-compose.vm.yml --env-file "${CURRENT_ENV}" \
  exec -T db pg_dump -U "${POSTGRES_USER:-logs}" -d "${POSTGRES_DB:-logs_manager}" > "${BACKUP_FILE}" 2>/dev/null || {
  echo "pg_dump failed. Aborting deploy." >&2
  exit 1
}
echo "Database backup written to ${BACKUP_FILE}."

# Keep last N backups
BACKUP_COUNT=$(ls -1 "${BACKUP_DIR}"/*.sql 2>/dev/null | wc -l)
KEEP_N=10
if [ "${BACKUP_COUNT}" -gt "${KEEP_N}" ]; then
  ls -1t "${BACKUP_DIR}"/*.sql | tail -n +$((KEEP_N + 1)) | xargs rm -f
  echo "Retained last ${KEEP_N} backups."
fi

# ------------------------------------------------------------
# 5. Run migrations with NEW backend image BEFORE switching
#    (forward/redeploy mode only, gated by RUN_MIGRATIONS=true)
# ------------------------------------------------------------
if [ "${MODE}" = "forward" ] || [ "${MODE}" = "redeploy" ]; then
  if [ "${RUN_MIGRATIONS}" = "true" ]; then
    echo "Running migrations with new backend image..."
    docker compose -f docker-compose.vm.yml --env-file "${NEXT_ENV}" run --rm --no-deps backend \
      alembic upgrade head
    echo "Migrations completed."
  else
    echo "RUN_MIGRATIONS is not 'true'. Skipping migrations."
  fi
elif [ "${MODE}" = "rollback" ]; then
  echo "Rollback mode: skipping migrations."
fi

# ------------------------------------------------------------
# 6. Switch containers with new image refs
# ------------------------------------------------------------
echo "Switching containers to new images..."
docker compose -f docker-compose.vm.yml --env-file "${NEXT_ENV}" up -d --wait

# ------------------------------------------------------------
# 7. Health check /ready
# ------------------------------------------------------------
echo "Waiting for /ready health check..."
ATTEMPTS=0
until docker compose -f docker-compose.vm.yml --env-file "${NEXT_ENV}" exec -T backend \
      curl -sf http://localhost:4500/ready >/dev/null 2>&1; do
  ATTEMPTS=$((ATTEMPTS + 1))
  if [ "${ATTEMPTS}" -ge 30 ]; then
    echo "Health check failed after ~150s." >&2
    docker compose -f docker-compose.vm.yml --env-file "${NEXT_ENV}" ps >&2
    echo "=== Rolling back to current.env ==="
    if [ -f "${CURRENT_ENV}" ]; then
      docker compose -f docker-compose.vm.yml --env-file "${CURRENT_ENV}" up -d --force-recreate
      echo "Rollback complete."
    else
      echo "No current.env — cannot roll back." >&2
    fi
    exit 1
  fi
  sleep 5
done
echo "All services healthy."

# ------------------------------------------------------------
# 8. Promote env files on success
# ------------------------------------------------------------
mv "${CURRENT_ENV}" "${PREVIOUS_ENV}" 2>/dev/null || true
mv "${NEXT_ENV}" "${CURRENT_ENV}"
echo "Promoted next.env -> current.env."
echo "Deploy succeeded for SHA ${SHA}."

# ------------------------------------------------------------
# 9. Logout from GHCR
# ------------------------------------------------------------
docker logout ghcr.io
REMOTE_EOF
)

# Substitute placeholders
REMOTE_SCRIPT=$(printf '%s' "${REMOTE_SCRIPT}" \
  | sed -e "s|__VM_COMPOSE_DIR__|${VM_COMPOSE_DIR}|g" \
        -e "s|__MODE__|${MODE}|g" \
        -e "s|__SHA__|${SHA}|g" \
        -e "s|__BACKEND_REF__|${BACKEND_REF}|g" \
        -e "s|__INGEST_REF__|${INGEST_REF}|g" \
        -e "s|__FRONTEND_REF__|${FRONTEND_REF}|g" \
        -e "s|__RUN_MIGRATIONS__|${RUN_MIGRATIONS}|g")

# Write the script to the VM
SCRIPT_PATH="/tmp/deploy_lms_${SHA}.sh"
printf '%s\n' "${REMOTE_SCRIPT}" | ssh "${SSH_OPTS[@]}" "${VM_USER}@${VM_HOST}" "cat > '${SCRIPT_PATH}' && chmod +x '${SCRIPT_PATH}'"

echo "Deploy script written to VM."

# Step 2: Login to GHCR via stdin, then run the deploy script
echo "${GITHUB_TOKEN}" | ssh "${SSH_OPTS[@]}" "${VM_USER}@${VM_HOST}" \
  "docker login ghcr.io -u '${GITHUB_ACTOR}' --password-stdin && bash '${SCRIPT_PATH}'"

echo "Deploy script completed."
