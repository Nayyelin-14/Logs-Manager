"""Alerting schema: first-class alert_rules + alerts columns

Revision ID: a7b8c9d0e1f2
Revises: e1f2g3h4i5j6
Create Date: 2026-11-06

Adds first-class columns to alert_rules (rule_type, filter, group_by, threshold,
window_minutes, cooldown_minutes, notify) and to alerts (group_value,
evidence_event_ids, notifications).

The dedupe_key column and its active index already exist from the base migration
(a1b2c3d4e5f6), so they are NOT added here.

Migrates existing `conditions` JSON into the new structured columns without
data loss.

Downgrade: drops the new columns, restoring conditions as the single source of
truth.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, Sequence[str], None] = 'e1f2g3h4i5j6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- alert_rules: add first-class columns ----
    op.add_column('alert_rules',
        sa.Column('rule_type', sa.String(length=32), nullable=True,
                  server_default='threshold'))
    op.add_column('alert_rules',
        sa.Column('filter', postgresql.JSONB(astext_type=sa.Text()),
                  nullable=True, server_default=sa.text("'{}'::jsonb")))
    op.add_column('alert_rules',
        sa.Column('group_by', sa.String(length=32), nullable=True,
                  server_default="'src_ip'"))
    op.add_column('alert_rules',
        sa.Column('threshold', sa.Integer(), nullable=True,
                  server_default='5'))
    op.add_column('alert_rules',
        sa.Column('window_minutes', sa.Integer(), nullable=True,
                  server_default='5'))
    op.add_column('alert_rules',
        sa.Column('cooldown_minutes', sa.Integer(), nullable=True,
                  server_default='15'))
    op.add_column('alert_rules',
        sa.Column('notify', postgresql.JSONB(astext_type=sa.Text()),
                  nullable=True, server_default=sa.text("'{}'::jsonb")))

    # Migrate existing conditions -> structured columns (best effort, no data loss)
    op.execute("""
        UPDATE alert_rules
        SET filter = CASE
            WHEN conditions->>'type' = 'event_type'
                THEN jsonb_build_object('event_type', conditions->>'value')
            WHEN conditions->>'type' = 'severity_min'
                THEN jsonb_build_object('severity_gte', conditions->>'value')
            WHEN conditions->>'type' = 'threshold_count'
                THEN jsonb_build_object('event_type', conditions->>'value')
            WHEN conditions->>'type' = 'field_value'
                THEN jsonb_build_object(conditions->>'field', conditions->>'value')
            WHEN conditions->>'type' = 'repeated_failures'
                THEN jsonb_build_object(
                    'outcome', 'failure',
                    'action', 'login',
                    'source', conditions->>'source'
                )
            ELSE COALESCE(conditions->'filter', '{}'::jsonb)
        END,
        group_by = COALESCE(conditions->>'groupBy', conditions->>'group_by', 'src_ip'),
        threshold = COALESCE((conditions->>'threshold')::int, 5),
        window_minutes = COALESCE((conditions->>'windowSeconds')::int, 300) / 60,
        cooldown_minutes = COALESCE((conditions->>'cooldownSeconds')::int, 900) / 60,
        notify = COALESCE(conditions->'notify', '{}'::jsonb)
        WHERE conditions IS NOT NULL
    """)

    # ---- alerts: add new columns (dedupe_key already exists from base migration) ----
    op.add_column('alerts',
        sa.Column('group_value', sa.String(length=255), nullable=True))
    op.add_column('alerts',
        sa.Column('evidence_event_ids', postgresql.ARRAY(sa.String()),
                  nullable=True, server_default=sa.text("'{}'")))
    op.add_column('alerts',
        sa.Column('notifications', postgresql.JSONB(astext_type=sa.Text()),
                  nullable=True, server_default=sa.text("'[]'::jsonb")))


def downgrade() -> None:
    # Drop new alerts columns
    op.drop_column('alerts', 'group_value')
    op.drop_column('alerts', 'evidence_event_ids')
    op.drop_column('alerts', 'notifications')

    # Drop new alert_rules columns
    op.drop_column('alert_rules', 'notify')
    op.drop_column('alert_rules', 'cooldown_minutes')
    op.drop_column('alert_rules', 'window_minutes')
    op.drop_column('alert_rules', 'threshold')
    op.drop_column('alert_rules', 'group_by')
    op.drop_column('alert_rules', 'filter')
    op.drop_column('alert_rules', 'rule_type')
