"""
NormalizedEvent validation wrapper.

Validates a normalized event dict through the Pydantic NormalizedEvent model.
Returns (validated_db_dict, None) on success, or (None, error_dict) on failure.
Invalid records are rejected per-record and never fail the batch.
"""

from __future__ import annotations

from typing import Any
from app.schemas.normalized_event import NormalizedEvent


def validate_normalized(normalized: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Validate a normalized event dict.

    Returns:
        (validated_dict, None) on success, or (None, {"error": str}) on failure.
        validated_dict uses NormalizedEvent field names (ts, user, etc.).
    """
    try:
        event = NormalizedEvent(**normalized)
        return event.model_dump(), None
    except Exception as exc:  # pydantic.ValidationError or ValueError
        return None, {"error": str(exc)}
