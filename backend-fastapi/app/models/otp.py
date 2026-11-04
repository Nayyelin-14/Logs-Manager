from sqlalchemy import Column, Integer, String, DateTime, Enum as SQLEnum, Index
from app.models.base import Base
from app.models.enums import Status


class Otp(Base):
    __tablename__ = "Otp"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False)
    opt_code = Column("optCode", String(255), nullable=False)
    remember_token = Column("rememberToken", String(255), nullable=False)
    verify_token = Column("verifyToken", String(255), nullable=True)
    count = Column(Integer, default=0, nullable=False)
    error = Column(Integer, default=0, nullable=False)
    create_at = Column("createAt", DateTime(timezone=True), server_default="now()", nullable=False)
    updated_at = Column("updatedAt", DateTime(timezone=True), server_default="now()", onupdate="now()", nullable=False)

    __table_args__ = (
        Index("ix_Otp_email", "email"),
    )