# LMS Completion Status

Updated after the deployment, alerting, tenant-scope, seed, and test pass.

## Done

### Deployment and operations
- [x] Removed obsolete Express backend (`backend/`), root `docker-compose.yml`,
      and `render.yaml` — FastAPI-only tree
- [x] `backend-fastapi/Dockerfile` + canonical compose (Postgres, Redis, API, UI, syslog 5514/udp+tcp)
- [x] `frontend/lms/Dockerfile` + `nginx.conf` (`/api` reverse proxy, SPA fallback)
- [x] Health checks, `depends_on`, persistent volumes
- [x] `Makefile` and `run.sh`
- [x] `docs/setup_appliance.md`
- [x] `frontend/lms/vercel.json`
- [x] Corrected `docs/setup_saas.md` (Vercel root `frontend/lms`, Render root
      `backend`, env names, TLS, no stale demo URLs)
- [x] `/healthz` endpoint
- [x] Env-configurable rate limiting enabled for `/api`
- [x] Cookie flags configurable for HTTP appliance vs HTTPS SaaS
- [x] Daily 7-day retention cron

### Ingestion, storage, alerts
- [x] Syslog UDP/TCP, HTTP single, HTTP batch (JSON/JSONL/CSV)
- [x] API-key ingestion bound to a tenant
- [x] Normalization for firewall/syslog, network, API, AWS, CrowdStrike, M365, AD
- [x] Samples and sender scripts in `samples/`
- [x] Alert rules and Alerts page/endpoint
- [x] Alert grouping by source IP (fallback user/host)
- [x] Alert deduplication per rule/group/window
- [x] Alert severity derived from the event severity
- [x] Alert email fallback to tenant admins
- [x] Seeded repeated-failure rule and seeded alert

### Auth, tenant scope, data
- [x] Viewer can read every event in its own tenant (not only its own events)
- [x] Fixed dead `requireTenant` tenant check
- [x] Server-side `eventType` log filter
- [x] Seed uses relative timestamps, aligned tenants, demo users, logs, rule, alert
- [x] Seed clears alerts/rules/events/OTP/users in dependency order
- [x] Root `.gitignore` and `frontend/lms/.env.example`

### Tests and API client
- [x] Alert grouping/dedup/severity tests
- [x] Viewer tenant-scope tests
- [x] `tests/smoke.sh` end-to-end smoke test
- [x] `postman/Logs-Manager.postman_collection.json` + environment

## Remaining (not code-blocking)

- [ ] Deploy the SaaS stack with real Vercel/Render/Neon/Redis credentials and
      fill the placeholder URLs in `docs/setup_saas.md`.
- [ ] Record the 30-minute demo video (`docs/demo_script.md` still to write).
- [ ] Build and test the Docker images on the target host (`./run.sh`).
- [ ] Optional: full-text/trigram search indexes.
- [ ] Optional: `from`/`to` time-range log filters.
- [ ] Optional: GitHub Actions CI.
- [ ] Optional: IaC/Helm/Terraform and an OVA image.
- [ ] Optional: frontend component tests (Vitest + Testing Library).
