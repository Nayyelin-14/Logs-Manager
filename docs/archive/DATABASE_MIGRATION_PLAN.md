# Database Migration Plan — Prisma to SQLAlchemy + Alembic

**Version:** 1.0  
**Date:** 2026-11-03  
**Status:** Design Phase

---

## 1. Objective

Safely transition from Prisma ORM (legacy Node.js/TypeScript) to SQLAlchemy 2.x + Alembic (FastAPI/Python) while:

- **Preserving all existing data** in the PostgreSQL database
- **Maintaining exact schema compatibility** (table names, column names, types, indexes, constraints, enums)
- **Avoiding any destructive operations** (no DROP TABLE, no TRUNCATE, no column type changes that lose data)
- **Enabling future migrations** via Alembic for schema evolution

---

## 2. Existing Database Schema Analysis

### 2.1 Tables (from Prisma schema)

| Prisma Model | Table Name | Primary Key | Key Columns |
|--------------|------------|-------------|-------------|
| `User` | `"User"` | `id` (serial) | `username`, `email` (unique), `password`, `role`, `tenant`, `status`, `createAt`, `updatedAt` |
| `AlertRule` | `"alert_rules"` | `id` (cuid) | `name`, `tenant`, `conditions` (JSONB), `enabled`, `severity` |
| `Alert` | `"alerts"` | `id` (cuid) | `rule_id`, `tenant`, `description`, `triggered_at`, `event_ids` (text[]), `severity`, `status`, `title`, `dedupe_key` |
| `Otp` | `"Otp"` | `id` (serial) | `email` (unique), `opt_code`, `remember_token`, `verify_token`, `count`, `error` |
| `SecurityEvent` | `"security_logs"` | `id` (cuid) | `timestamp` (`@timestamp`), `tenant`, `source`, `vendor`, `product`, `event_type`, `canonical_event_type`, `original_event_type`, `event_subtype`, `severity`, `action`, `src_ip`, `src_port`, `dst_ip`, `dst_port`, `protocol`, `user`, `host`, `process`, `url`, `http_method`, `status_code`, `rule_name`, `rule_id`, `cloud_account_id`, `cloud_region`, `cloud_service`, `raw` (JSONB), `tags` (text[]), `created_at`, `updated_at`, `ip`, `description`, `event_id`, `login_type`, `priority`, `sha256`, `status`, `interface`, `mac` |

### 2.2 Enums (stored as TEXT with CHECK constraints or native enums)

| Enum | Values | Prisma Mapping |
|------|--------|----------------|
| `Role` | `VIEWER`, `ADMIN` | `Role` enum |
| `Status` | `FREEZE`, `INACTIVE`, `ACTIVE` | `Status` enum |
| `Action` | `ALLOW`, `DENY`, `CREATE`, `DELETE`, `LOGIN`, `LOGOUT`, `ALERT`, `QUARANTINE`, `CREATEUSER` | `Action` enum |
| `Source` | `FIREWALL`, `CROWDSTRIKE`, `AWS`, `M365`, `AD`, `API`, `NETWORK` | `Source` enum |

**Note**: Prisma creates native PostgreSQL enums for these. SQLAlchemy must use `Enum` with `native_enum=True` and matching names.

### 2.3 Indexes (Critical for Performance)

SecurityEvent has 15+ indexes including:
- Single column: `timestamp`, `event_type`, `canonical_event_type`, `severity`, `src_ip`, `ip`, `user`, `event_id`, `login_type`, `priority`, `sha256`, `status`, `interface`, `mac`
- Composite: `(tenant, timestamp)`, `(source, timestamp)`, `(tenant, user)`, `(tenant, src_ip)`, `(tenant, created_at DESC)`, `(tenant, source, created_at DESC)`, `(tenant, action, created_at DESC)`, `(tenant, event_type, created_at DESC)`, `(tenant, canonical_event_type, created_at DESC)`
- Alert: `(tenant, status)`, `(rule_id, dedupe_key, triggered_at)`
- User: `(tenant)`, `(role)`, `(create_at)`, `(status)`
- Otp: `(email)` unique

---

## 3. SQLAlchemy Model Design

### 3.1 Naming Conventions

- **Table names**: Match Prisma exactly. Use SQLAlchemy's `__tablename__` with the actual identifier (e.g., `"User"`, `"Otp"`, `alert_rules`, `alerts`, `security_logs`). SQLAlchemy will quote case-sensitive identifiers automatically when generating DDL.
- **Column names**: Match Prisma `@map` or snake_case: `@timestamp` → `timestamp`, `event_type`, `canonical_event_type`, `src_ip`, etc.
- **Enum names**: Use Prisma enum names: `Role`, `Status`, `Action`, `Source`
- **Primary keys**: `id` with appropriate type (Integer for serial, String for cuid)

### 3.2 Base Model Configuration

```python
# app/models/base.py
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import MetaData

# Match Prisma's naming convention for constraints
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
```

### 3.3 Enum Definitions

```python
# app/models/enums.py
import enum
from sqlalchemy import Enum

class Role(str, enum.Enum):
    VIEWER = "VIEWER"
    ADMIN = "ADMIN"

class Status(str, enum.Enum):
    FREEZE = "FREEZE"
    INACTIVE = "INACTIVE"
    ACTIVE = "ACTIVE"

class Action(str, enum.Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    CREATE = "CREATE"
    DELETE = "DELETE"
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    ALERT = "ALERT"
    QUARANTINE = "QUARANTINE"
    CREATEUSER = "CREATEUSER"

class Source(str, enum.Enum):
    FIREWALL = "FIREWALL"
    CROWDSTRIKE = "CROWDSTRIKE"
    AWS = "AWS"
    M365 = "M365"
    AD = "AD"
    API = "API"
    NETWORK = "NETWORK"
```

### 3.4 Model Definitions (Key Examples)

```python
# app/models/user.py
from sqlalchemy import Column, Integer, String, DateTime, Enum as SQLEnum, Index
from sqlalchemy.orm import relationship
from app.models.base import Base
from app.models.enums import Role, Status

class User(Base):
    __tablename__ = "User"  # Case-sensitive; SQLAlchemy quotes automatically
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), nullable=True)
    email = Column(String(255), unique=True, nullable=False)
    password = Column(String(255), nullable=True)  # bcrypt hash
    role = Column(SQLEnum(Role, name="Role", native_enum=True), default=Role.VIEWER, nullable=False)
    tenant = Column(String(100), nullable=True)
    status = Column(SQLEnum(Status, name="Status", native_enum=True), default=Status.ACTIVE, nullable=False)
    create_at = Column(DateTime(timezone=True), server_default="now()", nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default="now()", onupdate="now()", nullable=False)
    
    # Indexes
    __table_args__ = (
        Index('ix_User_tenant', 'tenant'),
        Index('ix_User_role', 'role'),
        Index('ix_User_create_at', 'create_at'),
        Index('ix_User_status', 'status'),
    )
```

```python
# app/models/security_event.py
from sqlalchemy import Column, String, Integer, DateTime, Enum as SQLEnum, JSON, ARRAY, Text, Index, BigInteger
from sqlalchemy.dialects.postgresql import JSONB
from app.models.base import Base
from app.models.enums import Source, Action

class SecurityEvent(Base):
    __tablename__ = "security_logs"
    
    id = Column(String(25), primary_key=True)  # cuid
    timestamp = Column(DateTime(timezone=True), server_default="now()", nullable=False)  # @timestamp
    tenant = Column(String(100), nullable=False)
    source = Column(SQLEnum(Source, name="Source", native_enum=True), nullable=False)
    vendor = Column(String(100), nullable=True)
    product = Column(String(100), nullable=True)
    event_type = Column(String(200), nullable=False)
    canonical_event_type = Column(String(200), nullable=True)
    original_event_type = Column(String(200), nullable=True)
    event_subtype = Column(String(200), nullable=True)
    severity = Column(Integer, default=0, nullable=False)
    action = Column(SQLEnum(Action, name="Action", native_enum=True), nullable=True)
    src_ip = Column(String(45), nullable=True)  # IPv6 max length
    src_port = Column(String(10), nullable=True)
    dst_ip = Column(String(45), nullable=True)
    dst_port = Column(String(10), nullable=True)
    protocol = Column(String(20), nullable=True)
    user = Column(String(255), nullable=True)
    host = Column(String(255), nullable=True)
    process = Column(String(255), nullable=True)
    url = Column(Text, nullable=True)
    http_method = Column(String(10), nullable=True)
    status_code = Column(Integer, nullable=True)
    rule_name = Column(String(255), nullable=True)
    rule_id = Column(String(255), nullable=True)
    cloud_account_id = Column(String(100), nullable=True)
    cloud_region = Column(String(100), nullable=True)
    cloud_service = Column(String(100), nullable=True)
    raw = Column(JSONB, nullable=False)
    tags = Column(ARRAY(String), default=[], nullable=False)
    created_at = Column(DateTime(timezone=True), server_default="now()", nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default="now()", onupdate="now()", nullable=False)
    ip = Column(String(45), nullable=True)
    description = Column(Text, nullable=True)
    event_id = Column(Integer, nullable=True)
    login_type = Column(Integer, nullable=True)
    priority = Column(Integer, nullable=True)
    sha256 = Column(String(64), nullable=True)
    status = Column(String(50), nullable=True)
    interface = Column(String(100), nullable=True)
    mac = Column(String(17), nullable=True)  # MAC address format
    
    # Indexes (matching Prisma exactly)
    __table_args__ = (
        Index('ix_security_logs_timestamp', 'timestamp'),
        Index('ix_security_logs_tenant_timestamp', 'tenant', 'timestamp'),
        Index('ix_security_logs_source_timestamp', 'source', 'timestamp'),
        Index('ix_security_logs_event_type', 'event_type'),
        Index('ix_security_logs_canonical_event_type', 'canonical_event_type'),
        Index('ix_security_logs_severity', 'severity'),
        Index('ix_security_logs_tenant_user', 'tenant', 'user'),
        Index('ix_security_logs_tenant_src_ip', 'tenant', 'src_ip'),
        Index('ix_security_logs_src_ip', 'src_ip'),
        Index('ix_security_logs_tenant_created_at_desc', 'tenant', 'created_at', postgresql_using='btree', postgresql_ops={'created_at': 'DESC'}),
        Index('ix_security_logs_tenant_source_created_at_desc', 'tenant', 'source', 'created_at', postgresql_using='btree', postgresql_ops={'created_at': 'DESC'}),
        Index('ix_security_logs_tenant_action_created_at_desc', 'tenant', 'action', 'created_at', postgresql_using='btree', postgresql_ops={'created_at': 'DESC'}),
        Index('ix_security_logs_tenant_event_type_created_at_desc', 'tenant', 'event_type', 'created_at', postgresql_using='btree', postgresql_ops={'created_at': 'DESC'}),
        Index('ix_security_logs_tenant_canonical_event_type_created_at_desc', 'tenant', 'canonical_event_type', 'created_at', postgresql_using='btree', postgresql_ops={'created_at': 'DESC'}),
    )
```

---

## 4. Alembic Migration Strategy

### 4.1 The Core Challenge

Alembic's `autogenerate` compares **SQLAlchemy models** against the **actual database**. Since the database already has all tables from Prisma, the first migration must be a **baseline** (empty migration that marks current state as "applied").

### 4.2 Step-by-Step Process

#### Step 1: Inspect Existing Database

```bash
# In backend directory
# 1. Start with a clean Python environment
python -m venv .venv && source .venv/bin/activate
pip install sqlalchemy alembic asyncpg psycopg2-binary python-dotenv

# 2. Create initial SQLAlchemy models matching Prisma schema exactly
# (Write app/models/*.py as designed above)

# 3. Configure alembic.ini and env.py for async
```

#### Step 2: Configure Alembic for Async

```python
# migrations/env.py
import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

from app.models.base import Base
from app.core.config import settings

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_offline():
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection: Connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online():
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

#### Step 3: Create Baseline Migration

```bash
# Generate baseline migration (should be empty if models match exactly)
alembic revision --autogenerate -m "baseline_from_prisma"

# Inspect the generated migration file - it should have NO op.create_table, NO op.add_column
# If it shows changes, DO NOT APPLY. Fix models until autogenerate produces empty upgrade().
```

#### Step 4: Stamp Baseline

```bash
# Mark database as at baseline revision without running any SQL
alembic stamp head
```

#### Step 5: Verify Schema Match

```bash
# Compare models vs database again - should show no changes
alembic revision --autogenerate -m "verify_no_changes"

# The generated file should be empty (pass in upgrade/downgrade)
```

#### Step 6: Add `ingested_at` Column (First Real Migration)

```bash
# After baseline is confirmed, create the ingested_at migration
alembic revision -m "add_ingested_at_to_security_logs"
```

Edit the generated file with a **safe multi-step migration**:

```python
# migrations/versions/xxxx_add_ingested_at_to_security_logs.py
from alembic import op
import sqlalchemy as sa
from datetime import datetime, timezone

def upgrade():
    # Step 1: Add column as nullable, NO default
    op.add_column(
        "security_logs",
        sa.Column(
            'ingested_at',
            sa.DateTime(timezone=True),
            nullable=True
        )
    )
    
    # Step 2: Backfill existing records using created_at (the actual ingestion time)
    # For rows where created_at is also missing (shouldn't happen), use migration-time fallback
    migration_time = datetime.now(timezone.utc)
    op.execute(f"""
        UPDATE "security_logs"
        SET ingested_at = COALESCE(created_at, '{migration_time.isoformat()}')
        WHERE ingested_at IS NULL
    """)
    
    # Step 3: Verify no NULLs remain
    # (In production, you might want to check this before proceeding)
    # result = op.get_bind().execute(sa.text('SELECT count(*) FROM "security_logs" WHERE ingested_at IS NULL'))
    # assert result.scalar() == 0
    
    # Step 4: Add DEFAULT now() for future inserts
    op.alter_column(
        "security_logs",
        "ingested_at",
        server_default=sa.text("now()"),
        nullable=False
    )
    
    # Step 5: Create index for retention queries
    op.create_index(
        'ix_security_logs_ingested_at',
        "security_logs",
        ['ingested_at']
    )

def downgrade():
    op.drop_index('ix_security_logs_ingested_at', table_name="security_logs")
    op.drop_column("security_logs", "ingested_at")
```

**Key differences from the incorrect approach:**
- Column added **nullable first** without server default → existing rows get NULL
- Backfill uses **`created_at`** (actual ingestion time), NOT the original event `timestamp`
- Migration-time fallback for any edge cases without `created_at`
- `ALTER COLUMN` adds default and NOT NULL **after** backfill
- Table name passed without embedded quotes (SQLAlchemy handles quoting)

#### Step 7: Apply and Test

```bash
alembic upgrade head
# Verify: SELECT column_name FROM information_schema.columns WHERE table_name = 'security_logs' AND column_name = 'ingested_at';
```

---

## 5. Backfill Strategy for `ingested_at`

### 5.1 Logic

| Scenario | `ingested_at` Value |
|----------|---------------------|
| Existing records with `created_at` | `created_at` (actual ingestion timestamp) |
| Existing records without `created_at` (edge case) | Migration execution timestamp (conservative fallback) |
| New records (after migration) | `now()` (server default) |

### 5.2 Why This Is Safe

- **Original `timestamp` preserved**: The event's original timestamp (`@timestamp`) is never modified or used for retention
- **Retention uses `ingested_at`**: New retention job deletes where `ingested_at < 7 days ago`
- **Sample data unaffected**: Old sample events have `ingested_at = created_at` (when seeded), so they expire 7 days after seeding, not immediately
- **New ingestions**: Get `ingested_at = now()`, correctly subject to 7-day retention from ingestion time
- **No data loss risk**: Migration adds column nullable, backfills, then constrains

### 5.3 Verification Queries

```sql
-- Check backfill
SELECT 
    count(*) as total,
    count(ingested_at) as with_ingested_at,
    min(ingested_at) as min_ingested,
    max(ingested_at) as max_ingested
FROM "security_logs";

-- Verify sample data expires correctly (7 days after created_at, not immediately)
SELECT count(*) FROM "security_logs" 
WHERE ingested_at < now() - interval '7 days';
-- Should be 0 for recently seeded data
```

---

## 6. Rollback Strategy

### 6.1 Pre-Migration Backup

```bash
# Always backup before any migration
pg_dump -h <host> -U <user> -d <db> -Fc -f backup_$(date +%Y%m%d_%H%M%S).dump
```

### 6.2 Alembic Rollback

```bash
# Rollback last migration
alembic downgrade -1

# Rollback to specific revision
alembic downgrade <revision_id>

# Full rollback to baseline
alembic downgrade base
```

### 6.3 Emergency Restore

```bash
# If something goes wrong
pg_restore -h <host> -U <user> -d <db> -c backup_YYYYMMDD_HHMMSS.dump
```

---

## 7. Testing Migration Safety

### 7.1 Test Environment

- **Separate test database** (not production Neon)
- Use `docker-compose -f docker-compose.test.yml` with isolated PostgreSQL
- Seed with production-like data (anonymized or subset)

### 7.2 Test Steps

1. **Restore production backup to test DB**
2. **Run baseline migration** → verify `alembic current` shows baseline
3. **Run `ingested_at` migration** → verify column exists, backfilled
4. **Run application integration tests** against migrated schema
5. **Verify retention job** uses `ingested_at` correctly
6. **Rollback `ingested_at` migration** → verify column removed
7. **Rollback to baseline** → verify schema matches original

### 7.3 Automated Migration Test (CI)

```python
# tests/test_migrations.py
import pytest
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine, inspect, text

def test_baseline_migration_empty(alembic_config, test_db_url):
    """Baseline migration should produce no SQL changes."""
    # This test runs after models are written but before baseline stamp
    # Generate migration in temp dir, inspect upgrade() ops
    pass

def test_ingested_at_migration(alembic_config, test_db_url):
    """Test ingested_at add + backfill + index (multi-step migration)."""
    # Apply baseline
    command.stamp(alembic_config, "head")
    
    # Apply ingested_at migration
    command.upgrade(alembic_config, "head")
    
    # Verify
    engine = create_engine(test_db_url)
    insp = inspect(engine)
    cols = {c['name'] for c in insp.get_columns('security_logs', schema='public')}
    assert 'ingested_at' in cols
    
    indexes = {i['name'] for i in insp.get_indexes('security_logs', schema='public')}
    assert 'ix_security_logs_ingested_at' in indexes
    
    # Verify backfill: no NULLs, all rows have ingested_at = created_at (or migration time)
    with engine.connect() as conn:
        result = conn.execute(text('SELECT count(*) FROM "security_logs" WHERE ingested_at IS NULL'))
        assert result.scalar() == 0
        
        # Verify backfill used created_at
        result = conn.execute(text('''
            SELECT count(*) FROM "security_logs" 
            WHERE ingested_at = created_at
        '''))
        assert result.scalar() > 0  # At least some rows matched
    
    # Rollback
    command.downgrade(alembic_config, "-1")
    cols = {c['name'] for c in insp.get_columns('security_logs', schema='public')}
    assert 'ingested_at' not in cols
```

---

## 8. Ongoing Migration Workflow

### 8.1 For Future Schema Changes

1. Modify SQLAlchemy models in `app/models/`
2. Generate migration: `alembic revision --autogenerate -m "description"`
3. **Review generated SQL carefully** — never trust autogenerate blindly
4. Test on test database
5. Apply to production: `alembic upgrade head`

### 8.2 Forbidden Patterns

| Pattern | Reason |
|---------|--------|
| `op.drop_table()` | Data loss |
| `op.drop_column()` without data migration | Data loss |
| `op.alter_column(..., type_=...)` changing type | Potential data truncation |
| Renaming tables/columns without `op.rename_table()` / `op.alter_column(..., new_column_name=...)` | Breaks existing queries |

### 8.3 Required Reviews

Every migration must be reviewed for:
- [ ] No destructive operations
- [ ] Backfill strategy for new NOT NULL columns
- [ ] Indexes added for new query patterns
- [ ] Enum changes use `postgresql_using` for safe casting
- [ ] Downgrade path works

---

## 9. Enum Handling Details

### 9.1 Prisma Creates Native Enums

Prisma creates PostgreSQL enum types: `"Role"`, `"Status"`, `"Action"`, `"Source"`.

### 9.2 SQLAlchemy Must Use Same Enums

```python
# In model definition
role = Column(
    SQLEnum(Role, name="Role", native_enum=True, create_constraint=True),
    default=Role.VIEWER,
    nullable=False
)
```

### 9.3 Adding Enum Values Later

```python
# Migration to add new enum value
def upgrade():
    # PostgreSQL: ALTER TYPE "Role" ADD VALUE 'NEW_VALUE'
    op.execute('ALTER TYPE "Role" ADD VALUE \'NEW_VALUE\'')

def downgrade():
    # Cannot easily remove enum values in PostgreSQL
    # Must rename type, create new, migrate data, drop old
    pass
```

---

## 10. JSONB and Array Columns

### 10.1 `raw` (JSONB)

```python
raw = Column(JSONB, nullable=False)
```

- Prisma stores as `jsonb`
- SQLAlchemy `JSONB` from `sqlalchemy.dialects.postgresql`
- Queries: `SecurityEvent.raw['key'].astext` for text extraction

### 10.2 `tags` and `event_ids` (TEXT[])

```python
tags = Column(ARRAY(String), default=[], nullable=False)
# Alert model
event_ids = Column(ARRAY(String), nullable=False)
```

- Prisma: `String[]` → PostgreSQL `text[]`
- SQLAlchemy: `ARRAY(String)`

---

## 11. CUID Primary Keys

### 11.1 Current State

`AlertRule.id`, `Alert.id`, `SecurityEvent.id` use Prisma's `cuid()` (25-char string).

### 11.2 SQLAlchemy Handling

```python
id = Column(String(25), primary_key=True)
```

- No auto-generation in DB (application generates)
- Or use Python `cuid2` library in service layer
- **Do not change** existing IDs or generation strategy

---

## 12. Summary Checklist

### Pre-Migration
- [ ] Full production database backup
- [ ] SQLAlchemy models written matching Prisma exactly
- [ ] Alembic configured for async
- [ ] Test database provisioned

### Baseline
- [ ] `alembic revision --autogenerate` produces empty migration
- [ ] `alembic stamp head` succeeds
- [ ] `alembic current` shows baseline revision

### ingested_at Migration
- [ ] Migration adds column as nullable, no default
- [ ] Backfill uses `created_at` (actual ingestion time), migration-time fallback for edge cases
- [ ] Column then altered to add DEFAULT now() and NOT NULL
- [ ] Index created for retention queries
- [ ] Migration applies cleanly on test DB
- [ ] Rollback works
- [ ] Application works with new column

### Post-Migration
- [ ] Retention job updated to use `ingested_at`
- [ ] All integration tests pass
- [ ] Performance benchmarks (index usage)
- [ ] Documentation updated

---

**End of Database Migration Plan**