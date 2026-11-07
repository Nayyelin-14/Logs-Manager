from functools import lru_cache
from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[".env", ".env.local"],
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # App
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 4501

    # Database
    DATABASE_URL: str
    # "queue" (default pooled) or "null" (NullPool: one connection per checkout,
    # used by the test suite so connections are never shared across event loops)
    DATABASE_POOL: str = "queue"

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # Auth
    ACCESS_TOKEN_SECRET: str
    REFRESH_TOKEN_SECRET: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    JWT_ALGORITHM: str = "HS256"
    COOKIE_SECURE: bool = False
    COOKIE_SAME_SITE: str = "lax"

    # Email (SMTP)
    SMTP_ENABLED: bool = False
    OTP_EMAIL_ENABLED: bool = True
    ALERT_EMAIL_ENABLED: bool = True
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_EMAIL: Optional[str] = None
    SMTP_USE_TLS: bool = True
    ALERT_EMAIL_RECIPIENTS: str = ""

    # Ingestion
    INGEST_API_USERNAME: str = "log-forwarder"
    INGEST_DEFAULT_TENANT: str = "demoA"
    INGEST_BATCH_MAX_EVENTS: int = 1000
    INGEST_MAX_FILE_BYTES: int = 10_485_760

    # Syslog
    SYSLOG_ENABLED: bool = True
    SYSLOG_TENANT: str = "demoA"
    SYSLOG_SOURCE: str = "firewall"
    SYSLOG_USERNAME: str = "syslog"
    SYSLOG_UDP_PORT: int = 5514
    SYSLOG_TCP_PORT: int = 5514
    # Timezone policy for naive RFC3164 syslog timestamps (no offset in line):
    #   "UTC" (default, historical behavior) | "local" | IANA name ("Asia/Bangkok")
    # Unknown values fall back to UTC with a warning. RFC5424 lines carry their
    # own offset and are never affected by this setting.
    SYSLOG_TIMEZONE: str = "UTC"

    # Retention
    RETENTION_DAYS: int = 7
    RETENTION_SCHEDULE: str = "0 5 * * *"

    # Worker
    ALERT_SWEEP_INTERVAL: int = 30
    WORKER_EMBEDDED: bool = False
    SAAS_MODE: bool = False

    # Rate limiting (login brute-force protection)
    LOGIN_RATE_LIMIT: str = "5/minute"        # max login attempts per IP per minute
    LOGIN_LOCKOUT_ATTEMPTS: int = 5           # failed attempts before temporary lockout
    LOGIN_LOCKOUT_MINUTES: int = 15           # lockout duration in minutes

    # CORS
    CORS_ORIGINS: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    
    # Trusted hosts (for TrustedHostMiddleware in production)
    ALLOWED_HOSTS: list[str] = Field(default_factory=lambda: ["localhost", "127.0.0.1", "*.logmanager.local"])

    @field_validator("DATABASE_URL", "REDIS_URL", mode="before")
    @classmethod
    def validate_required_not_empty(cls, v: str) -> str:
        if not v or v.strip() == "":
            raise ValueError("Required environment variable cannot be empty")
        # Check for placeholder values (legacy-carried secrets are exempt;
        # see validate_auth_secrets below)
        placeholder_patterns = [
            "your_",
            "change_me",
            "dev_",
            "ep-xxxx",
        ]
        for pattern in placeholder_patterns:
            if pattern in v.lower():
                raise ValueError(f"Environment variable appears to contain placeholder: {pattern}")
        return v

    @field_validator("ACCESS_TOKEN_SECRET", "REFRESH_TOKEN_SECRET", mode="before")
    @classmethod
    def validate_auth_secrets(cls, v: str) -> str:
        if not v or v.strip() == "":
            raise ValueError("Auth secret cannot be empty")
        # Allow exact secrets carried over during the backend migration so
        # already-issued JWTs keep validating (even if they look like placeholders)
        return v

    def cookie_options(self) -> dict:
        # Preserve the exact cookie options used by the previous backend so
        # existing sessions keep working:
        # secure = COOKIE_SECURE or APP_ENV == "production"
        # sameSite = COOKIE_SAME_SITE or (secure ? "none" : "lax")
        secure = self.COOKIE_SECURE or self.APP_ENV == "production"
        same_site = self.COOKIE_SAME_SITE or ("none" if secure else "lax")
        return {
            "httponly": True,
            "secure": secure,
            "samesite": same_site,
            "path": "/",
        }

@lru_cache
def get_settings() -> Settings:
    return Settings()