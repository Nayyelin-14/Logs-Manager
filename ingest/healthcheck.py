"""Container health check for the native Syslog ingest service.

Kept dependency-free so it can run inside the slim ingest image without
importing the application or opening a socket of its own. The in-process
health server performs the actual database ``SELECT 1`` and listener checks.
"""

from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request


def main() -> int:
    port = int(os.environ.get("INGEST_HEALTH_PORT", "8090"))
    url = f"http://127.0.0.1:{port}/healthz"
    try:
        with urllib.request.urlopen(url, timeout=4) as response:
            body = response.read().decode("utf-8", errors="replace")
            print(body)
            return 0 if response.status == 200 else 1
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"health check failed ({exc.code}): {body}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"health check failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
