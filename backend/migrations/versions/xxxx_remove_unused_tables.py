"""Remove unused security_logs and Otp tables

Revision ID: xxxx_remove_unused_tables
Revises: a7b8c9d0e1f2
Create Date: 2026-11-07

Remove unused security_logs and Otp tables.
events is the canonical event table.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'xxxx_remove_unused_tables'
down_revision: Union[str, Sequence[str], None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table('security_logs')
    op.drop_table('Otp')


def downgrade() -> None:
    op.create_table('security_logs',
        sa.Column('id', sa.String(length=25), nullable=False),
        sa.Column('@timestamp', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('tenant', sa.String(length=100), nullable=False),
        sa.Column('source', sa.Enum('firewall', 'crowdstrike', 'aws', 'm365', 'ad', 'api', 'network', name='Source'), nullable=False),
        sa.Column('vendor', sa.String(length=100), nullable=True),
        sa.Column('product', sa.String(length=100), nullable=True),
        sa.Column('event_type', sa.String(length=200), nullable=False),
        sa.Column('canonical_event_type', sa.String(length=200), nullable=True),
        sa.Column('original_event_type', sa.String(length=200), nullable=True),
        sa.Column('event_subtype', sa.String(length=200), nullable=True),
        sa.Column('severity', sa.Integer(), server_default='0', nullable=False),
        sa.Column('action', sa.Enum('allow', 'deny', 'create', 'delete', 'login', 'logout', 'alert', 'other', name='Action'), nullable=True),
        sa.Column('src_ip', sa.String(length=45), nullable=True),
        sa.Column('src_port', sa.String(length=10), nullable=True),
        sa.Column('dst_ip', sa.String(length=45), nullable=True),
        sa.Column('dst_port', sa.String(length=10), nullable=True),
        sa.Column('protocol', sa.String(length=20), nullable=True),
        sa.Column('user', sa.String(length=255), nullable=True),
        sa.Column('host', sa.String(length=255), nullable=True),
        sa.Column('process', sa.String(length=255), nullable=True),
        sa.Column('url', sa.Text(), nullable=True),
        sa.Column('http_method', sa.String(length=10), nullable=True),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('rule_name', sa.String(length=255), nullable=True),
        sa.Column('rule_id', sa.String(length=255), nullable=True),
        sa.Column('cloud_account_id', sa.String(length=100), nullable=True),
        sa.Column('cloud_region', sa.String(length=100), nullable=True),
        sa.Column('cloud_service', sa.String(length=100), nullable=True),
        sa.Column('raw', postgresql.JSONB(), nullable=False),
        sa.Column('_tags', postgresql.ARRAY(sa.String()), server_default='{}', nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('ip', sa.String(length=45), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('eventId', sa.Integer(), nullable=True),
        sa.Column('loginType', sa.Integer(), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=True),
        sa.Column('sha256', sa.String(length=64), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('interface', sa.String(length=100), nullable=True),
        sa.Column('mac', sa.String(length=17), nullable=True),
        sa.Column('ingested_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('outcome', sa.String(length=20), server_default='unknown', nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_security_logs_timestamp', 'security_logs', ['@timestamp'])
    op.create_index('ix_security_logs_tenant_timestamp', 'security_logs', ['tenant', '@timestamp'])
    op.create_index('ix_security_logs_source_timestamp', 'security_logs', ['source', '@timestamp'])
    op.create_index('ix_security_logs_event_type', 'security_logs', ['event_type'])
    op.create_index('ix_security_logs_canonical_event_type', 'security_logs', ['canonical_event_type'])
    op.create_index('ix_security_logs_severity', 'security_logs', ['severity'])
    op.create_index('ix_security_logs_tenant_user', 'security_logs', ['tenant', 'user'])
    op.create_index('ix_security_logs_tenant_src_ip', 'security_logs', ['tenant', 'src_ip'])
    op.create_index('ix_security_logs_src_ip', 'security_logs', ['src_ip'])
    op.create_index('ix_security_logs_ingested_at', 'security_logs', ['ingested_at'])
    op.create_index('ix_security_logs_tenant_created_at_desc', 'security_logs', ['tenant', 'created_at'], postgresql_using='btree', postgresql_ops={'created_at': 'DESC'})
    op.create_index('ix_security_logs_tenant_source_created_at_desc', 'security_logs', ['tenant', 'source', 'created_at'], postgresql_using='btree', postgresql_ops={'created_at': 'DESC'})
    op.create_index('ix_security_logs_tenant_action_created_at_desc', 'security_logs', ['tenant', 'action', 'created_at'], postgresql_using='btree', postgresql_ops={'created_at': 'DESC'})
    op.create_index('ix_security_logs_tenant_event_type_created_at_desc', 'security_logs', ['tenant', 'event_type', 'created_at'], postgresql_using='btree', postgresql_ops={'created_at': 'DESC'})
    op.create_index('ix_security_logs_tenant_canonical_event_type_created_at_desc', 'security_logs', ['tenant', 'canonical_event_type', 'created_at'], postgresql_using='btree', postgresql_ops={'created_at': 'DESC'})
    op.create_index('ix_security_logs_gin_tsvector', 'security_logs', ['gin__tsvector'], postgresql_using='gin')

    op.create_table('Otp',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('opt_code', sa.String(length=255), nullable=False),
        sa.Column('remember_token', sa.String(length=255), nullable=False),
        sa.Column('verify_token', sa.String(length=255), nullable=True),
        sa.Column('count', sa.Integer(), nullable=False),
        sa.Column('error', sa.Integer(), nullable=False),
        sa.Column('create_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email', name=op.f('uq_Otp_email')),
    )
    op.create_index('ix_Otp_email', 'Otp', ['email'], unique=False)