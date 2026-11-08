set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-lms_local}"
TEST_TENANT="retention_test"
BACKEND_SERVICE="backend"

echo "============================================="
echo " Retention Policy Demo (7-day window)"
echo "============================================="

echo "[1] Inserting test events into tenant '$TEST_TENANT'..."
docker compose -p "$COMPOSE_PROJECT_NAME" exec -T "$BACKEND_SERVICE" python3 -c "
import asyncio, hashlib
from datetime import datetime, timedelta, timezone
from app.core.database import async_session_maker
from app.models.events import Event
from sqlalchemy import select, func

async def main():
    async with async_session_maker() as session:
        now = datetime.now(timezone.utc)
        old_8d = now - timedelta(days=8)
        old_6d = now - timedelta(days=6)

        id_8d = hashlib.sha256(f'retention_test|ad|{old_8d.isoformat()}|8day'.encode()).hexdigest()[:64]
        session.add(Event(
            id=id_8d, ts=old_8d, tenant='$TEST_TENANT', source='ad',
            event_type='LogonFailed', user_name='retest', src_ip='10.0.0.99',
            severity=7, action='login', outcome='failure',
            raw={'_retention_test': True, 'age_days': 8},
            _tags=['retention', 'test'], ingested_at=old_8d,
        ))

        id_6d = hashlib.sha256(f'retention_test|ad|{old_6d.isoformat()}|6day'.encode()).hexdigest()[:64]
        session.add(Event(
            id=id_6d, ts=old_6d, tenant='$TEST_TENANT', source='ad',
            event_type='LogonFailed', user_name='retest', src_ip='10.0.0.98',
            severity=7, action='login', outcome='failure',
            raw={'_retention_test': True, 'age_days': 6},
            _tags=['retention', 'test'], ingested_at=old_6d,
        ))

        await session.commit()
        before = await session.execute(
            select(func.count()).select_from(Event).where(Event.tenant == '$TEST_TENANT')
        )
        print(f'  Before retention: {before.scalar()} events')

asyncio.run(main())
" 2>&1

echo ""

echo "[2] Running retention maintenance (RETENTION_DAYS=7)..."
docker compose -p "$COMPOSE_PROJECT_NAME" exec -T "$BACKEND_SERVICE" python3 -m app.services.retention --days 7 2>&1

echo ""

echo "[3] Counting events after retention and cleaning up..."
docker compose -p "$COMPOSE_PROJECT_NAME" exec -T "$BACKEND_SERVICE" python3 -c "
import asyncio
from app.core.database import async_session_maker
from app.models.events import Event
from sqlalchemy import select, func, text as sql_text

async def main():
    async with async_session_maker() as session:
        after = await session.execute(
            select(func.count()).select_from(Event).where(Event.tenant == '$TEST_TENANT')
        )
        count = after.scalar()
        print(f'  After retention: {count} events')

        if count == 1:
            print('  PASS: 8-day-old event purged, 6-day-old event kept')
        elif count == 0:
            print('  FAIL: Both events were purged (6-day-old should be kept)')
        else:
            print(f'  FAIL: Expected 1 event, got {count}')

        await session.execute(sql_text(\"DELETE FROM events WHERE tenant = '$TEST_TENANT'\"))
        await session.commit()
        print('  Cleaned up test tenant events')

asyncio.run(main())
" 2>&1

echo ""
echo "============================================="
echo " Retention demo complete"
echo "============================================="
