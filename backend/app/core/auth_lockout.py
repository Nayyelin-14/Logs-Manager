"""Redis-backed failed-login lockout service.

Replaces the in-memory ``_FAILED_LOGIN_TRACKER`` dictionary with a Redis-backed
mechanism so that lockout state is shared across all backend instances
(Docker replicas, worker, etc.) instead of being local to a single process.

Two Redis key families are used (both with a 900-second / 15-minute TTL):

* ``lms:auth:login:failed:{email_hash}`` -- integer counter of failed attempts
  within the current window.
* ``lms:auth:login:locked:{email_hash}`` -- lockout flag (value ``1``).

The lockout key is authoritative: if it exists, the account is locked.

All email addresses are SHA-256 hashed before being embedded in Redis keys, so
no plaintext email, password, password hash, access token, or session cookie is
ever stored in Redis.

A new Redis client is opened for each operation (following the pattern used by
``app.api.routes.health``), so the service is safe to call from any asyncio
event loop without cross-loop connection issues.
"""

from __future__ import annotations

import hashlib
import logging

import redis.asyncio as redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# ---------------------------------------------------------------------------
# Configuration (driven by existing settings, not hardcoded)
# ---------------------------------------------------------------------------

FAILED_LOGIN_ATTEMPTS = settings.LOGIN_LOCKOUT_ATTEMPTS  # 5
LOCKOUT_TTL_SECONDS = settings.LOGIN_LOCKOUT_MINUTES * 60  # 900
COUNTER_TTL_SECONDS = settings.LOGIN_LOCKOUT_MINUTES * 60  # 900

FAILED_KEY_PREFIX = "lms:auth:login:failed"
LOCKED_KEY_PREFIX = "lms:auth:login:locked"

# ---------------------------------------------------------------------------
# Redis client factory (reuses the same configured REDIS_URL as SlowAPI
# and the health readiness check -- no new provider or connection pool)
# ---------------------------------------------------------------------------


def _redis_client() -> redis.Redis:
    """Return a fresh Redis client using the project's configured REDIS_URL.

    The caller is responsible for closing the client after use.
    """
    return redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )


# ---------------------------------------------------------------------------
# Key helpers
# ---------------------------------------------------------------------------


def _normalize_email(email: str) -> str:
    """Normalize an email for consistent hashing across cases.

    Whitespace is stripped and the address is lowercased so that
    ``Admin@Demo.LOCAL`` and ``admin@demo.local`` share the same lockout
    bucket.  This does not change database lookup semantics -- the database
    query remains case-sensitive as before.
    """
    return email.strip().lower()


def _email_hash(email: str) -> str:
    """Return a SHA-256 hash of the normalized email address.

    Never stores plaintext email in Redis keys.
    """
    return hashlib.sha256(_normalize_email(email).encode("utf-8")).hexdigest()


def _failed_key(email_hash: str) -> str:
    return f"{FAILED_KEY_PREFIX}:{email_hash}"


def _locked_key(email_hash: str) -> str:
    return f"{LOCKED_KEY_PREFIX}:{email_hash}"


# ---------------------------------------------------------------------------
# Atomic Lua scripts
# ---------------------------------------------------------------------------

# Increment the failed-attempt counter and, if the threshold is reached, set
# the lockout key.  Returns [current_count, lockout_activated].
_RECORD_FAILED_LUA = """
local counter_key = KEYS[1]
local lock_key = KEYS[2]
local threshold = tonumber(ARGV[1])
local counter_ttl = tonumber(ARGV[2])
local lock_ttl = tonumber(ARGV[3])

local current = redis.call('INCR', counter_key)
if current == 1 then
    redis.call('EXPIRE', counter_key, counter_ttl)
end

if current >= threshold then
    redis.call('SET', lock_key, '1', 'EX', lock_ttl)
    return {current, 1}
end
return {current, 0}
"""

# Check whether the account is currently locked.  Returns [locked, ttl_remaining].
_CHECK_LOCKED_LUA = """
local lock_key = KEYS[1]
local locked = redis.call('EXISTS', lock_key)
if locked == 1 then
    local ttl = redis.call('TTL', lock_key)
    return {1, ttl}
end
return {0, 0}
"""


# ---------------------------------------------------------------------------
# Clear both keys
# ---------------------------------------------------------------------------

_CLEAR_KEYS_LUA = """
local counter_key = KEYS[1]
local lock_key = KEYS[2]
redis.call('DEL', counter_key)
redis.call('DEL', lock_key)
return 1
"""


class RedisUnavailableError(RuntimeError):
    """Raised when Redis cannot be reached for lockout operations."""


class AuthLockoutService:
    """Redis-backed failed-login lockout service.

    All methods are fail-closed: if Redis cannot be reached, the caller
    receives an error rather than silently bypassing lockout protection.

    Each method opens its own Redis client and closes it before returning,
    so the service is safe to call from any asyncio event loop.
    """

    # ------------------------------------------------------------------
    # Lockout check
    # ------------------------------------------------------------------

    async def is_locked_out(self, email: str) -> tuple[bool, int]:
        """Return ``(locked, retry_after_seconds)`` for the given email.

        Raises ``RedisUnavailableError`` if Redis cannot be reached.
        """
        email_hash = _email_hash(email)
        client = _redis_client()
        try:
            result = await client.eval(
                _CHECK_LOCKED_LUA,
                1,
                _locked_key(email_hash),
            )
            locked = int(result[0]) == 1
            ttl = int(result[1]) if result[1] > 0 else 0
            return locked, ttl
        except redis.RedisError as exc:
            logger.error("redis lockout check failed: %s", type(exc).__name__)
            raise RedisUnavailableError("lockout check unavailable") from exc
        finally:
            try:
                await client.aclose()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Record a failed attempt
    # ------------------------------------------------------------------

    async def record_failed_login(self, email: str) -> tuple[int, bool]:
        """Record a failed login attempt.

        Returns ``(count, lockout_activated)``.  Raises ``RedisUnavailableError``
        if Redis cannot be reached -- the caller must treat this as a
        controlled service failure (503), not as a successful authentication.
        """
        email_hash = _email_hash(email)
        client = _redis_client()
        try:
            result = await client.eval(
                _RECORD_FAILED_LUA,
                2,
                _failed_key(email_hash),
                _locked_key(email_hash),
                FAILED_LOGIN_ATTEMPTS,
                COUNTER_TTL_SECONDS,
                LOCKOUT_TTL_SECONDS,
            )
            count = int(result[0])
            lockout_activated = int(result[1]) == 1
            if lockout_activated:
                logger.warning(
                    "auth lockout activated: email_hash=%s attempts=%d",
                    email_hash[:12],
                    count,
                )
            return count, lockout_activated
        except redis.RedisError as exc:
            logger.error("redis record failed-login failed: %s", type(exc).__name__)
            raise RedisUnavailableError("failed-login recording unavailable") from exc
        finally:
            try:
                await client.aclose()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Clear on successful login
    # ------------------------------------------------------------------

    async def clear_failed_logins(self, email: str) -> None:
        """Delete both lockout and counter keys after a successful login."""
        email_hash = _email_hash(email)
        client = _redis_client()
        try:
            await client.eval(
                _CLEAR_KEYS_LUA,
                2,
                _failed_key(email_hash),
                _locked_key(email_hash),
            )
        except redis.RedisError as exc:
            logger.error("redis clear failed-logins failed: %s", type(exc).__name__)
            raise RedisUnavailableError("failed-login cleanup unavailable") from exc
        finally:
            try:
                await client.aclose()
            except Exception:
                pass


# Module-level singleton service (stateless -- safe to import and reuse).
auth_lockout = AuthLockoutService()
