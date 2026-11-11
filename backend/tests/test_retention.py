"""Retention acceptance tests.

The assignment requires at least seven days of retention. These checks assert
the configured default and prove that the purge removes only expired rows while
a dry run changes nothing.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.database import async_session_maker
from app.models.events import Event
from app.schemas.normalized_event import Source
from app.services.retention import purge_expired_events, run_retention_once


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
async def test_retention_is_at_least_seven_days_and_purges_only_expired(test_database):
    assert get_settings().RETENTION_DAYS >= 7

    async with async_session_maker() as session:
        old = _event("retention_old", timedelta(days=8))
        fresh = _event("retention_fresh", timedelta(days=1))
        session.add_all([old, fresh])
        await session.commit()

        would_purge = await run_retention_once(dry_run=True)
        assert would_purge >= 1
        still_there = (
            await session.execute(
                select(Event).where(Event.id == old.id, Event.ts == old.ts)
            )
        ).scalar_one_or_none()
        assert still_there is not None, "dry run must not delete rows"

        deleted = await purge_expired_events(session)
        assert deleted >= 1
        old_row = (
            await session.execute(
                select(Event).where(Event.id == old.id, Event.ts == old.ts)
            )
        ).scalar_one_or_none()
        fresh_row = (
            await session.execute(
                select(Event).where(Event.id == fresh.id, Event.ts == fresh.ts)
            )
        ).scalar_one_or_none()
        assert old_row is None, "events older than the retention window must be purged"
        assert fresh_row is not None, "events inside the window must survive"

        await session.execute(
            delete(Event).where(Event.id == fresh.id, Event.ts == fresh.ts)
        )
        await session.commit()
