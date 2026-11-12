set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:-udp}"
FILE="${2:-${SCRIPT_DIR}/syslog_firewall.log}"
HOST="${SYSLOG_HOST:-127.0.0.1}"
PORT="${SYSLOG_PORT:-514}"

if [[ ! -f "${FILE}" ]]; then
  echo "File not found: ${FILE}" >&2
  exit 1
fi

case "${MODE}" in
  udp)
    nc -u -w 1 "${HOST}" "${PORT}" < "${FILE}"
    ;;
  tcp)
    nc -w 2 "${HOST}" "${PORT}" < "${FILE}"
    ;;
  logger)
    while IFS= read -r line; do
      logger --udp --server "${HOST}" --port "${PORT}" -- "${line#<*>}"
    done < "${FILE}"
    ;;
  *)
    echo "Usage: $0 [udp|tcp|logger] [file]" >&2
    exit 1
    ;;
esac

echo "Sent ${FILE} to ${HOST}:${PORT} over ${MODE}."
