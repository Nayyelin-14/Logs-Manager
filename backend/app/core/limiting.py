"""Shared in-process rate limiter.

Kept in its own module so route modules can decorate handlers without
importing ``app.main`` (which would create a circular import).

Ingestion traffic is keyed by the presented API key when one is available, so
one tenant cannot exhaust another tenant's budget (and Render's reverse proxy
does not collapse every client onto a single IP). Requests without an API key
fall back to the remote address.
"""

import hashlib

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


def ingest_rate_key(request: Request) -> str:
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return "key:" + hashlib.sha256(api_key.encode()).hexdigest()
    return "ip:" + str(get_remote_address(request))


limiter = Limiter(key_func=ingest_rate_key)
