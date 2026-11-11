"""Shared in-process rate limiter.

Kept in its own module so route modules can decorate handlers without
importing ``app.main`` (which would create a circular import).

Rate-limit identity is never derived from an unverified ``X-API-Key`` header.
An attacker can fabricate arbitrary API keys to create unlimited independent
rate-limit buckets, so the key is only used later by ``verify_api_key`` for
authentication -- never for bucket selection.

Identity resolution (in order):

1. UI / session-authenticated traffic: the server-issued ``accessToken``
   cookie is hashed and used as a stable, unforgeable per-session identity.
   The cookie is HttpOnly and set only after successful login, so clients
   cannot forge it.
2. Machine API-key and unauthenticated traffic: the remote address (peer IP,
   not a forwarded header) is used. Invalid or fabricated API keys are
   rejected by ``verify_api_key`` with 401 and still consume IP budget, so
   arbitrary headers cannot bypass rate limits.
"""

import hashlib

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


def ingest_rate_key(request: Request) -> str:
    """Return a rate-limit identity for ingestion requests.

    Never uses the raw ``X-API-Key`` header, which is unverified at rate-limit
    time and can be forged to create unlimited buckets.
    """

    # UI / session-authenticated traffic: stable, server-issued identity.
    access_token = request.cookies.get("accessToken")
    if access_token:
        return "ui:" + hashlib.sha256(access_token.encode()).hexdigest()[:32]

    # Machine API-key and unauthenticated traffic: peer IP only. The API key
    # (if any) is verified later by verify_api_key; it never selects a bucket here.
    return "ip:" + str(get_remote_address(request))


limiter = Limiter(key_func=ingest_rate_key)
