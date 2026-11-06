"""fresh_baseline

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-11-04

Clean baseline generated from actual SQLAlchemy models in app/models/.
Works on empty Docker PostgreSQL. No alter/drop of pre-existing tables.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('User',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('username', sa.String(length=50), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password', sa.String(length=255), nullable=True),
        sa.Column('role', sa.Enum('VIEWER', 'ADMIN', name='Role'), nullable=False),
        sa.Column('tenant', sa.String(length=100), nullable=True),
        sa.Column('status', sa.Enum('FREEZE', 'INACTIVE', 'ACTIVE', name='Status'), nullable=False),
        sa.Column('createAt', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updatedAt', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email', name=op.f('uq_User_email')),
    )
    op.create_index('ix_User_tenant', 'User', ['tenant'], unique=False)
    op.create_index('ix_User_role', 'User', ['role'], unique=False)
    op.create_index('ix_User_create_at', 'User', ['createAt'], unique=False)
    op.create_index('ix_User_status', 'User', ['status'], unique=False)

    op.create_table('Otp',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('optCode', sa.String(length=255), nullable=False),
        sa.Column('rememberToken', sa.String(length=255), nullable=False),
        sa.Column('verifyToken', sa.String(length=255), nullable=True),
        sa.Column('count', sa.Integer(), nullable=False),
        sa.Column('error', sa.Integer(), nullable=False),
        sa.Column('createAt', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updatedAt', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email', name=op.f('uq_Otp_email')),
    )
    op.create_index('ix_Otp_email', 'Otp', ['email'], unique=False)

    op.create_table('alert_rules',
        sa.Column('id', sa.String(length=25), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('tenant', sa.String(length=100), nullable=False),
        sa.Column('conditions', postgresql.JSONB(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('severity', sa.String(length=50), nullable=False),
        sa.Column('createdAt', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updatedAt', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('alerts',
        sa.Column('id', sa.String(length=25), nullable=False),
        sa.Column('rule_id', sa.String(length=25), nullable=False),
        sa.Column('tenant', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('triggeredAt', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('event_ids', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('severity', sa.String(length=50), nullable=False),
        sa.Column('status', sa.Enum('open', 'acknowledged', 'resolved', name='alert_status'), server_default='open', nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('tags', postgresql.ARRAY(sa.String()), server_default='{}', nullable=False),
        sa.Column('dedupe_key', sa.String(length=255), nullable=True),
        sa.Column('group_key', sa.String(length=255), nullable=True),
        sa.Column('count', sa.Integer(), server_default='1', nullable=False),
        sa.Column('first_seen', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_seen', sa.DateTime(timezone=True), nullable=True),
        sa.Column('acknowledged_by', sa.String(length=100), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['rule_id'], ['alert_rules.id'], name=op.f('fk_alerts_rule_id_alert_rules')),
    )
    op.create_index('ix_alerts_tenant_status', 'alerts', ['tenant', 'status'], unique=False)
    op.create_index('ix_alerts_rule_dedupe_triggered', 'alerts', ['rule_id', 'dedupe_key', 'triggeredAt'], unique=False)
    op.create_index('ix_alerts_dedupe_key_active', 'alerts', ['dedupe_key'], unique=True, 
                    postgresql_where=sa.text("status != 'resolved' AND dedupe_key IS NOT NULL"))

    op.create_table('email_notifications',
        sa.Column('id', sa.String(length=150), nullable=False),
        sa.Column('alertId', sa.String(length=25), nullable=True),
        sa.Column('emailType', sa.Enum('alert', 'otp', name='EmailType'), nullable=False),
        sa.Column('tenant', sa.String(length=100), nullable=False),
        sa.Column('recipientEmail', sa.String(length=255), nullable=False),
        sa.Column('subject', sa.String(length=500), nullable=False),
        sa.Column('status', sa.Enum('pending', 'sent', 'failed', 'retrying', name='EmailStatus'), nullable=True),
        sa.Column('attempts', sa.Integer(), nullable=True),
        sa.Column('lastAttemptAt', sa.DateTime(timezone=True), nullable=True),
        sa.Column('lastError', sa.Text(), nullable=True),
        sa.Column('sentAt', sa.DateTime(timezone=True), nullable=True),
        sa.Column('createdAt', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['alertId'], ['alerts.id'], name=op.f('fk_email_notifications_alertId_alerts')),
        sa.UniqueConstraint('alertId', 'emailType', 'recipientEmail', name='uq_email_notification_alert_type_recipient'),
    )
    op.create_index('ix_email_notifications_tenant_status', 'email_notifications', ['tenant', 'status'], unique=False)
    op.create_index('ix_email_notifications_alert_id', 'email_notifications', ['alertId'], unique=False)
    op.create_index('ix_email_notifications_created_at', 'email_notifications', ['createdAt'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_email_notifications_created_at', table_name='email_notifications')
    op.drop_index('ix_email_notifications_alert_id', table_name='email_notifications')
    op.drop_index('ix_email_notifications_tenant_status', table_name='email_notifications')
    op.drop_table('email_notifications')
    op.drop_index('ix_alerts_rule_dedupe_triggered', table_name='alerts')
    op.drop_index('ix_alerts_tenant_status', table_name='alerts')
    op.drop_table('alerts')
    op.drop_table('alert_rules')
    op.drop_index('ix_Otp_email', table_name='Otp')
    op.drop_table('Otp')
    op.drop_index('ix_User_status', table_name='User')
    op.drop_index('ix_User_create_at', table_name='User')
    op.drop_index('ix_User_role', table_name='User')
    op.drop_index('ix_User_tenant', table_name='User')
    op.drop_table('User')
    op.execute('DROP TYPE IF EXISTS "EmailStatus"')
    op.execute('DROP TYPE IF EXISTS "EmailType"')
    op.execute('DROP TYPE IF EXISTS "Action"')
    op.execute('DROP TYPE IF EXISTS "Source"')
    op.execute('DROP TYPE IF EXISTS "Status"')
    op.execute('DROP TYPE IF EXISTS "Role"')
    op.execute('DROP TYPE IF EXISTS "alert_status"')