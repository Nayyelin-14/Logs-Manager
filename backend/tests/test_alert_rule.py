"""
Alert rule model verification tests.
"""
import pytest
from sqlalchemy import inspect
from app.models.alert import AlertRule, Alert


class TestAlertRuleModel:
    """Alert rule model column verification."""

    def test_alert_rule_model_has_required_columns(self):
        """AlertRule model has all required columns."""
        cols = {c.name for c in AlertRule.__table__.columns}
        expected = {
            "id", "name", "description", "tenant", "conditions",
            "enabled", "severity", "createdAt", "updatedAt",
        }
        assert expected.issubset(cols)

    def test_alert_model_has_required_columns(self):
        """Alert model has all required columns."""
        cols = {c.name for c in Alert.__table__.columns}
        expected = {
            "id", "rule_id", "tenant", "description", "triggeredAt",
            "event_ids", "severity", "status", "title", "dedupe_key",
        }
        assert expected.issubset(cols)
