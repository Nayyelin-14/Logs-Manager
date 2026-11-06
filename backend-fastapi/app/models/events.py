from sqlalchemy import Column, String, Integer, DateTime, Enum as SQLEnum, JSON, ARRAY, Text, Index, func
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.schema import Computed
from app.models.base import Base

OutcomeEnum = SQLEnum(
    "success", "failure", "unknown",
    name="outcome_enum",
    native_enum=True
)

SourceEnum = SQLEnum(
    "firewall", "crowdstrike", "aws", "m365", "ad", "api", "network",
    name="source_enum",
    native_enum=True
)

ActionEnum = SQLEnum(
    "allow", "deny", "create", "delete", "login", "logout", "alert", "other",
    name="action_enum",
    native_enum=True
)


class Event(Base):
    __tablename__ = "events"

    id = Column(String(64), primary_key=True)
    ts = Column("ts", DateTime(timezone=True), primary_key=True)
    tenant = Column(String(100), nullable=False)
    source = Column(SourceEnum, nullable=False)
    vendor = Column(String(100), nullable=True)
    product = Column(String(100), nullable=True)
    event_type = Column("event_type", String(200), nullable=False)
    event_subtype = Column("event_subtype", String(200), nullable=True)
    severity = Column(Integer, nullable=False)
    action = Column(ActionEnum, nullable=True)
    action_detail = Column("action_detail", String(255), nullable=True)
    outcome = Column(OutcomeEnum, nullable=True)
    src_ip = Column("src_ip", String(45), nullable=True)
    src_port = Column("src_port", Integer, nullable=True)
    dst_ip = Column("dst_ip", String(45), nullable=True)
    dst_port = Column("dst_port", Integer, nullable=True)
    protocol = Column("protocol", String(20), nullable=True)
    user_name = Column("user_name", String(255), nullable=True)
    host = Column("host", String(255), nullable=True)
    process = Column("process", String(255), nullable=True)
    url = Column("url", Text, nullable=True)
    http_method = Column("http_method", String(10), nullable=True)
    status_code = Column("status_code", Integer, nullable=True)
    rule_name = Column("rule_name", String(255), nullable=True)
    rule_id = Column("rule_id", String(255), nullable=True)
    cloud_account_id = Column("cloud_account_id", String(100), nullable=True)
    cloud_region = Column("cloud_region", String(100), nullable=True)
    cloud_service = Column("cloud_service", String(100), nullable=True)
    event_id = Column("event_id", Integer, nullable=True)
    logon_type = Column("logon_type", Integer, nullable=True)
    raw = Column("raw", JSONB, nullable=False)
    _tags = Column("_tags", ARRAY(String), nullable=False)
    ingested_at = Column("ingested_at", DateTime(timezone=True), nullable=False, default=func.now(), server_default=func.now())
    gin__tsvector = Column(
        "gin__tsvector",
        TSVECTOR,
        Computed("to_tsvector('english'::regconfig, COALESCE(raw::text, ''))", persisted=True)
    )

    __table_args__ = (
        Index("ix_events_tenant_ts_desc", "tenant", "ts", postgresql_using="btree", postgresql_ops={"ts": "DESC"}),
        Index("ix_events_tenant_source_ts", "tenant", "source", "ts", postgresql_using="btree"),
        Index("ix_events_tenant_src_ip_ts", "tenant", "src_ip", "ts", postgresql_using="btree"),
        Index("ix_events_tenant_user_name_ts", "tenant", "user_name", "ts", postgresql_using="btree"),
        Index("ix_events_raw_gin", "raw", postgresql_using="gin"),
        Index("ix_events_gin_tsvector", "gin__tsvector", postgresql_using="gin"),
        Index("ix_events_src_ip", "src_ip", unique=False),
        Index("ix_events_user_name", "user_name", unique=False),
        Index("ix_events_event_type", "event_type", unique=False),
        Index("ix_events_ingested_at", "ingested_at", unique=False),
    )