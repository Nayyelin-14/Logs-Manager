#!/usr/bin/env bash
set -euo pipefail

BACKEND_URL="${1:?usage: smoke_saas.sh <backend-url> [frontend-url]}"
FRONTEND_URL="${2:-}"
EXPECTED_SHA="${EXPECTED_SHA:-}"

echo "Checking backend health..."
curl -fsS --max-time 90 "${BACKEND_URL}/healthz" | grep -q '"status"'

echo "Checking backend readiness..."
curl -fsS --max-time 90 "${BACKEND_URL}/ready" | grep -q '"status":"ready"'

if [ -n "${EXPECTED_SHA}" ]; then
  echo "Checking deployed commit..."
  DEPLOYED_SHA=$(curl -fsS --max-time 30 "${BACKEND_URL}/version" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("git_sha",""))')
  if [ "${DEPLOYED_SHA}" != "${EXPECTED_SHA}" ]; then
    echo "Expected commit ${EXPECTED_SHA}, got ${DEPLOYED_SHA}" >&2
    exit 1
  fi
fi

echo "Checking unauthenticated API enforcement..."
CODE=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 30 "${BACKEND_URL}/api/get-logs")
if [ "${CODE}" != "401" ]; then
  echo "Expected 401 from /api/get-logs, got ${CODE}" >&2
  exit 1
fi

if [ -n "${FRONTEND_URL}" ]; then
  echo "Checking frontend SPA..."
  curl -fsS --max-time 90 "${FRONTEND_URL}/" | grep -qi '<!doctype html'
  echo "Checking frontend API proxy..."
  CODE=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 90 "${FRONTEND_URL}/api/get-logs")
  if [ "${CODE}" != "401" ]; then
    echo "Expected 401 from the proxied /api/get-logs, got ${CODE}" >&2
    exit 1
  fi
fi

echo "SaaS smoke checks passed."
