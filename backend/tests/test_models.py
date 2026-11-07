import pytest
from sqlalchemy import inspect
from app.models.user import User
from app.models.alert import AlertRule, Alert, EmailNotification
from app.models.security_event import SecurityEvent


def test_user_model_columns():
    """Verify User model has all required columns (matching actual DB column names)."""
    cols = {c.name for c in User.__table__.columns}
    expected = {
        "id", "username", "email", "password", "role", "tenant",
        "status", "createAt", "updatedAt",
    }
    assert expected.issubset(cols)


def test_user_model_indexes():
    """Verify User model has required indexes."""
    index_names = {ix.name for ix in User.__table__.indexes}
    expected = {
        "ix_User_tenant", "ix_User_role", "ix_User_create_at", "ix_User_status",
    }
    assert expected.issubset(index_names)


def test_alert_rule_model_columns():
    """Verify AlertRule model has all required columns."""
    cols = {c.name for c in AlertRule.__table__.columns}
    expected = {
        "id", "name", "description", "tenant", "conditions",
        "enabled", "severity", "createdAt", "updatedAt",
    }
    assert expected.issubset(cols)


def test_alert_model_columns():
    """Verify Alert model has all required columns."""
    cols = {c.name for c in Alert.__table__.columns}
    expected = {
        "id", "rule_id", "tenant", "description", "triggeredAt",
        "event_ids", "severity", "status", "title", "dedupe_key",
    }
    assert expected.issubset(cols)


def test_security_event_model_columns():
    """Verify SecurityEvent model has all required columns."""
    cols = {c.name for c in SecurityEvent.__table__.columns}
    expected = {
        "id", "@timestamp", "tenant", "source", "vendor", "product",
        "event_type", "canonical_event_type", "original_event_type",
        "event_subtype", "severity", "action", "src_ip", "src_port",
        "dst_ip", "dst_port", "protocol", "user", "host", "process",
        "url", "http_method", "status_code", "rule_name", "rule_id",
        "cloud_account_id", "cloud_region", "cloud_service", "raw",
        "_tags", "created_at", "updated_at", "ip", "description",
        "eventId", "loginType", "priority", "sha256", "status",
        "interface", "mac", "ingested_at",
    }
    assert expected.issubset(cols)


def test_security_event_ingested_at_column():
    """Verify SecurityEvent has ingested_at column."""
    cols = {c.name for c in SecurityEvent.__table__.columns}
    assert "ingested_at" in cols


def test_email_notification_model_columns():
    """Verify EmailNotification model has all required columns."""
    cols = {c.name for c in EmailNotification.__table__.columns}
    expected = {
        "id", "alertId", "emailType", "tenant", "recipientEmail",
        "subject", "status", "attempts", "lastAttemptAt",
        "lastError", "sentAt", "createdAt",
    }
    assert expected.issubset(cols)


def test_email_notification_unique_constraint():
    """Verify EmailNotification has unique constraint on alertId, emailType, recipientEmail."""
    constraints = {c.name for c in EmailNotification.__table__.constraints}
    assert "uq_email_notification_alert_type_recipient" in constraints


def test_table_names_match_prisma():
    """Verify table names match Prisma schema."""
    assert User.__tablename__ == "User"
    assert AlertRule.__tablename__ == "alert_rules"
    assert Alert.__tablename__ == "alerts"
    assert SecurityEvent.__tablename__ == "security_logs"
    assert EmailNotification.__tablename__ == "email_notifications"