# SaaS Deployment Guide (Render + Vercel + Neon + Upstash)

This guide deploys Log Manager as a public HTTPS SaaS at **$0/month** using
free tiers only. It is separate from the single-machine appliance described in
`docs/setup_appliance.md`.

## What gets deployed

```
Browser
  │  https://<project>.vercel.app
  ▼
Vercel (React SPA, static hosting)
  │  /api/*  →  rewrite/proxy
  ▼
Render (FastAPI + embedded worker, Docker, free web service)
  │                 │
  ▼                 ▼
Neon PostgreSQL     Upstash Redis
(TLS, pooled)       (TLS, rediss://)
```

| Service | Free tier | What it runs | Main limitation |
|---|---|---|---|
| Vercel | Hobby | React SPA + `/api/*` proxy | None for this app |
| Render | Free web service | FastAPI, alert sweep, retention | 512 MB RAM, sleeps after 15 min idle |
| Neon | Free | PostgreSQL 18 | 0.5 GB storage, autosuspend |
| Upstash | Free | Redis for rate limiting/health | ~10k commands/day |

Because the API is proxied through Vercel, the browser sees a **same-origin**
`/api/*`. Auth cookies therefore work with `Secure` + `SameSite=Lax`; no
cross-site cookie workarounds are needed.

## Syslog: SaaS vs Appliance

The Docker appliance runs a native UDP/TCP listener. It binds host port **514**
(container port 5514) by default; on Docker Desktop/WSL2, or when host port 514
is busy, set `SYSLOG_HOST_PORT=5514` in `.env` and send to `-P 5514`.

Render and Vercel only expose HTTP(S), so SaaS mode keeps
`SYSLOG_ENABLED=false` and uses `POST /api/ingest/syslog` instead. It accepts
the same RFC3164, RFC5424, and key=value syslog lines as the listener:

```bash
curl -X POST https://<project>.vercel.app/api/ingest/syslog \
  -H "Content-Type: text/plain" \
  -H "X-API-Key: $INGEST_API_KEY" \
  --data-binary @samples/syslog_firewall.log
```

or JSON:

```bash
curl -X POST https://<project>.vercel.app/api/ingest/syslog \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $INGEST_API_KEY" \
  -d '{"lines": ["<190>Oct 30 22:15:01 router01 source=network action=ALLOW src=192.168.1.10 dst=1.1.1.1 msg=\"outbound https\""]}'
```

Response (HTTP 202):

```json
{"accepted": 1, "rejected": 0, "errors": []}
```

- Tenant is taken from the API key. A mismatched `tenant` in the body/query
  returns **403**.
- Default limits are 1 MiB body and 1000 lines; larger requests return **413**.
- Each event is normalized through the same `parse_syslog_message` +
  `IngestionService`/`NormalizationService` path as the native listener, and is
  tagged `transport=http-syslog`.
- The route is rate limited with the shared limiter
  (`INGEST_RATE_LIMIT`, default `600/minute`).

Forwarders that forward local syslog to the HTTPS endpoint are in
`samples/forwarder/` (Vector recommended; rsyslog `omhttp` alternative).

## Prerequisites

- A GitHub account with this repository (branch `dev`).
- A [Render](https://render.com) account linked to GitHub.
- A [Vercel](https://vercel.com) account linked to GitHub.
- A Neon account and an Upstash account. The existing `neondb` database and
  Upstash Redis used during development can be reused.
- Python 3.13 and Node 20+ locally, to run migrations and seed users.

## 1. Neon PostgreSQL

1. Open the Neon console and select the project.
2. Click **Connect**.
3. Enable **Pooled connection**.
4. Copy the connection string. It looks like:

```
postgresql://neondb_owner:<password>@ep-xxxx-pooler.<region>.aws.neon.tech/neondb?sslmode=require&channel_binding=require
```

5. Change the scheme to `postgresql+asyncpg://`. Keep the rest:

```
postgresql+asyncpg://neondb_owner:<password>@ep-xxxx-pooler.<region>.aws.neon.tech/neondb?sslmode=require&channel_binding=require
```

The app removes `channel_binding` before handing the URL to `asyncpg` and turns
`sslmode=require` into an SSL context. Do not remove `sslmode=require`.

If you create a fresh Neon project instead of reusing the existing one, run the
migrations once from your laptop:

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL='postgresql+asyncpg://...'
alembic upgrade head
```

## 2. Upstash Redis

1. Open the Upstash console and select the Redis database.
2. Copy the **TLS** connection string. It starts with `rediss://`:

```
rediss://default:<password>@<name>.upstash.io:6379
```

`redis://` will not work with Upstash. Keep `rediss://`.

## 3. Generate application secrets

Render can generate the JWT secrets automatically from `render.yaml`. If you
prefer to set them yourself:

```bash
openssl rand -hex 32
openssl rand -hex 32
```

Choose an ingestion key. It must match the key used when seeding the database:

```bash
openssl rand -hex 24
```

## 4. Deploy the backend on Render

The repository contains `render.yaml` at the root. It defines one free Docker
web service named `nayyelin-logs-api` with the worker embedded in the web
process.

1. In Render, click **New → Blueprint**.
2. Connect the GitHub repository and select the `dev` branch.
3. Render reads `render.yaml` and asks for the values marked `sync: false`:

| Variable | Value |
|---|---|
| `DATABASE_URL` | Neon `postgresql+asyncpg://...` string from step 1 |
| `REDIS_URL` | Upstash `rediss://...` string from step 2 |
| `INGEST_API_KEY` | A key that matches the database tenant (see step 6) |
| `EMAIL_PROVIDER` | `resend` |
| `EMAIL_ENABLED` | `true` (only after Resend sender domain is verified) |
| `RESEND_API_KEY` | From the Resend dashboard (API Keys) |
| `ALERT_EMAIL_FROM` | Verified sender address, e.g. `alerts@yourdomain.com` |
| `ALERT_EMAIL_TO` | Administrator recipient address |
| `ALERT_WEBHOOK_URL` | Optional webhook receiver URL; leave unset to disable webhook alerts |

`ACCESS_TOKEN_SECRET` and `REFRESH_TOKEN_SECRET` are generated by Render.
`ALLOWED_HOSTS` already includes `*.onrender.com` and `*.vercel.app`.

### Resend email (Render)

Alert email is delivered through the Resend HTTPS API. Render blocks outbound
SMTP ports, so the backend logs a warning and skips SMTP whenever `RENDER` is
present; use `EMAIL_PROVIDER=resend` in production.

Before setting `EMAIL_ENABLED=true`:

1. Create a Resend account.
2. **Verify a sender.** In **Domains**, add your domain and publish the DNS
   records Resend shows (SPF/DKIM). For a quick test you can instead verify a
   single sender address under **API Keys → Sending access**.
3. Create an API key in the Resend dashboard and add it as `RESEND_API_KEY` in
   the Render environment (Render dashboard → Environment Variables).
4. Set `ALERT_EMAIL_FROM` to the verified address, e.g.
   `alerts@yourdomain.com`.
5. Set `ALERT_EMAIL_TO` to the administrator recipient.
6. Only then set `EMAIL_ENABLED=true`.

**Resend free-tier recipient limit:** until a domain is verified, Resend only
delivers to the email address that owns the Resend account. Sending to any
other recipient returns a provider rejection. Verify your domain to send to
arbitrary `ALERT_EMAIL_TO` addresses. The free tier also has a daily/monthly
message cap, so keep alert volume low.

The key is never committed to Git and is never exposed to the frontend or
logged. Webhook delivery continues to work independently of email.

Send a test notification after the service is live (admin session cookie
required). This uses the same production delivery path as alert emails:

```bash
curl -sS -X POST https://<project>.vercel.app/api/alerts/test-notification \
  -H 'Content-Type: application/json' \
  -b cookies.txt \
  -d '{"channel":"email","recipient":"admin@yourdomain.com"}'
```

Success returns `{"ok":true,"channel":"email","status":"sent",...}`. Clear
errors are returned for a disabled provider, missing `RESEND_API_KEY`, an
invalid recipient, or a provider rejection. To test a webhook:

```bash
curl -sS -X POST https://<project>.vercel.app/api/alerts/test-notification \
  -H 'Content-Type: application/json' \
  -b cookies.txt \
  -d '{"channel":"webhook","webhook_url":"https://example.com/hooks/logs"}'
```

`CORS_ORIGINS` defaults to `[]`, which is correct because the Vercel proxy is
same-origin. You only need to set it if browsers call the Render URL directly.

Run the key rotation in step 6 before you click **Apply**, so you have the
`INGEST_API_KEY` value to paste here. The value must match the database; a
mismatch only affects ingestion, not login.

4. Click **Apply**. The first build installs Python dependencies and usually
   takes several minutes.
5. Wait until the service shows **Live**. The health check is `/ready`, which
   verifies both PostgreSQL and Redis.
6. Copy the public URL. It is normally:

```
https://nayyelin-logs-api.onrender.com
```

If that name is already taken, Render will use a different URL. In that case
update two places:

- `frontend/vercel.json` → the `/api/:path*` rewrite destination
- the GitHub repository variable `SAAS_BACKEND_URL`

### Render settings used

| Setting | Value | Why |
|---|---|---|
| Plan | `free` | $0 |
| Runtime | Docker | Reuses `backend/Dockerfile` |
| Worker | embedded (`WORKER_EMBEDDED=true`) | Free plan has no background workers |
| Syslog | `SYSLOG_ENABLED=false` | No UDP/TCP on Render |
| DB pool | `DATABASE_POOL=null` | Safe with the Neon pooler |
| Health check | `/ready` | Verifies DB and Redis |
| Auto deploy | off | Deploys are triggered by CI after tests pass |

### Verify the backend

```bash
curl -s https://nayyelin-logs-api.onrender.com/healthz
curl -s https://nayyelin-logs-api.onrender.com/ready
curl -s https://nayyelin-logs-api.onrender.com/version
```

`/ready` must return `"status":"ready"`.

## 5. Deploy the frontend on Vercel

1. Before deploying, open `frontend/vercel.json` and confirm the rewrite points
   at your Render URL:

```json
{
  "source": "/api/:path*",
  "destination": "https://nayyelin-logs-api.onrender.com/api/:path*"
}
```

2. In Vercel, click **Add New → Project** and import the repository.
3. Set **Root Directory** to `frontend`.
4. Framework preset: **Vite**. Build command `npm run build`, output `dist`.
5. Add an environment variable for Production (and Preview if you want):

```
VITE_API_URL=/api
```

6. Click **Deploy**.
7. Open `https://<project>.vercel.app`. The SPA loads from Vercel and API calls
   go to `/api/*`, which Vercel proxies to Render.

### Verify the frontend proxy

Health routes live at the backend root, not under `/api`. Verify the proxy with
an authenticated API route instead:

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://<project>.vercel.app/api/get-logs
```

This must return `401`. If it returns `200` with HTML, the rewrite order or
destination is wrong and Vercel is serving the SPA instead of proxying.

## 6. Seed or repair the database

The database may already contain demo data. To create it on a fresh database:

```bash
cd backend
. .venv/bin/activate
export DATABASE_URL='postgresql+asyncpg://...'
export SAAS_MODE=true
export SEED_ADMIN_PASSWORD='<strong password>'
export SEED_VIEWER_A_PASSWORD='<strong password>'
export SEED_VIEWER_B_PASSWORD='<strong password>'
export INGEST_API_KEY='<same key as Render>'
python scripts/seed_demo_data.py
```

`SAAS_MODE=true` makes the seed script refuse to fall back to generated demo
passwords.

If the users already exist and you need a known password, set it directly:

Login uses the email address, for example `admin@demo.local`. The script accepts
either an email or a username:

```bash
cd backend
. .venv/bin/activate
export DATABASE_URL='postgresql+asyncpg://...'
python scripts/set_password.py admin@demo.local '<new password>'
```

or from the repository root:

```bash
DATABASE_URL='postgresql+asyncpg://...' make set-password IDENTIFIER=admin@demo.local PASSWORD='<new password>'
```

The existing demo accounts are `admin@demo.local`, `viewerA@demo.local`, and
`viewerB@demo.local`.

### Ingestion API key

If you reuse an existing database, its `demoa` tenant already has an API key
hash. The `INGEST_API_KEY` on Render must hash to that same value, or ingestion
returns `401 Invalid API key`. Either reuse the original key, or rotate the
stored hash to the key you want to use:

```bash
DATABASE_URL='postgresql+asyncpg://...' make set-api-key TENANT=demoa
```

Without `KEY`, the command prints a new random key. Store that value as
`INGEST_API_KEY` on Render and use it in the ingest requests below. If you pass
a key explicitly, use the same value on Render:

```bash
DATABASE_URL='postgresql+asyncpg://...' make set-api-key TENANT=demoa KEY='<your key>'
```

## 7. Send events

Use the Vercel URL so the request stays same-origin:

```bash
curl -X POST https://<project>.vercel.app/api/ingest \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: $INGEST_API_KEY" \
  -d '{"source":"firewall","event_type":"user_login","action":"ALLOW","src_ip":"203.0.113.42","severity":3}'
```

The old `/ingest` alias without `/api` also exists, but `/api/ingest` is the
documented path.

## 8. CI/CD

`.github/workflows/ci.yml` runs on every push to `dev` and on pull requests.
Repository checks, backend tests, and frontend checks run as parallel jobs. The
Docker build and smoke test only run when container, dependency, or CI files
change, and always on pull requests. A typical `dev` push gives feedback in
about 4 minutes.

Production deployment is release-gated. `.github/workflows/deploy-saas.yml`
runs when a GitHub release is published or when you start it manually:

1. Checks out the release tag, or the selected commit for a manual run.
2. Verifies the commit is still the head of `dev`.
3. Waits for the CI run for that commit to succeed.
4. Triggers the Render deploy hook and the Vercel build/deploy in parallel.
5. Polls `/version` until `git_sha` equals that commit (up to 15 minutes).
6. Runs `scripts/smoke_saas.sh` against the public URLs.

Release-please opens the release pull request. Merging it creates the GitHub
release and tag, which triggers this workflow. You can also run
**Actions → Deploy SaaS → Run workflow** from `dev` for an on-demand deploy.
Render's deploy hook deploys the service's configured branch, so the release
commit must still be the `dev` head. If `dev` has moved ahead, deploy the new
head manually or publish a new release.

If the Render or Vercel secrets are absent, those steps are skipped and the
workflow still passes. This keeps forks and pull requests safe.

### GitHub repository secrets

Add these under **Settings → Secrets and variables → Actions → Secrets**:

| Secret | Where to get it |
|---|---|
| `RENDER_DEPLOY_HOOK_URL` | Render service → Settings → Deploy Hook |
| `VERCEL_TOKEN` | Vercel → Account Settings → Tokens |
| `VERCEL_ORG_ID` | Vercel project → Settings → General → Team ID |
| `VERCEL_PROJECT_ID` | Vercel project → Settings → General → Project ID |
| `GIT_PUSH_PAT` | Optional. A PAT with `repo` scope for release-please. Falls back to `GITHUB_TOKEN` |

### GitHub repository variables

Add these under **Settings → Secrets and variables → Actions → Variables**:

| Variable | Value |
|---|---|
| `SAAS_BACKEND_URL` | `https://nayyelin-logs-api.onrender.com` |
| `SAAS_FRONTEND_URL` | `https://<project>.vercel.app` |

`SAAS_BACKEND_URL` has a built-in default that matches `render.yaml`. Set it
only if you renamed the Render service.

### Manual deploy

Render: open the service and click **Manual Deploy → Deploy latest commit**.

Vercel (run from the repository root; the project Root Directory is `frontend`):

```bash
npx vercel --prod
```

### Local validation before pushing

```bash
make saas-check
bash scripts/smoke_saas.sh https://nayyelin-logs-api.onrender.com https://<project>.vercel.app
```

## 9. Free-tier behaviour you must expect

- **Cold start:** Render sleeps after 15 minutes without traffic. The first
  request afterwards can take 30-60 seconds. Open the site once before a demo.
- **Worker pauses:** alerts and retention run inside the web process. They do
  not run while Render is asleep. This is acceptable for a demo.
- **Retention:** the embedded worker runs the purge once at startup and then
  every `RETENTION_INTERVAL_MINUTES` (default 60). Set
  `RETENTION_RUN_ON_STARTUP=false` to skip the startup pass. Because the free
  service sleeps, retention is best-effort; it catches up on the next wake.
- **Keep-warm pinger:** to keep alerts and retention running, have an external
  cron (for example cron-job.org or a GitHub Actions schedule) call the health
  endpoint every 10-14 minutes:
  ```bash
  curl -fsS https://nayyelin-logs-api.onrender.com/healthz >/dev/null
  ```
  Use `/healthz` rather than `/ready` to avoid spending Upstash commands.
- **Neon autosuspend:** the first query after idle can take a couple of seconds.
- **512 MB RAM:** do not deploy a separate worker service or add another process
  to the Render service. The current configuration is sized for the free plan.
- **No syslog:** use `POST /api/ingest`.
- **Upstash command budget:** the health check uses Redis. If the daily command
  limit is a concern, point the Render health check at `/healthz` instead of
  `/ready`.
- **Ephemeral disk:** no local file storage. Everything persistent lives in Neon.

## 10. Troubleshooting

### `400 Invalid host header`

`APP_ENV=production` enables `TrustedHostMiddleware`. Add the missing host to
`ALLOWED_HOSTS`. The default in `render.yaml` already allows `*.onrender.com`
and `*.vercel.app`.

### Login succeeds but the UI immediately returns to `/login`

- Access the app through the Vercel URL, not the Render URL directly.
- Keep `COOKIE_SECURE=true` and `COOKIE_SAME_SITE=lax` when using the proxy.
- Clear cookies for both domains and retry.

If you intentionally call Render directly from a different origin, set
`COOKIE_SAME_SITE=none` (requires HTTPS) and add the exact origin to
`CORS_ORIGINS`.

### `sslmode` / SSL errors from PostgreSQL

Use the Neon pooled connection string with `sslmode=require`, and change only
the scheme to `postgresql+asyncpg://`.

### `prepared statement ... does not exist`

This happens when a transaction-mode pooler is used with a client-side prepared
statement cache. Keep `DATABASE_POOL=null` on Render and use the Neon **pooled**
host (`...-pooler...`).

### Render reports unhealthy

Check the service logs. The usual causes are:

- `DATABASE_URL` or `REDIS_URL` missing or still containing a placeholder
- Upstash URL using `redis://` instead of `rediss://`
- Neon project suspended or password rotated
- The service exceeding 512 MB and being restarted

### Vercel returns 404 or HTML for `/api/*`

- `frontend/vercel.json` must list the `/api/:path*` rewrite before the SPA
  catch-all.
- The Render URL in that rewrite must match the real service URL.
- Redeploy after editing the file.

### Alembic fails during the first boot

Run migrations from your laptop against the same Neon database:

```bash
cd backend
. .venv/bin/activate
export DATABASE_URL='postgresql+asyncpg://...'
alembic upgrade head
```

Then redeploy the Render service.

## 11. Teardown

1. Render: suspend or delete the web service.
2. Vercel: delete the project.
3. Neon: delete the project or database if it is no longer shared.
4. Upstash: delete the Redis database.
5. GitHub: remove the deploy secrets and the deploy hook.

The Docker appliance remains available in `docker-compose.yml` and
`docs/setup_appliance.md`.
