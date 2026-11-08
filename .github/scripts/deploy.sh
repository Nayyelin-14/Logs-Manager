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
GITHUB_ACTOR="${GITHUB_ACTOR:?GITHUB_ACTOR must be set}"
RUN_MIGRATIONS="${RUN_MIGRATIONS:-false}"

case "${MODE}" in forward|redeploy|rollback) ;; *) echo "Bad MODE: ${MODE}" >&2; exit 1 ;; esac
[[ "${SHA}" =~ ^[0-9a-f]{40}$ ]] || { echo "SHA must be a 40-char hex commit" >&2; exit 1; }
for D in "${BACKEND_DIGEST}" "${INGEST_DIGEST}" "${FRONTEND_DIGEST}"; do
  [[ "${D}" =~ ^sha256:[0-9a-f]{64}$ ]] || { echo "Bad digest: ${D}" >&2; exit 1; }
done
[ "${RUN_MIGRATIONS}" = "true" ] || RUN_MIGRATIONS="false"

OWNER="${GITHUB_REPOSITORY_OWNER:-${GITHUB_REPOSITORY%%/*}}"
OWNER="${OWNER,,}"
BACKEND_REF="ghcr.io/${OWNER}/logs-manager-backend@${BACKEND_DIGEST}"
INGEST_REF="ghcr.io/${OWNER}/logs-manager-ingest@${INGEST_DIGEST}"
FRONTEND_REF="ghcr.io/${OWNER}/logs-manager-frontend@${FRONTEND_DIGEST}"

SSH_KEY=$(mktemp)
HOST_KEY_FILE=$(mktemp)
trap 'rm -f "${SSH_KEY}" "${HOST_KEY_FILE}"' EXIT
printf '%s\n' "${SSH_PRIVATE_KEY}" > "${SSH_KEY}"
printf '%s\n' "${VM_SSH_HOST_KEY}" > "${HOST_KEY_FILE}"
chmod 600 "${SSH_KEY}" "${HOST_KEY_FILE}"

SSH_OPTS=(-i "${SSH_KEY}"
  -o UserKnownHostsFile="${HOST_KEY_FILE}"
  -o StrictHostKeyChecking=yes
  -o ConnectTimeout=15
  -o BatchMode=yes
  -o ServerAliveInterval=30
  -o ServerAliveCountMax=10)

REMOTE_SCRIPT=$(cat <<'REMOTE_EOF'
set -euo pipefail
COMPOSE_DIR="$1"; MODE="$2"; SHA="$3"
BACKEND_REF="$4"; INGEST_REF="$5"; FRONTEND_REF="$6"; RUN_MIGRATIONS="$7"

cd "${COMPOSE_DIR}"
trap 'docker logout ghcr.io >/dev/null 2>&1 || true; rm -f "$0"' EXIT

DEPLOY_DIR=.deploy
BACKUP_DIR="${DEPLOY_DIR}/backups"
CURRENT_ENV="${DEPLOY_DIR}/current.env"
PREVIOUS_ENV="${DEPLOY_DIR}/previous.env"
NEXT_ENV="${DEPLOY_DIR}/next.env"
mkdir -p "${DEPLOY_DIR}" "${BACKUP_DIR}"

compose() {
  local envf="$1"; shift
  local args=()
  if [ -f .env ]; then args+=(--env-file .env); fi
  args+=(--env-file "${envf}")
  docker compose -f docker-compose.vm.yml "${args[@]}" "$@"
}

MIGRATED=false
BACKUP_FILE=""

rollback() {
  echo "=== Rolling back to ${CURRENT_ENV} ===" >&2
  if [ ! -f "${CURRENT_ENV}" ]; then
    echo "No current.env (first deploy): nothing to roll back to." >&2
    return 0
  fi
  if ! compose "${CURRENT_ENV}" up -d --force-recreate --wait; then
    echo "ROLLBACK ALSO FAILED. Manual intervention required." >&2
  fi
  if [ "${MIGRATED}" = "true" ]; then
    echo "WARNING: migrations were already applied; old images now run on the NEW schema." >&2
    echo "Pre-deploy backup: ${BACKUP_FILE}" >&2
  fi
}

echo "=== Deploy mode: ${MODE} | SHA: ${SHA} ==="
echo "Backend:  ${BACKEND_REF}"
echo "Ingest:   ${INGEST_REF}"
echo "Frontend: ${FRONTEND_REF}"

cat > "${NEXT_ENV}" <<NEXT_ENV_EOF
BACKEND_IMAGE=${BACKEND_REF}
INGEST_IMAGE=${INGEST_REF}
FRONTEND_IMAGE=${FRONTEND_REF}
NEXT_ENV_EOF

compose "${NEXT_ENV}" config -q

AVAILABLE_KB=$(df --output=avail "${BACKUP_DIR}" | tail -1 | tr -d ' ')
if [ "${AVAILABLE_KB}" -lt 1048576 ]; then
  echo "Insufficient disk space for backup: ${AVAILABLE_KB} KB free, 1048576 KB required." >&2
  exit 1
fi
if [ -f "${CURRENT_ENV}" ]; then
  BACKUP_FILE="${BACKUP_DIR}/pre_deploy_$(date -u +%Y%m%d-%H%M%S).sql"
  if ! compose "${CURRENT_ENV}" exec -T db sh -c 'pg_dump -U "${POSTGRES_USER:-logs}" -d "${POSTGRES_DB:-logs_manager}"' > "${BACKUP_FILE}.partial"; then
    rm -f "${BACKUP_FILE}.partial"
    echo "pg_dump failed. Aborting deploy." >&2
    exit 1
  fi
  mv "${BACKUP_FILE}.partial" "${BACKUP_FILE}"
  echo "Backup written to ${BACKUP_FILE}."
  ls -1t "${BACKUP_DIR}"/*.sql 2>/dev/null | tail -n +11 | xargs -r rm -f
else
  echo "No current.env: first deploy, skipping backup."
fi

if [ "${MODE}" != "rollback" ] && [ "${RUN_MIGRATIONS}" = "true" ]; then
  echo "Running migrations..."
  MIGRATED=true
  compose "${NEXT_ENV}" run --rm --no-deps backend alembic upgrade head
else
  echo "Skipping migrations (mode=${MODE}, RUN_MIGRATIONS=${RUN_MIGRATIONS})."
fi

echo "Switching containers..."
if ! compose "${NEXT_ENV}" up -d --wait; then
  compose "${NEXT_ENV}" ps >&2 || true
  rollback
  exit 1
fi

echo "Waiting for /ready..."
ATTEMPTS=0
until compose "${NEXT_ENV}" exec -T backend curl -sf http://localhost:4500/ready >/dev/null 2>&1; do
  ATTEMPTS=$((ATTEMPTS + 1))
  if [ "${ATTEMPTS}" -ge 30 ]; then
    echo "/ready failed after ~150s." >&2
    compose "${NEXT_ENV}" ps >&2 || true
    rollback
    exit 1
  fi
  sleep 5
done
echo "All services healthy."

if [ -f "${CURRENT_ENV}" ] && ! cmp -s "${CURRENT_ENV}" "${NEXT_ENV}"; then
  cp "${CURRENT_ENV}" "${PREVIOUS_ENV}"
fi
mv "${NEXT_ENV}" "${CURRENT_ENV}"
echo "Deploy succeeded for SHA ${SHA}."
REMOTE_EOF
)

REMOTE_PATH="/tmp/deploy_lms_${SHA}.sh"
printf '%s\n' "${REMOTE_SCRIPT}" | ssh "${SSH_OPTS[@]}" "${VM_USER}@${VM_HOST}" \
  "$(printf 'cat > %q && chmod 700 %q' "${REMOTE_PATH}" "${REMOTE_PATH}")"
echo "Deploy script written to VM."

REMOTE_CMD=$(printf 'docker login ghcr.io -u %q --password-stdin && bash %q %q %q %q %q %q %q %q' \
  "${GITHUB_ACTOR}" "${REMOTE_PATH}" "${VM_COMPOSE_DIR}" "${MODE}" "${SHA}" \
  "${BACKEND_REF}" "${INGEST_REF}" "${FRONTEND_REF}" "${RUN_MIGRATIONS}")
printf '%s' "${GITHUB_TOKEN}" | ssh "${SSH_OPTS[@]}" "${VM_USER}@${VM_HOST}" "${REMOTE_CMD}"
echo "Deploy script completed."
