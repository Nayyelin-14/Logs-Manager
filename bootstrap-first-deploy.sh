set -euo pipefail

VM_COMPOSE_DIR="${VM_COMPOSE_DIR:?VM_COMPOSE_DIR must be set}"

DEPLOY_DIR="${VM_COMPOSE_DIR}/.deploy"
BACKUP_DIR="${DEPLOY_DIR}/backups"
CURRENT_ENV="${DEPLOY_DIR}/current.env"
FLAGS_ENV="${DEPLOY_DIR}/flags.env"

echo "=== First-deploy bootstrap ==="
echo "VM_COMPOSE_DIR: ${VM_COMPOSE_DIR}"

mkdir -p "${DEPLOY_DIR}" "${BACKUP_DIR}"

echo ""
echo "Step 1: Discovering locally-built image digests..."

BACKEND_DIGEST=""
INGEST_DIGEST=""
FRONTEND_DIGEST=""

for img in $(docker images --format "{{.Repository}}:{{.Tag}}"); do
  repo="${img%:*}"
  case "$repo" in
    *backend*)
      digest=$(docker inspect --format='{{index .RepoDigests 0}}' "$img" 2>/dev/null || echo "")
      if [ -n "$digest" ] && [ -z "$BACKEND_DIGEST" ]; then
        BACKEND_DIGEST="$digest"
      fi
      ;;
    *ingest*)
      digest=$(docker inspect --format='{{index .RepoDigests 0}}' "$img" 2>/dev/null || echo "")
      if [ -n "$digest" ] && [ -z "$INGEST_DIGEST" ]; then
        INGEST_DIGEST="$digest"
      fi
      ;;
    *frontend*)
      digest=$(docker inspect --format='{{index .RepoDigests 0}}' "$img" 2>/dev/null || echo "")
      if [ -n "$digest" ] && [ -z "$FRONTEND_DIGEST" ]; then
        FRONTEND_DIGEST="$digest"
      fi
      ;;
  esac
done

echo "Backend digest: ${BACKEND_DIGEST:-<not detected>}"
echo "Ingest digest:  ${INGEST_DIGEST:-<not detected>}"
echo "Frontend digest: ${FRONTEND_DIGEST:-<not detected>}"

echo ""
echo "Step 2: Writing .deploy/current.env..."

cat > "${CURRENT_ENV}" <<CURRENT_ENV_EOF
BACKEND_IMAGE=${BACKEND_DIGEST:-}
INGEST_IMAGE=${INGEST_DIGEST:-}
FRONTEND_IMAGE=${FRONTEND_DIGEST:-}
CURRENT_ENV_EOF

echo "Wrote ${CURRENT_ENV}"

echo ""
echo "Step 3: Writing .deploy/flags.env..."

cat > "${FLAGS_ENV}" <<FLAGS_ENV_EOF
FEATURE_SEARCH_ENABLED=false
FEATURE_DELETE_POST_ENABLED=false
FEATURE_TEST_FLAG_ENABLED=false
FLAGS_ENV_EOF

echo "Wrote ${FLAGS_ENV}"

echo ""
echo "Step 4: Checking docker-compose.vm.yml..."

COMPOSE_FILE="${VM_COMPOSE_DIR}/docker-compose.vm.yml"
if [ ! -f "${COMPOSE_FILE}" ]; then
  echo "ERROR: ${COMPOSE_FILE} not found." >&2
  echo "Copy docker-compose.vm.yml to the VM first." >&2
  exit 1
fi

if grep -qE '^\s*build:' "${COMPOSE_FILE}"; then
  echo "WARNING: docker-compose.vm.yml still contains 'build:' for app services." >&2
  echo "  Edit the file to use image: \${BACKEND_IMAGE}, \${INGEST_IMAGE}, \${FRONTEND_IMAGE}" >&2
  echo "  See Stage 2 compose diff for the exact changes." >&2
else
  echo "docker-compose.vm.yml uses image: variables — ready for pipeline deploy."
fi

echo ""
echo "Step 5: Checking .env..."

ENV_FILE="${VM_COMPOSE_DIR}/.env"
if [ -f "${ENV_FILE}" ]; then
  echo ""
  echo "Checking .env..."
  for var in DATABASE_URL ACCESS_TOKEN_SECRET REFRESH_TOKEN_SECRET INGEST_API_KEY; do
    if grep -q "^${var}=" "${ENV_FILE}"; then
      echo "  ${var}: set"
    else
      echo "  ${var}: MISSING — add to .env" >&2
    fi
  done
else
  echo ""
  echo ".env not found at ${ENV_FILE}" >&2
  echo "  Copy .env.example to .env and fill in all required values." >&2
fi

echo ""
echo "=== Bootstrap complete ==="
echo ""
echo "Next steps:"
echo "  1. Review .deploy/current.env and .deploy/flags.env"
echo "  2. Verify docker-compose.vm.yml uses image: variables"
echo "  3. Dispatch the 'Deploy to VM' workflow with dry_run=true first"
echo "  4. If dry run passes, dispatch with dry_run=false"
echo ""
echo "Example dry run dispatch:"
echo "  gh workflow run deploy.yml -f image_ref=dev-\$(date -u +%Y%m%d-%H%M%S)-\$(git rev-parse --short HEAD) -f dry_run=true"
