from sqlalchemy import Column, String, DateTime, Enum as SQLEnum, JSON, Index, ForeignKey, ARRAY, Text, Boolean, Integer, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.models.base import Base
from app.models.enums import Role, Status, Action, Source
import enum


class AlertStatus(str, enum.Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id = Column(String(25), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    tenant = Column(String(100), nullable=False)
    conditions = Column(JSONB, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    severity = Column(String(50), default="medium", nullable=False)
    created_at = Column("createdAt", DateTime(timezone=True), server_default="now()", nullable=False)
    updated_at = Column("updatedAt", DateTime(timezone=True), server_default="now()", onupdate=func.now(), nullable=False)

    alerts = relationship("Alert", back_populates="rule")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(String(25), primary_key=True)
    rule_id = Column("rule_id", String(25), ForeignKey("alert_rules.id"), nullable=False)
    tenant = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    triggered_at = Column("triggeredAt", DateTime(timezone=True), server_default="now()", nullable=False)
    event_ids = Column(ARRAY(String), nullable=False)
    severity = Column(String(50), nullable=False)
    status = Column(
        SQLEnum(
            AlertStatus,
            name="alert_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default="open", nullable=False
    )
    title = Column(String(255), nullable=False)
    tags = Column("tags", ARRAY(String), default=[], nullable=False)
    dedupe_key = Column("dedupe_key", String(255), nullable=True)
    group_key = Column(String(255), nullable=True)
    count = Column(Integer, default=1, nullable=False)
    first_seen = Column("first_seen", DateTime(timezone=True), nullable=True)
    last_seen = Column("last_seen", DateTime(timezone=True), nullable=True)
    acknowledged_by = Column("acknowledged_by", String(100), nullable=True)
    acknowledged_at = Column("acknowledged_at", DateTime(timezone=True), nullable=True)

    rule = relationship("AlertRule", back_populates="alerts")

    __table_args__ = (
        Index("ix_alerts_tenant_status", "tenant", "status"),
        Index("ix_alerts_rule_dedupe_triggered", "rule_id", "dedupe_key", "triggeredAt"),
        Index("ix_alerts_dedupe_key_active", "dedupe_key", unique=True, 
              postgresql_where=text("status != 'resolved' AND dedupe_key IS NOT NULL")),
    )


class EmailType(str, enum.Enum):
    ALERT = "alert"
    OTP = "otp"


class EmailStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    RETRYING = "retrying"


class EmailNotification(Base):
    __tablename__ = "email_notifications"

    id = Column(String(150), primary_key=True)
    alert_id = Column("alertId", String(25), ForeignKey("alerts.id"), nullable=True)
    email_type = Column(
        "emailType",
        SQLEnum(
            EmailType,
            name="EmailType",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    tenant = Column(String(100), nullable=False)
    recipient_email = Column("recipientEmail", String(255), nullable=False)
    subject = Column(String(500), nullable=False)
    status = Column(
        SQLEnum(
            EmailStatus,
            name="EmailStatus",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=EmailStatus.PENDING,
    )
    attempts = Column(Integer, default=0)
    last_attempt_at = Column("lastAttemptAt", DateTime(timezone=True), nullable=True)
    last_error = Column("lastError", Text, nullable=True)
    sent_at = Column("sentAt", DateTime(timezone=True), nullable=True)
    created_at = Column("createdAt", DateTime(timezone=True), server_default="now()", nullable=False)

    __table_args__ = (
        UniqueConstraint("alertId", "emailType", "recipientEmail", name="uq_email_notification_alert_type_recipient"),
        Index("ix_email_notifications_tenant_status", "tenant", "status"),
        Index("ix_email_notifications_alert_id", "alertId"),
        Index("ix_email_notifications_created_at", "createdAt"),
    )