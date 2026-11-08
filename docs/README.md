# Logs Manager — Documentation

This directory contains the reviewer-facing documentation for the Logs Manager
(Mini SIEM) project. All documents describe the current implementation and
match the running codebase.

## Documentation Index

| Document | Purpose |
|---|---|
| [`architecture.md`](architecture.md) | System architecture, components, data flow, ingestion pipeline, storage, worker, and tenant model |
| [`setup_appliance.md`](setup_appliance.md) | Local/on-prem installation and operation using Docker Compose |
| [`setup_saas.md`](setup_saas.md) | Zero-cost SaaS deployment on Render + Vercel + Neon + Upstash, including CI/CD |
| [`DEMO_GUIDE.md`](DEMO_GUIDE.md) | Practical 30-minute assignment demonstration walkthrough |
| [`API_CONTRACT.md`](API_CONTRACT.md) | Actual API endpoints, authentication, request/response formats, and examples |
| [`SECURITY_DESIGN.md`](SECURITY_DESIGN.md) | Authentication, RBAC, tenant isolation, and security controls |
| [`schema.md`](schema.md) | Normalized event schema, field descriptions, severity mapping, and schema diagram |

## Canonical Workflow

```bash
# 1. Start the stack (local appliance mode)
make up

# 2. Seed demo data
make seed

# 3. Run verification checks
make verify
```

## Verification Status

Automated checks (backend tests, frontend lint/typecheck/build, Compose config)
are verified against the current codebase. Runtime/SSL/end-to-end verification
requires a live Docker Compose stack and is not claimed as passed without a
manual run.

## Postman

The canonical Postman collection and environment are at the repository root:

- `postman/Logs-Manager.postman_collection.json`
- `postman/Logs-Manager.postman_environment.json`

All request paths have been cross-checked against the actual FastAPI routes.
