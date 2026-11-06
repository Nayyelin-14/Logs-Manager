#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:4500}"
API_KEY="${INGEST_API_KEY:-ingest-key-dev}"
EMAIL="${ADMIN_EMAIL:-admin@demo.local}"
PASSWORD="${ADMIN_PASSWORD:-$SEED_ADMIN_PASSWORD}"
TENANT="${TENANT:-demoA}"

JAR="$(mktemp)"
trap 'rm -f "$JAR"' EXIT

failures=0

pass() { printf '  ok   %s\n' "$1"; }
fail() { printf '  FAIL %s\n' "$1"; failures=$((failures + 1)); }

request() {
  local name="$1"
  local method="$2"
  local path="$3"
  shift 3

  local body
  body="$(curl -sS -o /tmp/lms_smoke_body -w '%{http_code}' -X "$method" \
    "$BASE_URL$path" "$@" 2>/tmp/lms_smoke_err)" || {
    fail "$name (curl error: $(cat /tmp/lms_smoke_err))"
    return 1
  }

  if [[ "$body" =~ ^2 ]]; then
    pass "$name"
    return 0
  fi

  fail "$name (HTTP $body: $(cat /tmp/lms_smoke_body))"
  return 1
}

echo "Smoke testing $BASE_URL"

request "health endpoint" GET /healthz || true

request "login" POST /api/auth/login \
  -c "$JAR" -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" || true

request "authenticated auth-check" GET /api/auth/auth-check -b "$JAR" || true

request "single ingest" POST /api/ingest \
  -H "Content-Type: application/json" -H "X-API-Key: $API_KEY" \
  -d "{\"source\":\"api\",\"tenant\":\"$TENANT\",\"event_type\":\"smoke_test\",\"user\":\"smoke\",\"ip\":\"203.0.113.99\",\"severity\":6}" || true

request "batch ingest" POST /api/ingest/batch \
  -H "Content-Type: application/json" -H "X-API-Key: $API_KEY" \
  -d "{\"events\":[{\"source\":\"api\",\"event_type\":\"smoke_batch_1\"},{\"source\":\"aws\",\"eventName\":\"CreateUser\",\"eventSource\":\"iam.amazonaws.com\"}]}" || true

request "list logs" GET "/api/get-logs?limit=5" -b "$JAR" || true
request "list alerts" GET "/api/get-alerts?limit=5" -b "$JAR" || true
request "dashboard" GET "/api/dashboard?range=7d&tenant=$TENANT" -b "$JAR" || true
request "list rules" GET "/api/get-rules?limit=5" -b "$JAR" || true

echo
if [ "$failures" -eq 0 ]; then
  echo "All smoke checks passed."
else
  echo "$failures smoke check(s) failed."
  exit 1
fi
