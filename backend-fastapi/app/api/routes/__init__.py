"""
API Routes Package

All FastAPI route modules.
"""

from app.api.routes import health, auth, ingest, search, dashboard, alerts, rules, users

__all__ = ["health", "auth", "ingest", "search", "dashboard", "alerts", "rules", "users"]