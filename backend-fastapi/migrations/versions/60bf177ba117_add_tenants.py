"""add tenants table and normalize tenant field

Revision ID: 60bf177ba117
Revises: a1b2c3d4e5f6
Create Date: 2026-11-05 13:58:00

This migration:
1. Creates the tenants table for API key-based tenant isolation
2. Adds CHECK constraint for lowercase tenant names
3. Normalizes existing tenant values to lowercase
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text


revision: str = '60bf177ba117'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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
    op.create_index('ix_tenants_api_key_hash', 'tenants', ['api_key_hash'], unique=True)

    # Normalize existing tenant values to lowercase (needed before adding constraint)
    op.execute(text("UPDATE \"User\" SET tenant = lower(trim(tenant)) WHERE tenant IS NOT NULL"))
    op.execute(text("UPDATE security_logs SET tenant = lower(trim(tenant)) WHERE tenant IS NOT NULL"))
    op.execute(text("UPDATE alerts SET tenant = lower(trim(tenant)) WHERE tenant IS NOT NULL"))
    op.execute(text("UPDATE alert_rules SET tenant = lower(trim(tenant)) WHERE tenant IS NOT NULL"))


def downgrade() -> None:
    op.drop_index('ix_tenants_api_key_hash', table_name='tenants')
    op.drop_table('tenants')

    # Restore original case (best-effort: can't restore original case, just remove lowercase)
    op.execute(text("UPDATE \"User\" SET tenant = trim(tenant) WHERE tenant IS NOT NULL"))
    op.execute(text("UPDATE security_logs SET tenant = trim(tenant) WHERE tenant IS NOT NULL"))
    op.execute(text("UPDATE alerts SET tenant = trim(tenant) WHERE tenant IS NOT NULL"))
    op.execute(text("UPDATE alert_rules SET tenant = trim(tenant) WHERE tenant IS NOT NULL"))