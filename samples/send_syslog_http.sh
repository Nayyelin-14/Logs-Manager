#!/usr/bin/env bash
# Send newline-delimited syslog to the SaaS HTTPS endpoint.
#
# The appliance uses UDP/TCP, but Render/Vercel only expose HTTPS. This script
# posts the same syslog lines to POST /api/ingest/syslog.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
URL="${SYSLOG_HTTP_URL:-http://localhost:4500/api/ingest/syslog}"
INGEST_API_KEY="${INGEST_API_KEY:-}"
FILE="${1:-${SCRIPT_DIR}/syslog_firewall.log}"
FORMAT="${2:-text}"   # text | json

if [[ -z "${INGEST_API_KEY}" ]]; then
  echo "Set INGEST_API_KEY (tenant API key) before running." >&2
  exit 1
fi
if [[ ! -f "${FILE}" ]]; then
  echo "File not found: ${FILE}" >&2
  exit 1
fi

COMMON_HEADERS=(-H "X-API-Key: ${INGEST_API_KEY}")
if [[ -n "${INGEST_TENANT:-}" ]]; then
  URL="${URL}?tenant=${INGEST_TENANT}"
fi

case "${FORMAT}" in
  text)
    echo "POST ${URL} (text/plain) from ${FILE}"
    curl -sS -i -X POST "${URL}" \
      "${COMMON_HEADERS[@]}" \
      -H "Content-Type: text/plain; charset=utf-8" \
      --data-binary "@${FILE}"
    ;;
  json)
    if ! command -v python3 >/dev/null 2>&1; then
      echo "python3 is required for the json format" >&2
      exit 1
    fi
    PAYLOAD="$(python3 - "${FILE}" <<'PY'
import json, sys
lines = [line.rstrip("\n") for line in open(sys.argv[1], encoding="utf-8")]
print(json.dumps({"lines": [line for line in lines if line.strip()]}))
PY
)"
    echo "POST ${URL} (application/json) from ${FILE}"
    curl -sS -i -X POST "${URL}" \
      "${COMMON_HEADERS[@]}" \
      -H "Content-Type: application/json" \
      --data-binary "${PAYLOAD}"
    ;;
  *)
    echo "Usage: $0 [syslog-file] [text|json]" >&2
    exit 1
    ;;
esac
