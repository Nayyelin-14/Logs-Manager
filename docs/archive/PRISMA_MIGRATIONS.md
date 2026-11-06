# Prisma Migration History (Express Era) — Archived

> **Status: historical reference only.** The Express/Prisma backend has been
> removed. The active database schema is owned by **SQLAlchemy + Alembic**
> (`backend-fastapi/migrations/versions/`, head `a1b2c3d4e5f6_fresh_baseline`).
> These Prisma migrations are documented here so the schema evolution is not
> lost. **None of them are applied or executed anymore** — do not run
> `prisma migrate`.

## Models defined in `schema.prisma`

`User`, `AlertRule`, `Alert`, `Otp`, `SecurityEvent`

## Migrations (in order)

| Migration | Date | Change |
|---|---|---|
| `20250928125113_` | 2025-09-28 | Initial schema: enums `Role` (USER/ADMIN), `Status`, `Action`, `Source` (FIREWALL/CROWDSTRIKE/AWS/M365/AD/API/NETWORK); tables `User`, `AlertRule`, `Alert`, `Otp`, `SecurityEvent` |
| `20250929123158_` | 2025-09-29 | `alert_rules`: dropped `enabled` column |
| `20250929142802_` | 2025-09-29 | `alert_rules`: replaced `condition`/`threshold`/`windowSeconds` with `conditions`; `alerts`: added required `severity` |
| `20250930122949_` | 2025-09-30 | `alert_rules`: dropped `actions` and `enabled` columns |
| `20261102090000_restore_rule_enabled` | 2026-11-02 | `alert_rules`: re-added `enabled BOOLEAN NOT NULL DEFAULT true` |
| `20261103000000_alert_dedupe_key` | 2026-11-03 | `alerts`: added `dedupe_key` + index for rule/window deduplication |
| `20261103132803_add_severity_to_alert_rule` | 2026-11-03 | `alert_rules`: added `severity TEXT NOT NULL DEFAULT 'medium'` |
| `20261103152051_add_canonical_event_fields` | 2026-11-03 | `security_logs`: added `canonical_event_type`, `original_event_type` + indexes |
| `20261103153000_make_alert_rule_severity_nullable` | 2026-11-03 | `alert_rules.severity`: dropped default and NOT NULL (unset vs explicit `'medium'`) |

## Relationship to Alembic

- FastAPI was bootstrapped with an Alembic **baseline** (`a1b2c3d4e5f6_fresh_baseline`)
  that reproduces the schema as it stood after the Prisma migrations above.
- The Prisma migrations above were never executed by the FastAPI stack.
- The 4 newest Prisma migrations (`20261103*`) were written on 2026-11-03 while
  the Express backend was still present; their effects are represented in the
  Alembic-managed schema and in `app/models/`.
