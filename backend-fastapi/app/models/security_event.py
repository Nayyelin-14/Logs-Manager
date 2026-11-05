from sqlalchemy import Column, String, Integer, DateTime, Enum as SQLEnum, JSON, ARRAY, Text, Index, ForeignKey, BigInteger, func
from sqlalchemy.dialects.postgresql import JSONB
from app.models.base import Base
from app.models.enums import Source, Action


class SecurityEvent(Base):
    __tablename__ = "security_logs"

    id = Column(String(25), primary_key=True)
    timestamp = Column("@timestamp", DateTime(timezone=True), server_default="now()", nullable=False)
    tenant = Column(String(100), nullable=False)
    source = Column(SQLEnum(Source, name="Source", native_enum=True), nullable=False)
    vendor = Column(String(100), nullable=True)
    product = Column(String(100), nullable=True)
    event_type = Column("event_type", String(200), nullable=False)
    canonical_event_type = Column("canonical_event_type", String(200), nullable=True)
    original_event_type = Column("original_event_type", String(200), nullable=True)
    event_subtype = Column("event_subtype", String(200), nullable=True)
    severity = Column(Integer, default=0, nullable=False)
    action = Column(SQLEnum(Action, name="Action", native_enum=True), nullable=True)
    src_ip = Column("src_ip", String(45), nullable=True)
    src_port = Column("src_port", String(10), nullable=True)
    dst_ip = Column("dst_ip", String(45), nullable=True)
    dst_port = Column("dst_port", String(10), nullable=True)
    protocol = Column(String(20), nullable=True)
    user = Column(String(255), nullable=True)
    host = Column(String(255), nullable=True)
    process = Column(String(255), nullable=True)
    url = Column(Text, nullable=True)
    http_method = Column("http_method", String(10), nullable=True)
    status_code = Column("status_code", Integer, nullable=True)
    rule_name = Column("rule_name", String(255), nullable=True)
    rule_id = Column("rule_id", String(255), nullable=True)
    cloud_account_id = Column("cloud_account_id", String(100), nullable=True)
    cloud_region = Column("cloud_region", String(100), nullable=True)
    cloud_service = Column("cloud_service", String(100), nullable=True)
    raw = Column(JSONB, nullable=False)
    tags = Column("_tags", ARRAY(String), default=[], nullable=False)
    created_at = Column("created_at", DateTime(timezone=True), server_default="now()", nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), server_default="now()", onupdate=func.now(), nullable=False)
    ip = Column(String(45), nullable=True)
    description = Column(Text, nullable=True)
    event_id = Column("eventId", Integer, nullable=True)
    login_type = Column("loginType", Integer, nullable=True)
    priority = Column(Integer, nullable=True)
    sha256 = Column(String(64), nullable=True)
    status = Column(String(50), nullable=True)
    interface = Column(String(100), nullable=True)
    mac = Column(String(17), nullable=True)
    ingested_at = Column(DateTime(timezone=True), server_default="now()", nullable=False)

    __table_args__ = (
        Index("ix_security_logs_timestamp", "@timestamp"),
        Index("ix_security_logs_tenant_timestamp", "tenant", "@timestamp"),
        Index("ix_security_logs_source_timestamp", "source", "@timestamp"),
        Index("ix_security_logs_event_type", "event_type"),
        Index("ix_security_logs_canonical_event_type", "canonical_event_type"),
        Index("ix_security_logs_severity", "severity"),
        Index("ix_security_logs_tenant_user", "tenant", "user"),
        Index("ix_security_logs_tenant_src_ip", "tenant", "src_ip"),
        Index("ix_security_logs_src_ip", "src_ip"),
        Index("ix_security_logs_ingested_at", "ingested_at"),
        Index("ix_security_logs_tenant_created_at_desc", "tenant", "created_at", postgresql_using="btree", postgresql_ops={"created_at": "DESC"}),
        Index("ix_security_logs_tenant_source_created_at_desc", "tenant", "source", "created_at", postgresql_using="btree", postgresql_ops={"created_at": "DESC"}),
        Index("ix_security_logs_tenant_action_created_at_desc", "tenant", "action", "created_at", postgresql_using="btree", postgresql_ops={"created_at": "DESC"}),
        Index("ix_security_logs_tenant_event_type_created_at_desc", "tenant", "event_type", "created_at", postgresql_using="btree", postgresql_ops={"created_at": "DESC"}),
        Index("ix_security_logs_tenant_canonical_event_type_created_at_desc", "tenant", "canonical_event_type", "created_at", postgresql_using="btree", postgresql_ops={"created_at": "DESC"}),
    )