import time
import json
from typing import Any, Dict, Optional
from arq import create_pool
from arq.connections import RedisSettings
from app.core.config import get_settings
settings = get_settings()
async def get_redis_pool():
    return await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))

class JobDefs:
    ALERT_EMAIL = "alert_email"
    INVALIDATE_LOG_CACHE = "invalidate_log_cache"
    INVALIDATE_RULE_CACHE = "invalidate_rule_cache"
async def enqueue_alert_email(
    email: str,
    username: str,
    tenant: str,
    title: str,
    description: str,
    severity: str,
    alert_id: Optional[str] = None
) -> Any:
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
    pool = await get_redis_pool()
    return await pool.enqueue_job(
        "invalidate_cache",
        pattern=pattern,
        _job_id=f"cache:{pattern}:{int(time.time())}",
        _queue_name=queue,
    )
