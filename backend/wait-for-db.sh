#!/usr/bin/env bash
set -e

echo "Waiting for PostgreSQL..."

# Use DATABASE_URL if available, otherwise fall back to hardcoded defaults
DB_URL="${DATABASE_URL:-postgresql+asyncpg://logs:postgres_pass@db:5432/logs_manager?sslmode=disable}"

# Extract sslmode from URL (default to disable for local/docker)
SSLMODE="disable"
if echo "$DB_URL" | grep -q "sslmode="; then
  SSLMODE=$(echo "$DB_URL" | sed -n 's/.*sslmode=\([^&]*\).*/\1/p')
fi

for i in $(seq 1 60); do
  python3 -c "
import asyncio
import asyncpg
import urllib.parse

url = urllib.parse.urlparse('''$DB_URL'''.replace('+asyncpg', ''))
sslmode = '''$SSLMODE'''

async def test():
    try:
        connect_args = {}
        if sslmode == 'require':
            import ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            connect_args['ssl'] = ctx
        elif sslmode in ('verify-ca', 'verify-full'):
            import ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_REQUIRED
            connect_args['ssl'] = ctx

        conn = await asyncpg.connect(
            host=url.hostname,
            port=url.port or 5432,
            user=url.username,
            password=url.password,
            database=url.path.lstrip('/'),
            **connect_args,
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
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-4500}"
