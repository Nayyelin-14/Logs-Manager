"""add tenants

Revision ID: 60bf177ba117
Revises: a1b2c3d4e5f6
Create Date: 2026-11-05 12:09:15.589618

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text
import hashlib
import secrets


# revision identifiers, used by Alembic.
revision: str = '60bf177ba117'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: add tenants table, backfill one row per distinct tenant."""
    # 1. Create tenants table
    op.create_table(
        'tenants',
        sa.Column('id', sa.String(length=25), primary_key=True),
        sa.Column('name', sa.String(length=50), nullable=False, unique=True),
        sa.Column('api_key_hash', sa.String(length=64), nullable=False, unique=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('now()'),
        ),
        sa.Column('alert_webhook_url', sa.String(length=500), nullable=True),
        sa.Column('alert_emails', postgresql.ARRAY(sa.String()), nullable=True),
        sa.CheckConstraint(
            "name ~ '^[a-z0-9_-]{2,50}$' AND name <> 'all'",
            name='ck_tenants_name_valid',
        ),
    )

    # 2. Collect distinct non-null tenants from existing tables
    conn = op.get_bind()
    tenant_set = set()

    for table in ['User', 'security_logs', 'alerts', 'alert_rules']:
        try:
            result = conn.execute(
                text(
                    f'SELECT DISTINCT tenant FROM {table} '
                    f'WHERE tenant IS NOT NULL AND tenant <> \'\''
                )
            )
            for row in result:
                tenant_set.add(row[0])
        except Exception:
            # Table might not exist yet in some environments; skip
            pass

    # 3. Normalize: lowercase + strip; report any changed values
    changed_values = []
    normalized_names = set()
    for raw_name in sorted(tenant_set):
        normalized = raw_name.strip().lower()
        if normalized != raw_name:
            changed_values.append((raw_name, normalized))
            print(f"Normalizing tenant name: {raw_name!r} -> {normalized!r}")
        normalized_names.add(normalized)

    # 4. UPDATE source tables to use normalized names
    for raw_name, normalized in changed_values:
        for table in ['User', 'security_logs', 'alerts', 'alert_rules']:
            try:
                conn.execute(
                    text(
                        f"UPDATE {table} SET tenant = :normalized WHERE tenant = :raw"
                    ),
                    {'normalized': normalized, 'raw': raw_name},
                )
            except Exception:
                pass

    # 5. Insert one row per distinct normalized tenant with random unusable hash
    for normalized_name in sorted(normalized_names):
        random_key = secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(random_key.encode()).hexdigest()
        tenant_id = hashlib.sha256(normalized_name.encode()).hexdigest()[:25]

        conn.execute(
            text(
                "INSERT INTO tenants (id, name, api_key_hash, is_active, created_at) "
                "VALUES (:id, :name, :api_key_hash, :is_active, now()) "
                "ON CONFLICT (name) DO NOTHING"
            ),
            {
                'id': tenant_id,
                'name': normalized_name,
                'api_key_hash': key_hash,
                'is_active': True,
            },
        )


def downgrade() -> None:
    """Downgrade schema: drop tenants table."""
    op.drop_table('tenants')
