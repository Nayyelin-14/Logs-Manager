"""add_outcome_and_alert_fields

Revision ID: f8e7d6c5b4a3
Revises: a1b2c3d4e5f6
Create Date: 2026-11-05 15:00:00

Migration for PHASE 1 alerting:
- Add outcome column to security_logs
- Add indexes for outcome-based queries
- Add alert columns: group_key, count, first_seen, last_seen, acknowledged_by, acknowledged_at
- Add tags column to alerts
- Add partial unique index on dedupe_key for non-resolved alerts
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'f8e7d6c5b4a3'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = 'phase1'
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add outcome column to security_logs (default to 'unknown')
    op.add_column('security_logs', sa.Column('outcome', sa.String(length=20), nullable=True, server_default='unknown'))
    
    # 2. Add new alert columns
    op.add_column('alerts', sa.Column('group_key', sa.String(length=255), nullable=True))
    op.add_column('alerts', sa.Column('count', sa.Integer(), nullable=True, server_default='1'))
    op.add_column('alerts', sa.Column('first_seen', sa.DateTime(timezone=True), nullable=True))
    op.add_column('alerts', sa.Column('last_seen', sa.DateTime(timezone=True), nullable=True))
    op.add_column('alerts', sa.Column('acknowledged_by', sa.String(length=100), nullable=True))
    op.add_column('alerts', sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('alerts', sa.Column('tags', postgresql.ARRAY(sa.String()), nullable=True, server_default='{}'))
    
    # 3. Create the alert_status enum type
    op.execute(sa.text("CREATE TYPE alert_status AS ENUM ('open', 'acknowledged', 'resolved')"))
    
    # 4. Alter status column to use enum type
    op.execute(sa.text("ALTER TABLE alerts ALTER COLUMN status TYPE alert_status USING status::alert_status"))
    op.execute(sa.text("ALTER TABLE alerts ALTER COLUMN status SET DEFAULT 'open'"))
    
    # 5. Add index on outcome for efficient queries
    op.create_index('ix_security_logs_outcome', 'security_logs', ['outcome'], unique=False)
    op.create_index(
        'ix_security_logs_tenant_outcome_src_ip_ts',
        'security_logs',
        ['tenant', 'outcome', 'src_ip', '@timestamp'],
        unique=False
    )
    
    # 6. Add partial unique index on dedupe_key WHERE status != 'resolved'
    op.create_index(
        'ix_alerts_dedupe_key_active',
        'alerts',
        ['dedupe_key'],
        unique=True,
        postgresql_where=sa.text("status != 'resolved' AND dedupe_key IS NOT NULL")
    )
    
    # 7. Backfill outcome for existing events
    # AD 4625 -> failure, AD 4624 -> success
    # M365 with status in ['Failure', 'Failed'] -> failure
    # M365 with status in ['Success', 'Successful'] -> success
    # canonical_event_type: ad_logon_failed, login_failed -> failure; ad_logon_success, login_success -> success
    op.execute(sa.text("""
        UPDATE security_logs 
        SET outcome = 'failure' 
        WHERE outcome = 'unknown' 
          AND (
            ("eventId" = 4625) 
            OR (status ILIKE '%fail%' AND action = 'LOGIN')
            OR (canonical_event_type IN ('ad_logon_failed', 'login_failed', 'logon_failed'))
          )
    """))
    op.execute(sa.text("""
        UPDATE security_logs 
        SET outcome = 'success' 
        WHERE outcome = 'unknown' 
          AND (
            ("eventId" = 4624) 
            OR (status ILIKE '%success%' AND action = 'LOGIN')
            OR (canonical_event_type IN ('ad_logon_success', 'login_success', 'logon_success'))
          )
    """))


def downgrade() -> None:
    # Drop indices first
    op.drop_index('ix_security_logs_outcome', table_name='security_logs')
    op.drop_index('ix_security_logs_tenant_outcome_src_ip_ts', table_name='security_logs')
    op.drop_index('ix_alerts_dedupe_key_active', table_name='alerts')
    
    # Drop new columns
    op.drop_column('security_logs', 'outcome')
    
    op.drop_column('alerts', 'group_key')
    op.drop_column('alerts', 'count')
    op.drop_column('alerts', 'first_seen')
    op.drop_column('alerts', 'last_seen')
    op.drop_column('alerts', 'acknowledged_by')
    op.drop_column('alerts', 'acknowledged_at')
    op.drop_column('alerts', 'tags')
    
    # Drop the custom enum type
    op.execute(sa.text("DROP TYPE alert_status"))
    
    # Revert status column back to string
    op.execute(sa.text("ALTER TABLE alerts ALTER COLUMN status TYPE VARCHAR(50) USING status::VARCHAR(50)"))
    
    # Drop old indices that will be recreated by baseline
    op.drop_index('ix_alerts_tenant_status', table_name='alerts')
    op.drop_index('ix_alerts_rule_dedupe_triggered', table_name='alerts')