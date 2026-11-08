from __future__ import annotations
from typing import Any
from app.schemas.normalized_event import NormalizedEvent

def validate_normalized(normalized: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:

    try:
        event = NormalizedEvent(**normalized)
        return event.model_dump(), None
    except Exception as exc:
        return None, {"error": str(exc)}
