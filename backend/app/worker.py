"""
Background worker: alert sweep every 30s + hourly retention maintenance.

Runs as a standalone container process (no network ports). Can also be
imported and started within the FastAPI lifespan (embedded mode).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.core.config import get_settings
from app.core.database import async_session_maker, EFFECTIVE_DB_TARGET
from app.services.alerting.evaluator import evaluate_all_rules
from app.services.retention import run_retention_once

settings = get_settings()
logger = logging.getLogger("worker")


async def alert_sweep(interval_seconds: int = 30) -> None:
    """Run evaluate_all_rules every interval_seconds. Never crashes."""
    logger.info("Worker starting: db_target=%s", EFFECTIVE_DB_TARGET)
    logger.info("Alert sweep started (interval=%ds)", interval_seconds)
    while True:
        try:
            async with async_session_maker() as session:
                now = datetime.now(timezone.utc)
                alerts = await evaluate_all_rules(session, now)
                if alerts:
                    logger.info("Alert sweep: %d rule(s) triggered", len(alerts))
                await session.commit()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - never crash the sweep
            logger.exception("Alert sweep error: %s", exc)
        await asyncio.sleep(interval_seconds)


async def retention_maintenance(interval_seconds: int = 3600) -> None:
    """Run retention purge every interval_seconds. Never crashes."""
    logger.info("Retention maintenance started (interval=%ds)", interval_seconds)
    while True:
        try:
            deleted = await run_retention_once()
            if deleted:
                logger.info("Retention maintenance: purged %d events", deleted)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - never crash maintenance
            logger.exception("Retention maintenance error: %s", exc)
        await asyncio.sleep(interval_seconds)


async def run() -> None:
    """Run both loops concurrently."""
    await asyncio.gather(
        alert_sweep(settings.ALERT_SWEEP_INTERVAL if hasattr(settings, 'ALERT_SWEEP_INTERVAL') else 30),
        retention_maintenance(),
    )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(run())


if __name__ == "__main__":
    main()
