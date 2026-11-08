import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select

from app.core.database import async_session_maker
from app.models.events import Event
from app.schemas.normalized_event import Source
from app.services.retention import (
    _cron_kwargs,
    count_expired,
    purge_expired_events,
    run_retention_once,
)


def _event(event_type: str, ingested_age: timedelta) -> Event:
    now = datetime.now(timezone.utc)
    return Event(
        id=uuid.uuid4().hex[:20],
        ts=now + timedelta(seconds=1),
        tenant="retention-test",
        source=Source.aws,
        event_type=event_type,
        severity=1,
        raw={"retention_probe": True},
        _tags=["retention-test"],
        user_name="test",
        ingested_at=now - ingested_age,
    )


@pytest.mark.asyncio
async def test_purge_removes_only_expired_events():
    async with async_session_maker() as session:
        old = _event("retention_old", timedelta(days=8))
        fresh = _event("retention_fresh", timedelta(days=1))

        session.add_all([old, fresh])
        await session.commit()

        deleted = await purge_expired_events(session)
        assert deleted >= 1

        old_row = (
            await session.execute(select(Event).where(Event.id == old.id, Event.ts == old.ts))
        ).scalar_one_or_none()
        fresh_row = (
            await session.execute(select(Event).where(Event.id == fresh.id, Event.ts == fresh.ts))
        ).scalar_one_or_none()
        assert old_row is None, "event older than 7 days must be purged"
        assert fresh_row is not None, "event inside the retention window must survive"

        await session.execute(delete(Event).where(Event.id == fresh.id, Event.ts == fresh.ts))
        await session.commit()


@pytest.mark.asyncio
async def test_count_expired_does_not_delete():
    async with async_session_maker() as session:
        old = _event("retention_count", timedelta(days=9))

        session.add(old)
        await session.commit()

        before = await count_expired(session)
        assert before >= 1
        still_there = (
            await session.execute(select(Event).where(Event.id == old.id, Event.ts == old.ts))
        ).scalar_one_or_none()
        assert still_there is not None, "count must not delete rows"

        await session.execute(delete(Event).where(Event.id == old.id, Event.ts == old.ts))
        await session.commit()


@pytest.mark.asyncio
async def test_run_retention_once_dry_run():
    async with async_session_maker() as session:
        old = _event("retention_dry", timedelta(days=10))

        session.add(old)
        await session.commit()

        would_purge = await run_retention_once(dry_run=True)
        assert would_purge >= 1
        still_there = (
            await session.execute(select(Event).where(Event.id == old.id, Event.ts == old.ts))
        ).scalar_one_or_none()
        assert still_there is not None

        await session.execute(delete(Event).where(Event.id == old.id, Event.ts == old.ts))
        await session.commit()


def test_cron_schedule_parsing():
    assert _cron_kwargs("0 5 * * *") == {
        "minute": "0",
        "hour": "5",
        "day": "*",
        "month": "*",
        "day_of_week": "*",
    }
    with pytest.raises(ValueError, match="5-field cron"):
        _cron_kwargs("0 5 * *")


def test_retention_settings_default_to_seven_days():
    from app.core.config import get_settings

    assert get_settings().RETENTION_DAYS == 7
