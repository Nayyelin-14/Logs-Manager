from sqlalchemy import Column, Integer, String, DateTime, Enum as SQLEnum, Index, func
from sqlalchemy.orm import relationship
from app.models.base import Base
from app.models.enums import Role, Status


class User(Base):
    __tablename__ = "User"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), nullable=True)
    email = Column(String(255), unique=True, nullable=False)
    password = Column(String(255), nullable=True)
    role = Column(String(50), default="VIEWER", nullable=False)
    tenant = Column(String(100), nullable=True)
    status = Column(String(50), default="ACTIVE", nullable=False)
    create_at = Column("createAt", DateTime(timezone=True), server_default="now()", nullable=False)
    updated_at = Column("updatedAt", DateTime(timezone=True), server_default="now()", onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_User_tenant", "tenant"),
        Index("ix_User_role", "role"),
        Index("ix_User_create_at", "createAt"),
        Index("ix_User_status", "status"),
    )