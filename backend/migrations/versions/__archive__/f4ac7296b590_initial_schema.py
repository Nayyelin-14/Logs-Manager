from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'f4ac7296b590'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

 op.create_table('email_notifications',
 sa.Column('id', sa.String(length=150), nullable=False),
 sa.Column('alertId', sa.String(length=25), nullable=True),
 sa.Column('emailType', sa.Enum('ALERT', 'OTP', name='EmailType'), nullable=False),
 sa.Column('tenant', sa.String(length=100), nullable=False),
 sa.Column('recipientEmail', sa.String(length=255), nullable=False),
 sa.Column('subject', sa.String(length=500), nullable=False),
 sa.Column('status', sa.Enum('PENDING', 'SENT', 'FAILED', 'RETRYING', name='EmailStatus'), nullable=True),
 sa.Column('attempts', sa.Integer(), nullable=True),
 sa.Column('lastAttemptAt', sa.DateTime(timezone=True), nullable=True),
 sa.Column('lastError', sa.Text(), nullable=True),
 sa.Column('sentAt', sa.DateTime(timezone=True), nullable=True),
 sa.Column('createdAt', sa.DateTime(timezone=True), server_default='now()', nullable=False),
 sa.ForeignKeyConstraint(['alertId'], ['alerts.id'], name=op.f('fk_email_notifications_alertId_alerts')),
 sa.PrimaryKeyConstraint('id', name=op.f('pk_email_notifications')),
 sa.UniqueConstraint('alertId', 'emailType', 'recipientEmail', name='uq_email_notification_alert_type_recipient')
 )
 op.create_index('ix_email_notifications_alert_id', 'email_notifications', ['alertId'], unique=False)
 op.create_index('ix_email_notifications_created_at', 'email_notifications', ['createdAt'], unique=False)
 op.create_index('ix_email_notifications_tenant_status', 'email_notifications', ['tenant', 'status'], unique=False)
 op.drop_table('_prisma_migrations')
 op.alter_column('Otp', 'email',
              existing_type=sa.TEXT(),
              type_=sa.String(length=255),
              existing_nullable=False)
 op.alter_column('Otp', 'optCode',
              existing_type=sa.TEXT(),
              type_=sa.String(length=255),
              existing_nullable=False)
 op.alter_column('Otp', 'rememberToken',
              existing_type=sa.TEXT(),
              type_=sa.String(length=255),
              existing_nullable=False)
 op.alter_column('Otp', 'verifyToken',
              existing_type=sa.TEXT(),
              type_=sa.String(length=255),
              existing_nullable=True)
 op.alter_column('Otp', 'count',
              existing_type=sa.SMALLINT(),
              server_default=None,
              type_=sa.Integer(),
              existing_nullable=False)
 op.alter_column('Otp', 'error',
              existing_type=sa.SMALLINT(),
              server_default=None,
              type_=sa.Integer(),
              existing_nullable=False)
 op.alter_column('Otp', 'createAt',
              existing_type=postgresql.TIMESTAMP(precision=3),
              server_default='now()',
              type_=sa.DateTime(timezone=True),
              existing_nullable=False)
 op.alter_column('Otp', 'updatedAt',
              existing_type=postgresql.TIMESTAMP(precision=3),
              server_default='now()',
              type_=sa.DateTime(timezone=True),
              existing_nullable=False)
 op.drop_index(op.f('Otp_email_key'), table_name='Otp')
 op.create_index('ix_Otp_email', 'Otp', ['email'], unique=False)
 op.create_unique_constraint(op.f('uq_Otp_email'), 'Otp', ['email'])
 op.alter_column('User', 'username',
              existing_type=sa.TEXT(),
              type_=sa.String(length=50),
              existing_nullable=True)
 op.alter_column('User', 'email',
              existing_type=sa.TEXT(),
              type_=sa.String(length=255),
              existing_nullable=False)
 op.alter_column('User', 'password',
              existing_type=sa.TEXT(),
              type_=sa.String(length=255),
              existing_nullable=True)
 op.alter_column('User', 'role',
              existing_type=postgresql.ENUM('USER', 'ADMIN', name='Role'),
              server_default=None,
              existing_nullable=False)
 op.alter_column('User', 'tenant',
              existing_type=sa.TEXT(),
              type_=sa.String(length=100),
              existing_nullable=True)
 op.alter_column('User', 'status',
              existing_type=postgresql.ENUM('FREEZE', 'INACTIVE', 'ACTIVE', name='Status'),
              server_default=None,
              existing_nullable=False)
 op.alter_column('User', 'createAt',
              existing_type=postgresql.TIMESTAMP(precision=3),
              server_default='now()',
              type_=sa.DateTime(timezone=True),
              existing_nullable=False)
 op.alter_column('User', 'updatedAt',
              existing_type=postgresql.TIMESTAMP(precision=3),
              server_default='now()',
              type_=sa.DateTime(timezone=True),
              existing_nullable=False)
 op.drop_index(op.f('User_createAt_idx'), table_name='User')
 op.drop_index(op.f('User_email_key'), table_name='User')
 op.drop_index(op.f('User_role_idx'), table_name='User')
 op.drop_index(op.f('User_status_idx'), table_name='User')
 op.drop_index(op.f('User_tenant_idx'), table_name='User')
 op.create_index('ix_User_create_at', 'User', ['createAt'], unique=False)
 op.create_index('ix_User_role', 'User', ['role'], unique=False)
 op.create_index('ix_User_status', 'User', ['status'], unique=False)
 op.create_index('ix_User_tenant', 'User', ['tenant'], unique=False)
 op.create_unique_constraint(op.f('uq_User_email'), 'User', ['email'])
 op.alter_column('alert_rules', 'id',
              existing_type=sa.TEXT(),
              type_=sa.String(length=25),
              existing_nullable=False)
 op.alter_column('alert_rules', 'name',
              existing_type=sa.TEXT(),
              type_=sa.String(length=255),
              existing_nullable=False)
 op.alter_column('alert_rules', 'tenant',
              existing_type=sa.TEXT(),
              type_=sa.String(length=100),
              existing_nullable=False)
 op.alter_column('alert_rules', 'enabled',
              existing_type=sa.BOOLEAN(),
              server_default=None,
              existing_nullable=False)
 op.alter_column('alert_rules', 'severity',
              existing_type=sa.TEXT(),
              server_default=None,
              type_=sa.String(length=50),
              existing_nullable=False)
 op.alter_column('alert_rules', 'createdAt',
              existing_type=postgresql.TIMESTAMP(precision=3),
              server_default='now()',
              type_=sa.DateTime(timezone=True),
              existing_nullable=False)
 op.alter_column('alert_rules', 'updatedAt',
              existing_type=postgresql.TIMESTAMP(precision=3),
              server_default='now()',
              type_=sa.DateTime(timezone=True),
              existing_nullable=False)
 op.alter_column('alerts', 'id',
              existing_type=sa.TEXT(),
              type_=sa.String(length=25),
              existing_nullable=False)
 op.alter_column('alerts', 'rule_id',
              existing_type=sa.TEXT(),
              type_=sa.String(length=25),
              existing_nullable=False)
 op.alter_column('alerts', 'tenant',
              existing_type=sa.TEXT(),
              type_=sa.String(length=100),
              existing_nullable=False)
 op.alter_column('alerts', 'triggeredAt',
              existing_type=postgresql.TIMESTAMP(precision=3),
              server_default='now()',
              type_=sa.DateTime(timezone=True),
              existing_nullable=False)
 op.alter_column('alerts', 'event_ids',
              existing_type=postgresql.ARRAY(sa.TEXT()),
              type_=sa.ARRAY(sa.String()),
              nullable=False)
 op.alter_column('alerts', 'severity',
              existing_type=sa.TEXT(),
              type_=sa.String(length=50),
              existing_nullable=False)
 op.alter_column('alerts', 'status',
              existing_type=sa.TEXT(),
              server_default=None,
              type_=sa.String(length=50),
              existing_nullable=False)
 op.alter_column('alerts', 'title',
              existing_type=sa.TEXT(),
              type_=sa.String(length=255),
              existing_nullable=False)
 op.alter_column('alerts', 'dedupe_key',
              existing_type=sa.TEXT(),
              type_=sa.String(length=255),
              existing_nullable=True)
 op.alter_column('security_logs', 'id',
              existing_type=sa.TEXT(),
              type_=sa.String(length=25),
              existing_nullable=False)
 op.alter_column('security_logs', '@timestamp',
              existing_type=postgresql.TIMESTAMP(precision=3),
              server_default='now()',
              type_=sa.DateTime(timezone=True),
              existing_nullable=False)
 op.alter_column('security_logs', 'tenant',
              existing_type=sa.TEXT(),
              type_=sa.String(length=100),
              existing_nullable=False)
 op.alter_column('security_logs', 'vendor',
              existing_type=sa.TEXT(),
              type_=sa.String(length=100),
              existing_nullable=True)
 op.alter_column('security_logs', 'product',
              existing_type=sa.TEXT(),
              type_=sa.String(length=100),
              existing_nullable=True)
 op.alter_column('security_logs', 'event_type',
              existing_type=sa.TEXT(),
              type_=sa.String(length=200),
              existing_nullable=False)
 op.alter_column('security_logs', 'canonical_event_type',
              existing_type=sa.TEXT(),
              type_=sa.String(length=200),
              existing_nullable=True)
 op.alter_column('security_logs', 'original_event_type',
              existing_type=sa.TEXT(),
              type_=sa.String(length=200),
              existing_nullable=True)
 op.alter_column('security_logs', 'event_subtype',
              existing_type=sa.TEXT(),
              type_=sa.String(length=200),
              existing_nullable=True)
 op.alter_column('security_logs', 'severity',
              existing_type=sa.INTEGER(),
              server_default=None,
              nullable=False)
 op.alter_column('security_logs', 'src_ip',
              existing_type=sa.TEXT(),
              type_=sa.String(length=45),
              existing_nullable=True)
 op.alter_column('security_logs', 'src_port',
              existing_type=sa.TEXT(),
              type_=sa.String(length=10),
              existing_nullable=True)
 op.alter_column('security_logs', 'dst_ip',
              existing_type=sa.TEXT(),
              type_=sa.String(length=45),
              existing_nullable=True)
 op.alter_column('security_logs', 'dst_port',
              existing_type=sa.TEXT(),
              type_=sa.String(length=10),
              existing_nullable=True)
 op.alter_column('security_logs', 'protocol',
              existing_type=sa.TEXT(),
              type_=sa.String(length=20),
              existing_nullable=True)
 op.alter_column('security_logs', 'user',
              existing_type=sa.TEXT(),
              type_=sa.String(length=255),
              existing_nullable=True)
 op.alter_column('security_logs', 'host',
              existing_type=sa.TEXT(),
              type_=sa.String(length=255),
              existing_nullable=True)
 op.alter_column('security_logs', 'process',
              existing_type=sa.TEXT(),
              type_=sa.String(length=255),
              existing_nullable=True)
 op.alter_column('security_logs', 'url',
              existing_type=sa.TEXT(),
              type_=sa.Text(),
              existing_nullable=True)
 op.alter_column('security_logs', 'http_method',
              existing_type=sa.TEXT(),
              type_=sa.String(length=10),
              existing_nullable=True)
 op.alter_column('security_logs', 'status_code',
              existing_type=sa.INTEGER(),
              type_=sa.Integer(),
              existing_nullable=True)
 op.alter_column('security_logs', 'rule_name',
              existing_type=sa.TEXT(),
              type_=sa.String(length=255),
              existing_nullable=True)
 op.alter_column('security_logs', 'rule_id',
              existing_type=sa.TEXT(),
              type_=sa.String(length=255),
              existing_nullable=True)
 op.alter_column('security_logs', 'cloud_account_id',
              existing_type=sa.TEXT(),
              type_=sa.String(length=100),
              existing_nullable=True)
 op.alter_column('security_logs', 'cloud_region',
              existing_type=sa.TEXT(),
              type_=sa.String(length=100),
              existing_nullable=True)
 op.alter_column('security_logs', 'cloud_service',
              existing_type=sa.TEXT(),
              type_=sa.String(length=100),
              existing_nullable=True)
 op.alter_column('security_logs', '_tags',
              existing_type=postgresql.ARRAY(sa.TEXT()),
              type_=sa.ARRAY(sa.String()),
              nullable=True)

op.execute("UPDATE security_logs SET _tags = '{}' WHERE _tags IS NULL")
op.alter_column('security_logs', '_tags',
              existing_type=postgresql.ARRAY(sa.TEXT()),
              type_=sa.ARRAY(sa.String()),
              nullable=False)
op.alter_column('security_logs', 'created_at',
             existing_type=postgresql.TIMESTAMP(precision=3),
             server_default='now()',
             type_=sa.DateTime(timezone=True),
             existing_nullable=False)
op.alter_column('security_logs', 'updated_at',
             existing_type=postgresql.TIMESTAMP(precision=3),
             server_default='now()',
             type_=sa.DateTime(timezone=True),
             existing_nullable=False)
op.alter_column('security_logs', 'ip',
             existing_type=sa.TEXT(),
             type_=sa.String(length=45),
             existing_nullable=True)
op.alter_column('security_logs', 'sha256',
             existing_type=sa.TEXT(),
             type_=sa.String(length=64),
             existing_nullable=True)
op.alter_column('security_logs', 'status',
             existing_type=sa.TEXT(),
             type_=sa.String(length=50),
             existing_nullable=True)
op.alter_column('security_logs', 'interface',
             existing_type=sa.TEXT(),
             type_=sa.String(length=100),
             existing_nullable=True)
op.alter_column('security_logs', 'mac',
             existing_type=sa.TEXT(),
             type_=sa.String(length=17),
             existing_nullable=True)


op.execute('DROP INDEX IF EXISTS "security_logs_@timestamp_idx"')
op.execute('DROP INDEX IF EXISTS "security_logs_tenant_@timestamp_idx"')
op.execute('DROP INDEX IF EXISTS "security_logs_source_@timestamp_idx"')
op.execute('DROP INDEX IF EXISTS "security_logs_event_type_idx"')
op.execute('DROP INDEX IF EXISTS "security_logs_severity_idx"')
op.execute('DROP INDEX IF EXISTS "security_logs_tenant_user_idx"')
op.execute('DROP INDEX IF EXISTS "security_logs_tenant_src_ip_idx"')
op.execute('DROP INDEX IF EXISTS "security_logs_src_ip_idx"')
op.execute('DROP INDEX IF EXISTS "security_logs_tenant_created_at_idx"')
op.execute('DROP INDEX IF EXISTS "security_logs_tenant_source_created_at_idx"')
op.execute('DROP INDEX IF EXISTS "security_logs_tenant_action_created_at_idx"')
op.execute('DROP INDEX IF EXISTS "security_logs_tenant_event_type_created_at_idx"')
op.execute('DROP INDEX IF EXISTS "security_logs_tenant_canonical_event_type_created_at_idx"')
op.execute('DROP INDEX IF EXISTS "security_logs_canonical_event_type_idx"')

op.create_index('ix_security_logs_canonical_event_type', 'security_logs', ['canonical_event_type'], unique=False)
op.create_index('ix_security_logs_event_type', 'security_logs', ['event_type'], unique=False)

op.add_column('security_logs', sa.Column('ingested_at', sa.DateTime(timezone=True), nullable=True))
op.create_index('ix_security_logs_ingested_at', 'security_logs', ['ingested_at'], unique=False)
op.create_index('ix_security_logs_severity', 'security_logs', ['severity'], unique=False)
op.execute('CREATE INDEX IF NOT EXISTS ix_security_logs_source_timestamp ON security_logs (source, "@timestamp")')
op.create_index('ix_security_logs_src_ip', 'security_logs', ['src_ip'], unique=False)
op.execute('CREATE INDEX IF NOT EXISTS ix_security_logs_tenant_action_created_at_desc ON security_logs (tenant, action, created_at DESC)')
op.execute('CREATE INDEX IF NOT EXISTS ix_security_logs_tenant_canonical_event_type_created_at_desc ON security_logs (tenant, canonical_event_type, created_at DESC)')
op.execute('CREATE INDEX IF NOT EXISTS ix_security_logs_tenant_created_at_desc ON security_logs (tenant, created_at DESC)')
op.execute('CREATE INDEX IF NOT EXISTS ix_security_logs_tenant_event_type_created_at_desc ON security_logs (tenant, event_type, created_at DESC)')
op.execute('CREATE INDEX IF NOT EXISTS ix_security_logs_tenant_source_created_at_desc ON security_logs (tenant, source, created_at DESC)')
op.execute('CREATE INDEX IF NOT EXISTS ix_security_logs_tenant_src_ip ON security_logs (tenant, src_ip)')
op.execute('CREATE INDEX IF NOT EXISTS ix_security_logs_tenant_timestamp ON security_logs (tenant, "@timestamp")')
op.execute('CREATE INDEX IF NOT EXISTS ix_security_logs_timestamp ON security_logs ("@timestamp")')



def downgrade() -> None:
 pass

op.execute('DROP INDEX IF EXISTS ix_security_logs_timestamp')
op.execute('DROP INDEX IF EXISTS ix_security_logs_tenant_src_ip')
op.execute('DROP INDEX IF EXISTS ix_security_logs_tenant_canonical_event_type_created_at_desc')
op.execute('DROP INDEX IF EXISTS ix_security_logs_tenant_event_type_created_at_desc')
op.execute('DROP INDEX IF EXISTS ix_security_logs_tenant_action_created_at_desc')
op.execute('DROP INDEX IF EXISTS ix_security_logs_tenant_source_created_at_desc')
op.execute('DROP INDEX IF EXISTS ix_security_logs_tenant_created_at_desc')
op.execute('DROP INDEX IF EXISTS ix_security_logs_src_ip')
op.execute('DROP INDEX IF EXISTS ix_security_logs_source_timestamp')
op.execute('DROP INDEX IF EXISTS ix_security_logs_severity')
op.execute('DROP INDEX IF EXISTS ix_security_logs_ingested_at')
op.execute('DROP INDEX IF EXISTS ix_security_logs_event_type')
op.execute('DROP INDEX IF EXISTS ix_security_logs_canonical_event_type')
op.execute('DROP INDEX IF EXISTS ix_security_logs_tenant_user')
op.drop_column('security_logs', 'ingested_at')
op.alter_column('security_logs', '_tags',
             existing_type=sa.ARRAY(sa.String()),
             type_=postgresql.ARRAY(sa.TEXT()),
             nullable=True)
op.alter_column('security_logs', 'updated_at',
             existing_type=sa.DateTime(timezone=True),
             server_default='now()',
             type_=postgresql.TIMESTAMP(precision=3),
             existing_nullable=False)
op.alter_column('security_logs', 'created_at',
             existing_type=sa.DateTime(timezone=True),
             server_default='now()',
             type_=postgresql.TIMESTAMP(precision=3),
             existing_nullable=False)
op.alter_column('security_logs', 'mac',
             existing_type=sa.String(length=17),
             type_=sa.TEXT(),
             existing_nullable=True)
op.alter_column('security_logs', 'interface',
             existing_type=sa.String(length=100),
             type_=sa.TEXT(),
             existing_nullable=True)
op.alter_column('security_logs', 'status',
             existing_type=sa.String(length=50),
             type_=sa.TEXT(),
             existing_nullable=True)
op.alter_column('security_logs', 'sha256',
             existing_type=sa.String(length=64),
             type_=sa.TEXT(),
             existing_nullable=True)
op.alter_column('security_logs', 'ip',
             existing_type=sa.String(length=45),
             type_=sa.TEXT(),
             existing_nullable=True)
op.alter_column('security_logs', 'updated_at',
             existing_type=sa.DateTime(timezone=True),
             server_default='now()',
             type_=postgresql.TIMESTAMP(precision=3),
             existing_nullable=False)
op.alter_column('security_logs', 'created_at',
             existing_type=sa.DateTime(timezone=True),
             server_default='now()',
             type_=postgresql.TIMESTAMP(precision=3),
             existing_nullable=False)

op.alter_column('security_logs', 'mac',
             existing_type=sa.String(length=17),
             type_=sa.TEXT(),
             existing_nullable=True)
op.alter_column('security_logs', 'interface',
             existing_type=sa.String(length=100),
             type_=sa.TEXT(),
             existing_nullable=True)
op.alter_column('security_logs', 'status',
             existing_type=sa.String(length=50),
             type_=sa.TEXT(),
             existing_nullable=True)
op.alter_column('security_logs', 'priority',
             existing_type=sa.INTEGER(),
             server_default=None,
             type_=sa.INTEGER(),
             existing_nullable=True)
op.alter_column('security_logs', 'sha256',
             existing_type=sa.String(length=64),
             type_=sa.TEXT(),
             existing_nullable=True)
op.alter_column('security_logs', 'ip',
             existing_type=sa.String(length=45),
             type_=sa.TEXT(),
             existing_nullable=True)
op.alter_column('security_logs', 'mac',
             existing_type=sa.String(length=17),
             type_=sa.TEXT(),
             existing_nullable=True)
op.alter_column('security_logs', 'interface',
             existing_type=sa.String(length=100),
             type_=sa.TEXT(),
             existing_nullable=True)
op.alter_column('security_logs', 'rule_id',
             existing_type=sa.String(length=255),
             type_=sa.TEXT(),
             existing_nullable=True)
op.alter_column('security_logs', 'rule_name',
             existing_type=sa.String(length=255),
             type_=sa.TEXT(),
             existing_nullable=True)
op.alter_column('security_logs', 'status_code',
             existing_type=sa.INTEGER(),
             type_=sa.INTEGER(),
             existing_nullable=True)
op.alter_column('security_logs', 'http_method',
             existing_type=sa.String(length=10),
             type_=sa.TEXT(),
             existing_nullable=True)
op.alter_column('security_logs', 'url',
             existing_type=sa.Text(),
             type_=sa.TEXT(),
             existing_nullable=True)
op.alter_column('security_logs', 'process',
             existing_type=sa.String(length=255),
             type_=sa.TEXT(),
             existing_nullable=True)
op.alter_column('security_logs', 'host',
             existing_type=sa.String(length=255),
             type_=sa.TEXT(),
             existing_nullable=True)
op.alter_column('security_logs', 'user',
             existing_type=sa.String(length=255),
             type_=sa.TEXT(),
             existing_nullable=True)
op.alter_column('security_logs', 'protocol',
             existing_type=sa.String(length=20),
             type_=sa.TEXT(),
             existing_nullable=True)
op.alter_column('security_logs', 'dst_port',
             existing_type=sa.String(length=10),
             type_=sa.TEXT(),
             existing_nullable=True)
op.alter_column('security_logs', 'dst_ip',
             existing_type=sa.String(length=45),
             type_=sa.TEXT(),
             existing_nullable=True)
op.alter_column('security_logs', 'src_port',
             existing_type=sa.String(length=10),
             type_=sa.TEXT(),
             existing_nullable=True)
op.alter_column('security_logs', 'src_ip',
             existing_type=sa.String(length=45),
             type_=sa.TEXT(),
             existing_nullable=True)
op.alter_column('security_logs', 'action',
             existing_type=sa.TEXT(),
             type_=sa.TEXT(),
             existing_nullable=True)
op.alter_column('security_logs', 'severity',
             existing_type=sa.INTEGER(),
             server_default=None,
             nullable=True)
op.alter_column('security_logs', 'original_event_type',
             existing_type=sa.String(length=200),
             type_=sa.TEXT(),
             existing_nullable=True)
op.alter_column('security_logs', 'canonical_event_type',
             existing_type=sa.String(length=200),
             type_=sa.TEXT(),
             existing_nullable=True)
op.alter_column('security_logs', 'event_subtype',
             existing_type=sa.String(length=200),
             type_=sa.TEXT(),
             existing_nullable=True)
op.alter_column('security_logs', 'event_type',
             existing_type=sa.String(length=200),
             type_=sa.TEXT(),
             existing_nullable=False)
op.alter_column('security_logs', 'product',
             existing_type=sa.String(length=100),
             type_=sa.TEXT(),
             existing_nullable=True)
op.alter_column('security_logs', 'vendor',
             existing_type=sa.String(length=100),
             type_=sa.TEXT(),
             existing_nullable=True)
op.alter_column('security_logs', 'tenant',
             existing_type=sa.String(length=100),
             type_=sa.TEXT(),
             existing_nullable=False)
op.alter_column('security_logs', '@timestamp',
             existing_type=sa.DateTime(timezone=True),
             server_default='now()',
             type_=postgresql.TIMESTAMP(precision=3),
             existing_nullable=False)
op.alter_column('security_logs', 'id',
             existing_type=sa.String(length=25),
             type_=sa.TEXT(),
             existing_nullable=False)
op.execute('DROP INDEX IF EXISTS security_logs_tenant_src_ip_idx')
op.execute('DROP INDEX IF EXISTS security_logs_src_ip_idx')
