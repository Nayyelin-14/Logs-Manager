"""
Queue Integration Module

Provides Redis-based queue operations using arq.
"""

import time
import json
from typing import Any, Dict, Optional
from arq import create_pool
from arq.connections import RedisSettings
from app.core.config import get_settings

settings = get_settings()


async def get_redis_pool():
    """Get or create Redis connection pool for arq."""
    return await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))


# Job type definitions
class JobDefs:
    OTP_EMAIL = "otp_email"
    ALERT_EMAIL = "alert_email"
    INVALIDATE_LOG_CACHE = "invalidate_log_cache"
    INVALIDATE_RULE_CACHE = "invalidate_rule_cache"


async def enqueue_otp_email(email: str, otp_code: int, otp_id: int) -> Any:
    """Enqueue OTP email job."""
    pool = await get_redis_pool()
    return await pool.enqueue_job(
        JobDefs.OTP_EMAIL,
        email=email,
        otp_code=otp_code,
        otp_id=otp_id,
        _job_id=f"OTP:{otp_id}:email",
        _queue_name="email_queue",
    )


async def enqueue_alert_email(
    email: str,
    username: str,
    tenant: str,
    title: str,
    description: str,
    severity: str,
    alert_id: Optional[str] = None
) -> Any:
    """Enqueue alert notification email job."""
    pool = await get_redis_pool()
    return await pool.enqueue_job(
        JobDefs.ALERT_EMAIL,
        email=email,
        username=username,
        tenant=tenant,
        title=title,
        description=description,
        severity=severity,
        alert_id=alert_id,
        _job_id=f"ALERT:{tenant}:{alert_id or int(time.time())}",
        _queue_name="email_queue",
    )


async def enqueue_cache_invalidation(pattern: str, queue: str = "cache_invalidation") -> Any:
    """Enqueue cache invalidation job."""
    pool = await get_redis_pool()
    return await pool.enqueue_job(
        "invalidate_cache",
        pattern=pattern,
        _job_id=f"cache:{pattern}:{int(time.time())}",
        _queue_name=queue,
    )