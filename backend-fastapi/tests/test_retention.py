"""Retention (7-day purge) tests against the test database."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select

from app.core.database import async_session_maker
from app.models.enums import Source
from app.models.security_event import SecurityEvent
from app.services.retention import (
    _cron_kwargs,
    count_expired,
    purge_expired_events,
    run_retention_once,
)


def _event(event_type: str, age: timedelta) -> SecurityEvent:
    now = datetime.now(timezone.utc)
    return SecurityEvent(
        id=uuid.uuid4().hex[:25],
        timestamp=now - age,
        tenant="retention-test",
        source=Source.API,
        event_type=event_type,
        severity=1,
        raw={"retention_probe": True},
        tags=["retention-test"],
        description=f"retention probe {event_type}",
    )


@pytest.mark.asyncio
async def test_purge_removes_only_expired_events():
    session = async_session_maker()
    old = _event("retention_old", timedelta(days=8))
    fresh = _event("retention_fresh", timedelta(days=1))
    try:
        session.add_all([old, fresh])
        await session.commit()

        deleted = await purge_expired_events(session)
        assert deleted >= 1

        old_row = (
            await session.execute(select(SecurityEvent).where(SecurityEvent.id == old.id))
        ).scalar_one_or_none()
        fresh_row = (
            await session.execute(select(SecurityEvent).where(SecurityEvent.id == fresh.id))
        ).scalar_one_or_none()
        assert old_row is None, "event older than 7 days must be purged"
        assert fresh_row is not None, "event inside the retention window must survive"
    finally:
        await session.execute(delete(SecurityEvent).where(SecurityEvent.id == fresh.id))
        await session.commit()
        await session.close()


@pytest.mark.asyncio
async def test_count_expired_does_not_delete():
    session = async_session_maker()
    old = _event("retention_count", timedelta(days=9))
    try:
        session.add(old)
        await session.commit()

        before = await count_expired(session)
        assert before >= 1
        still_there = (
            await session.execute(select(SecurityEvent).where(SecurityEvent.id == old.id))
        ).scalar_one_or_none()
        assert still_there is not None, "count must not delete rows"
    finally:
        await session.execute(delete(SecurityEvent).where(SecurityEvent.id == old.id))
        await session.commit()
        await session.close()


@pytest.mark.asyncio
async def test_run_retention_once_dry_run():
    session = async_session_maker()
    old = _event("retention_dry", timedelta(days=10))
    try:
        session.add(old)
        await session.commit()

        would_purge = await run_retention_once(dry_run=True)
        assert would_purge >= 1
        still_there = (
            await session.execute(select(SecurityEvent).where(SecurityEvent.id == old.id))
        ).scalar_one_or_none()
        assert still_there is not None
    finally:
        await session.execute(delete(SecurityEvent).where(SecurityEvent.id == old.id))
        await session.commit()
        await session.close()


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
