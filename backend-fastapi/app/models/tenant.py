from sqlalchemy import Column, String, DateTime, Boolean, text as sa_text
from sqlalchemy.dialects import postgresql
from app.models.base import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(String(25), primary_key=True)
    name = Column(String(50), nullable=False, unique=True)
    api_key_hash = Column(String(64), nullable=False, unique=True)
    is_active = Column(Boolean, nullable=False, server_default=sa_text("true"))
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=sa_text("now()")
    )
    alert_webhook_url = Column(String(500), nullable=True)
    alert_emails = Column(postgresql.ARRAY(String), nullable=True)
