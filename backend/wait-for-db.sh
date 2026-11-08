echo "Waiting for PostgreSQL at db:5432..."
for i in $(seq 1 60); do
  python3 -c "
import asyncio
import asyncpg
async def test():
    try:
        conn = await asyncpg.connect(
            host='db', port=5432,
            user='logs', password='postgres_pass',
            database='logs_manager',
            ssl=False
        )
        await conn.close()
        print('PostgreSQL is ready')
    except Exception as e:
        print(f'PostgreSQL is unavailable: {e}')
        raise
asyncio.run(test())
" && break
  echo "PostgreSQL is unavailable - sleeping ($i/60)"
  sleep 2
done
echo "PostgreSQL is ready - starting backend"
exec uvicorn app.main:app --host 0.0.0.0 --port 4500