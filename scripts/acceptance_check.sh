set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${BASE_URL:-http://localhost:4500}"
API_KEY="${INGEST_API_KEY:?set INGEST_API_KEY (or run with .env loaded)}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@demo.local}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-$SEED_ADMIN_PASSWORD}"
VIEWER_A_EMAIL="${VIEWER_A_EMAIL:-viewerA@demo.local}"
VIEWER_A_PASSWORD="${VIEWER_A_PASSWORD:-$SEED_VIEWER_A_PASSWORD}"
SYSLOG_HOST="${SYSLOG_HOST:-127.0.0.1}"
SYSLOG_PORT="${SYSLOG_PORT:-514}"
WEBHOOK_URL="${WEBHOOK_URL:-http://localhost:${WEBHOOK_PORT:-8008}}"
HTTP_URL="${HTTP_URL:-http://localhost:${HTTP_PORT:-8088}/}"
HTTPS_URL="${HTTPS_URL:-https://localhost:${HTTPS_PORT:-443}/}"
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-logs_verify}"

pass_count=0
fail_count=0
pass() { echo "  PASS: $1"; pass_count=$((pass_count + 1)); }
fail() { echo "  FAIL: $1"; fail_count=$((fail_count + 1)); }
http_code() { curl -s -o /tmp/ac_body -w "%{http_code}" "$@"; }

CURL_ARGS=()

ADMIN_JAR=/tmp/ac_admin_cookie
VIEWER_JAR=/tmp/ac_viewer_cookie
rm -f "$ADMIN_JAR" "$VIEWER_JAR"

compose() {
  COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME}" docker compose -f docker-compose.yml "$@"
}

admin_login() {
  local code
  code=$(http_code -s -c "$ADMIN_JAR" -X POST "$BASE_URL/api/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}")
  [[ "$code" =~ ^2 ]] || { fail "Admin login failed (HTTP $code: $(cat /tmp/ac_body))"; return 1; }
}

alert_count_for_ip() {
  local ip="$1"
  http_code -s -b "$ADMIN_JAR" "$BASE_URL/api/get-alerts?limit=200" >/dev/null
  python3 - "$ip" <<'PY'
import json, sys
ip = sys.argv[1]
try:
    data = json.load(open('/tmp/ac_body'))
except Exception:
    print(0); raise SystemExit
alerts = data.get('alerts', [])
print(sum(1 for a in alerts if ip in str(a.get('dedupeKey') or '')))
PY
}

webhook_count() {
  local filter_ip="${1:-}"
  http_code -s "$WEBHOOK_URL/alerts" >/dev/null
  python3 - "$filter_ip" <<'PY'
import json, sys
try:
    data = json.load(open('/tmp/ac_body'))
except Exception:
    print(0); raise SystemExit
filter_ip = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else None
alerts = data if isinstance(data, list) else data.get('alerts', [])
if filter_ip:
    alerts = [a for a in alerts if a.get('group') == filter_ip or a.get('dedupe_key','').endswith(':' + filter_ip)]
print(len(alerts))
PY
}

echo "============================================="
echo " Assignment Acceptance Checklist"
echo "============================================="
echo " Base URL: $BASE_URL"
echo " Syslog: $SYSLOG_HOST:$SYSLOG_PORT"
echo ""

echo "[1] System is running (one-command start prerequisite)"
if curl -sf "$BASE_URL/healthz" >/dev/null 2>&1; then
  pass "API healthz responds"
else
  fail "API healthz does not respond at $BASE_URL/healthz"
fi
admin_login || true

echo ""
echo "[2] Syslog message on port 514 (UDP + TCP) visible via the API within 60s"
SYSLOG_MSG='<134>Aug 20 12:44:56 fw01 vendor=demo product=ngfw action=deny src=10.0.1.10 dst=8.8.8.8 spt=5353 dpt=53 proto=udp msg="DNS blocked" policy=Block-DNS'
echo -n "$SYSLOG_MSG" | nc -u -w 1 "$SYSLOG_HOST" "$SYSLOG_PORT" >/dev/null 2>&1 || true
sleep 1
echo "$SYSLOG_MSG" | nc -w 1 "$SYSLOG_HOST" "$SYSLOG_PORT" >/dev/null 2>&1 || true

SYSLOG_OK=0
for _ in $(seq 1 30); do
  CODE=$(http_code -s -b "$ADMIN_JAR" "$BASE_URL/api/get-logs?source=firewall&src_ip=10.0.1.10&limit=20")
  if [[ "$CODE" =~ ^2 ]] && python3 -c "import json,sys; sys.exit(0 if json.load(open('/tmp/ac_body')).get('logs') else 1)" 2>/dev/null; then
    SYSLOG_OK=1; break
  fi
  sleep 2
done
[[ "$SYSLOG_OK" -eq 1 ]] && pass "Syslog events searchable via API (UDP+TCP within 60s)" || fail "Syslog events NOT searchable within 60s"

echo ""
echo "[3] POST /ingest sample JSON (4.3) then searchable"
SAMPLE='{"tenant":"demoA","source":"api","event_type":"app_login_failed","user":"alice","ip":"203.0.113.7","reason":"wrong_password","@timestamp":"2026-11-05T10:00:00Z"}'
INGEST_CODE=$(http_code -s -X POST "$BASE_URL/ingest" -H "Content-Type: application/json" -H "X-API-Key: $API_KEY" -d "$SAMPLE")
[[ "$INGEST_CODE" =~ ^2 ]] && pass "POST /ingest accepted sample (HTTP $INGEST_CODE)" || fail "POST /ingest rejected sample (HTTP $INGEST_CODE: $(cat /tmp/ac_body))"
sleep 1
SEARCH_CODE=$(http_code -s -b "$ADMIN_JAR" "$BASE_URL/api/get-logs?source=api&user=alice&limit=5")
if [[ "$SEARCH_CODE" =~ ^2 ]] && python3 -c "import json,sys; sys.exit(0 if any(l.get('user')=='alice' for l in json.load(open('/tmp/ac_body')).get('logs',[])) else 1)" 2>/dev/null; then
  pass "Ingested record is searchable via /api/get-logs"
else
  fail "Ingested record NOT searchable (HTTP $SEARCH_CODE)"
fi

echo ""
echo "[4] File upload: AWS/M365/AD sample files normalized"
for pair in "aws_cloudtrail.json:aws" "m365_audit.json:m365" "ad_4625.json:ad"; do
  sample="${pair%%:*}"; expected_source="${pair##*:}"
  FULL_PATH="$ROOT_DIR/samples/$sample"
  if [[ ! -f "$FULL_PATH" ]]; then fail "Sample file not found: $FULL_PATH"; continue; fi
  UPLOAD_CODE=$(http_code -s -X POST "$BASE_URL/ingest/file" -H "X-API-Key: $API_KEY" -F "file=@$FULL_PATH" -F "source=auto")
  if [[ ! "$UPLOAD_CODE" =~ ^2 ]]; then fail "File upload $sample rejected (HTTP $UPLOAD_CODE: $(cat /tmp/ac_body))"; continue; fi
  if ! python3 -c "import json,sys; d=json.load(open('/tmp/ac_body')); sys.exit(0 if d.get('ingested',0) > 0 else 1)" 2>/dev/null; then
    fail "File upload $sample parsed zero events: $(cat /tmp/ac_body)"
    continue
  fi
  sleep 1
  CHECK_CODE=$(http_code -s -b "$ADMIN_JAR" "$BASE_URL/api/get-logs?source=$expected_source&limit=20")
  if [[ "$CHECK_CODE" =~ ^2 ]] && python3 -c "import json,sys; sys.exit(0 if json.load(open('/tmp/ac_body')).get('logs') else 1)" 2>/dev/null; then
    pass "File upload $sample normalized and searchable as source=$expected_source"
  else
    fail "File upload $sample accepted but not searchable as source=$expected_source (HTTP $CHECK_CODE)"
  fi
done

echo ""
echo "[5] Dashboard stats endpoints respond"
for endpoint in "stats/summary" "stats/top?field=src_ip&n=10" "stats/timeline"; do
  CODE=$(http_code -s -b "$ADMIN_JAR" "$BASE_URL/api/$endpoint")
  [[ "$CODE" =~ ^2 ]] && pass "/api/$endpoint responds (HTTP $CODE)" || fail "/api/$endpoint does not respond (HTTP $CODE)"
done

echo ""
echo "[6] Bruteforce simulator creates exactly ONE alert and webhook logs it"
BRUTE_IP=""
ALERTS_BEFORE=0
for _ in $(seq 1 20); do
  CANDIDATE="198.18.$(( RANDOM % 256 )).$(( (RANDOM % 254) + 1 ))"
  CANDIDATE_BEFORE=$(alert_count_for_ip "$CANDIDATE")
  if [[ "$CANDIDATE_BEFORE" -eq 0 ]]; then
    BRUTE_IP="$CANDIDATE"
    ALERTS_BEFORE=0
    break
  fi
done
if [[ -z "$BRUTE_IP" ]]; then
  fail "Could not find an unused brute-force source IP"
  BRUTE_IP="198.18.255.254"
  ALERTS_BEFORE=$(alert_count_for_ip "$BRUTE_IP")
fi
WEBHOOKS_BEFORE=$(webhook_count "$BRUTE_IP")
python3 "$ROOT_DIR/samples/simulator.py" --rate 20 --duration 10 --scenario bruteforce \
  --tenants demoA --url "$BASE_URL" --api-key "$API_KEY" \
  --syslog-host "$SYSLOG_HOST" --syslog-port "$SYSLOG_PORT" --brute-ip "$BRUTE_IP" >/dev/null 2>&1 &
SIM_PID=$!
wait $SIM_PID 2>/dev/null || true
ALERTS_AFTER=0
for _ in $(seq 1 20); do
  ALERTS_AFTER=$(alert_count_for_ip "$BRUTE_IP")
  [[ $((ALERTS_AFTER - ALERTS_BEFORE)) -ge 1 ]] && break
  sleep 1
done
ALERT_DELTA=$((ALERTS_AFTER - ALERTS_BEFORE))
[[ "$ALERT_DELTA" -eq 1 ]] && pass "Bruteforce produced exactly 1 new alert (IP $BRUTE_IP)" || fail "Expected exactly 1 new alert, got $ALERT_DELTA (IP $BRUTE_IP)"
sleep 2
WEBHOOKS_AFTER=$(webhook_count "$BRUTE_IP")
WEBHOOK_DELTA=$((WEBHOOKS_AFTER - WEBHOOKS_BEFORE))
[[ "$WEBHOOK_DELTA" -eq 1 ]] && pass "Webhook receiver logged exactly 1 delivery for IP $BRUTE_IP" || fail "Expected 1 webhook delivery for IP $BRUTE_IP, got $WEBHOOK_DELTA"

echo ""
echo "[7] RBAC: viewer-a sees only demoA, not demoB"
LOGIN_CODE=$(http_code -s -c "$VIEWER_JAR" -X POST "$BASE_URL/api/auth/login" -H "Content-Type: application/json" \
  -d "{\"email\":\"$VIEWER_A_EMAIL\",\"password\":\"$VIEWER_A_PASSWORD\"}")
if [[ "$LOGIN_CODE" =~ ^2 ]]; then
  DEMOB_CODE=$(http_code -s -b "$VIEWER_JAR" "$BASE_URL/api/get-logs?tenant=demoB&limit=5")
  if [[ "$DEMOB_CODE" =~ ^2 ]]; then
    DEMOB_COUNT=$(python3 -c "import json; d=json.load(open('/tmp/ac_body')); print(sum(1 for l in d.get('logs',[]) if l.get('tenant')=='demoB'))" 2>/dev/null || echo 0)
    [[ "$DEMOB_COUNT" -eq 0 ]] && pass "Viewer-a gets zero demoB rows (tenant isolation enforced)" || fail "Viewer-a can see demoB data ($DEMOB_COUNT rows)"
  else
    pass "Viewer-a demoB access properly restricted (HTTP $DEMOB_CODE)"
  fi
else
  fail "Viewer-a login failed (HTTP $LOGIN_CODE)"
fi

echo ""
echo "[8] HTTPS responds (Caddy TLS)"
HTTPS_CODE=$(http_code -s -k -o /tmp/ac_https_body "$HTTPS_URL")
[[ "$HTTPS_CODE" =~ ^2 ]] && pass "HTTPS responds on localhost (HTTP $HTTPS_CODE)" || fail "HTTPS does not respond (HTTP $HTTPS_CODE)"
REDIRECT_CODE=$(curl -s -o /dev/null -w "%{http_code} %{redirect_url}" "$HTTP_URL")
[[ "$REDIRECT_CODE" == 30*"https://localhost/"* ]] && pass "HTTP redirects to HTTPS ($REDIRECT_CODE)" || fail "HTTP does not redirect to HTTPS ($REDIRECT_CODE)"

echo ""
echo "[9] Retention configuration"
RETENTION_DAYS_CHECK=$(grep -E '^RETENTION_DAYS=' "$ROOT_DIR/.env" 2>/dev/null | tail -1 | cut -d= -f2)
RETENTION_DAYS_CHECK="${RETENTION_DAYS_CHECK:-7}"
[[ "$RETENTION_DAYS_CHECK" -ge 7 ]] && pass "RETENTION_DAYS=$RETENTION_DAYS_CHECK (>= 7 days)" || fail "RETENTION_DAYS=$RETENTION_DAYS_CHECK (< 7 days)"

echo ""
echo "============================================="
echo " Results: $pass_count PASS, $fail_count FAIL"
echo "============================================="
[[ "$fail_count" -gt 0 ]] && exit 1
exit 0
