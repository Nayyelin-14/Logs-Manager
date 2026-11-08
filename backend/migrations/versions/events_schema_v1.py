from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import Computed

revision: str = 'b2c3d4e5f6g7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('events',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
        sa.Column('tenant', sa.String(length=100), nullable=False),
        sa.Column('source', sa.Enum('firewall', 'crowdstrike', 'aws', 'm365', 'ad', 'api', 'network', name='source_enum'), nullable=False),
        sa.Column('vendor', sa.String(length=100), nullable=True),
        sa.Column('product', sa.String(length=100), nullable=True),
        sa.Column('event_type', sa.String(length=200), nullable=False),
        sa.Column('event_subtype', sa.String(length=200), nullable=True),
        sa.Column('severity', sa.Integer(), nullable=False),
        sa.Column('action', sa.Enum('allow', 'deny', 'create', 'delete', 'login', 'logout', 'alert', 'other', name='action_enum'), nullable=True),
        sa.Column('action_detail', sa.String(length=255), nullable=True),
        sa.Column('outcome', sa.Enum('success', 'failure', 'unknown', name='outcome_enum'), nullable=True),
        sa.Column('src_ip', sa.String(length=45), nullable=True),
        sa.Column('src_port', sa.Integer(), nullable=True),
        sa.Column('dst_ip', sa.String(length=45), nullable=True),
        sa.Column('dst_port', sa.Integer(), nullable=True),
        sa.Column('protocol', sa.String(length=20), nullable=True),
        sa.Column('user_name', sa.String(length=255), nullable=True),
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
        sa.Column('event_id', sa.Integer(), nullable=True),
        sa.Column('logon_type', sa.Integer(), nullable=True),
        sa.Column('raw', postgresql.JSONB(), nullable=False),
        sa.Column('_tags', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('ingested_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('gin__tsvector', postgresql.TSVECTOR(),
                  Computed("to_tsvector('english'::regconfig, COALESCE(raw::text, ''))", persisted=True)),
        sa.PrimaryKeyConstraint('id', 'ts'),
    )
    op.create_index('ix_events_tenant_ts_desc', 'events', ['tenant', 'ts'], postgresql_using='btree', postgresql_ops={'ts': 'DESC'})
    op.create_index('ix_events_tenant_source_ts', 'events', ['tenant', 'source', 'ts'], postgresql_using='btree')
    op.create_index('ix_events_tenant_src_ip_ts', 'events', ['tenant', 'src_ip', 'ts'], postgresql_using='btree')
    op.create_index('ix_events_tenant_user_name_ts', 'events', ['tenant', 'user_name', 'ts'], postgresql_using='btree')
    op.create_index('ix_events_raw_gin', 'events', ['raw'], postgresql_using='gin')
    op.create_index('ix_events_gin_tsvector', 'events', ['gin__tsvector'], postgresql_using='gin')
    op.create_index('ix_events_src_ip', 'events', ['src_ip'], unique=False)
    op.create_index('ix_events_user_name', 'events', ['user_name'], unique=False)
    op.create_index('ix_events_event_type', 'events', ['event_type'], unique=False)
    op.create_index('ix_events_ingested_at', 'events', ['ingested_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_events_ingested_at', table_name='events')
    op.drop_index('ix_events_event_type', table_name='events')
    op.drop_index('ix_events_user_name', table_name='events')
    op.drop_index('ix_events_src_ip', table_name='events')
    op.drop_index('ix_events_gin_tsvector', table_name='events')
    op.drop_index('ix_events_raw_gin', table_name='events')
    op.drop_index('ix_events_tenant_user_name_ts', table_name='events')
    op.drop_index('ix_events_tenant_src_ip_ts', table_name='events')
    op.drop_index('ix_events_tenant_source_ts', table_name='events')
    op.drop_index('ix_events_tenant_ts_desc', table_name='events')

    op.drop_table('events')

    op.execute('DROP TYPE IF EXISTS source_enum')
    op.execute('DROP TYPE IF EXISTS action_enum')
    op.execute('DROP TYPE IF EXISTS outcome_enum')
