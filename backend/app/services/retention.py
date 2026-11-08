import argparse
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import delete, func, select
from app.core.config import get_settings
from app.models.events import Event
settings = get_settings()
logger = logging.getLogger(__name__)

async def count_expired(session, days: Optional[int] = None) -> int:

    retention_days = settings.RETENTION_DAYS if days is None else days
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    result = await session.execute(
        select(func.count()).select_from(Event).where(Event.ingested_at < cutoff)
    )
    return int(result.scalar() or 0)
async def purge_expired_events(session, days: Optional[int] = None) -> int:
    retention_days = settings.RETENTION_DAYS if days is None else days
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    result = await session.execute(
        delete(Event).where(Event.ingested_at < cutoff)
    )
    await session.commit()
    deleted = int(result.rowcount or 0)
    if deleted:
        logger.info("retention: purged %s events older than %s days", deleted, retention_days)
    return deleted
async def run_retention_once(days: Optional[int] = None, dry_run: bool = False) -> int:
    from app.core.database import async_session_maker
    session = async_session_maker()
    try:
        if dry_run:
            expired = await count_expired(session, days)
            logger.info("retention dry-run: %s events would be purged", expired)
            return expired
        return await purge_expired_events(session, days)
    finally:
        await session.close()
def _cron_kwargs(cron_expr: str) -> dict:
    parts = (cron_expr or "").split()
    if len(parts) != 5:
        raise ValueError(
            f"RETENTION_SCHEDULE must be a 5-field cron expression, got {cron_expr!r}"
        )
    minute, hour, day, month, day_of_week = parts
    return {
        "minute": minute,
        "hour": hour,
        "day": day,
        "month": month,
        "day_of_week": day_of_week,
    }
def start_retention_scheduler():
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        run_retention_once,
        trigger="cron",
        id="retention_purge",
        name=f"Purge security logs older than {settings.RETENTION_DAYS} days",
        replace_existing=True,
        **_cron_kwargs(settings.RETENTION_SCHEDULE),
    )
    scheduler.start()
    logger.info(
        "retention scheduler started: schedule=%r days=%s",
        settings.RETENTION_SCHEDULE,
        settings.RETENTION_DAYS,
    )
    return scheduler
async def stop_retention_scheduler(scheduler) -> None:
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("retention scheduler stopped")


def main() -> None:
    parser = argparse.ArgumentParser(description="Purge raw security logs outside the retention window.")
    parser.add_argument("--days", type=int, default=None, help="Override RETENTION_DAYS for this run.")
    parser.add_argument("--dry-run", action="store_true", help="Count matching rows without deleting.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    deleted = asyncio.run(run_retention_once(days=args.days, dry_run=args.dry_run))
    action = "would purge" if args.dry_run else "purged"
    print(f"retention {action}: {deleted} events")

if __name__ == "__main__":
    main()
