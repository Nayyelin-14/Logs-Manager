"""
Ingestion Service

Orchestrates the log ingestion pipeline:
source resolution -> normalization -> validation -> tenant assignment ->
Event persistence -> alert processing.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ValidationError
from app.integrations.queue import enqueue_cache_invalidation
from app.models.enums import Action, Source
from app.models.events import Event
from app.parsers.canonical import infer_source_from_event
from app.parsers.router import NormalizationService
from app.services.alert_service import AlertService
from app.services.alerting.engine import AlertingEngine
from app.services.validation import validate_normalized

settings = get_settings()
logger = logging.getLogger(__name__)

# Friendly aliases accepted from HTTP/file/syslog ingestion payloads.
SOURCE_ALIASES: Dict[str, Source] = {
    "firewall": Source.FIREWALL,
    "syslog": Source.FIREWALL,
    "network": Source.NETWORK,
    "router": Source.NETWORK,
    "api": Source.API,
    "http": Source.API,
    "aws": Source.AWS,
    "cloudtrail": Source.AWS,
    "m365": Source.M365,
    "o365": Source.M365,
    "office365": Source.M365,
    "microsoft365": Source.M365,
    "microsoft": Source.M365,
    "ad": Source.AD,
    "activedirectory": Source.AD,
    "active_directory": Source.AD,
    "windows": Source.AD,
    "crowdstrike": Source.CROWDSTRIKE,
    "falcon": Source.CROWDSTRIKE,
}

SUPPORTED_SOURCES = ", ".join(sorted(SOURCE_ALIASES))
_ACTION_NAMES = {action.value for action in Action}


def resolve_source(value: Any, raw_event: Optional[dict] = None) -> Source:
    """Resolve a caller-supplied source hint into a Source enum.

    Raises ValidationError for unrecognized sources instead of silently
    mapping them onto an unrelated source.
    """
    if isinstance(value, Source):
        return value

    if value and str(value).strip().lower() == "auto":
        value = None

    if value:
        key = str(value).strip().lower().replace("-", "").replace(" ", "").replace("_", "")
        for alias, source in SOURCE_ALIASES.items():
            if alias.replace("_", "") == key:
                return source
        raise ValidationError(
            f"Unsupported source '{value}'. Supported sources: {SUPPORTED_SOURCES}."
        )

    if raw_event:
        declared = raw_event.get("source")
        if declared and declared is not value:
            return resolve_source(declared)
        return infer_source_from_event(raw_event)

    return Source.API


def _json_safe(value: Any, depth: int = 0) -> Any:
    """Coerce a value into something JSONB-serializable without dropping data."""
    if depth > 12:
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v, depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v, depth + 1) for v in value]
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _build_raw_event(raw_event: Dict[str, Any], normalized: Dict[str, Any]) -> Dict[str, Any]:
    """Preserve the raw payload: original event plus the syslog line if present."""
    raw = normalized.get("raw")
    if isinstance(raw, dict):
        payload = dict(raw)
    elif raw is None:
        payload = dict(raw_event)
    else:
        payload = {"value": _json_safe(raw)}
    payload.setdefault("raw", _json_safe(raw_event))
    return _json_safe(payload)


class IngestionService:
    """Orchestrates the complete ingestion pipeline."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.normalizer = NormalizationService()
        self.alert_service = AlertService(session)
        self.alerting_engine = AlertingEngine(session)

    async def ingest(
        self,
        raw_event: Dict[str, Any],
        source: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Ingest a single event through the full pipeline.
        
        Uses batch evaluation internally for consistent alerting behavior.
        """
        if not isinstance(raw_event, dict):
            raise ValidationError(
                f"Event must be a JSON object, got {type(raw_event).__name__}."
            )

        resolved_source = resolve_source(source, raw_event)
        normalized = self.normalizer.normalize_event(raw_event, resolved_source)

        # Apply tenant from context before validation (API key / JWT tenant takes precedence)
        context = context or {}
        context_tenant = context.get("tenant")
        if context_tenant:
            normalized["tenant"] = context_tenant

        # Validate through NormalizedEvent (Pydantic v2 schema)
        validated, validation_error = validate_normalized(normalized)
        if validation_error is not None:
            raise ValidationError(f"Normalization validation failed: {validation_error['error']}")

        tenant = context.get("tenant") or validated.get("tenant") or settings.INGEST_DEFAULT_TENANT
        if not tenant or not str(tenant).strip():
            raise ValidationError("Tenant could not be determined for this event.")
        tenant = str(tenant).strip().lower()

        event = self._build_event(raw_event, validated, resolved_source, tenant)

        # Deterministic IDs make ingestion idempotent: a repeated identical
        # event is accepted without creating a duplicate row or alert.
        existing_event = await self.session.get(Event, (event.id, event.ts)) if event.id else None
        if existing_event is not None:
            return {"event": existing_event, "alerts": []}

        self.session.add(event)
        await self.session.flush()

        # Evaluate alerts for this single event using batch evaluation
        alerts = await self.alerting_engine.evaluate_batch([event])

        try:
            await enqueue_cache_invalidation("logs:*")
        except Exception as exc:
            logger.warning("cache invalidation enqueue failed: %s", exc)

        await self.session.commit()

        return {"event": event, "alerts": alerts}

    def _build_event(
        self,
        raw_event: Dict[str, Any],
        validated: Dict[str, Any],
        source: Source,
        tenant: str,
    ) -> Event:
        """Build an Event from normalized data with strict field handling."""
        timestamp = None
        raw_timestamp = validated.get("ts") or validated.get("timestamp")
        if raw_timestamp:
            try:
                timestamp = datetime.fromisoformat(str(raw_timestamp).replace("Z", "+00:00"))
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                logger.warning("unparseable timestamp %r, using ingestion time", raw_timestamp)
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        raw_action = validated.get("action")
        # Normalize enum values to lowercase strings
        if hasattr(raw_action, "value"):
            raw_action = raw_action.value
        action = (
            str(raw_action).lower()
            if raw_action
            and str(raw_action).upper()
            in {a.value.upper() for a in Action}
            else None
        )

        severity = validated.get("severity")
        try:
            severity = int(severity) if severity is not None else 0
        except (TypeError, ValueError):
            severity = 0
        severity = max(0, min(severity, 10))

        outcome = validated.get("outcome")
        if outcome is None:
            from app.parsers.helpers import determine_outcome
            from app.models.enums import Source as SourceEnum
            outcome = determine_outcome(
                event_type=validated.get("event_type"),
                canonical_event_type=validated.get("canonical_event_type"),
                status=validated.get("status"),
                action=validated.get("action"),
                severity=severity,
                event_id=validated.get("event_id"),
                source=source
            )

        src_port_raw = validated.get("src_port")
        dst_port_raw = validated.get("dst_port")

        event_id_value = validated.get("id")
        if event_id_value is None:
            event_id_value = validated.get("id")  # NormalizedEvent generates deterministic id

        return Event(
            id=event_id_value,
            ts=timestamp,
            tenant=tenant,
            source=source.value.lower(),
            vendor=validated.get("vendor"),
            product=validated.get("product"),
            event_type=validated.get("event_type") or "unknown",
            event_subtype=validated.get("event_subtype"),
            severity=severity,
            action=action,
            action_detail=validated.get("action_detail"),
            outcome=outcome,
            src_ip=validated.get("src_ip"),
            src_port=int(src_port_raw) if src_port_raw is not None else None,
            dst_ip=validated.get("dst_ip"),
            dst_port=int(dst_port_raw) if dst_port_raw is not None else None,
            protocol=validated.get("protocol"),
            user_name=validated.get("user"),
            host=validated.get("host"),
            process=validated.get("process"),
            url=validated.get("url"),
            http_method=validated.get("http_method"),
            status_code=validated.get("status_code"),
            rule_name=validated.get("rule_name"),
            rule_id=validated.get("rule_id"),
            cloud_account_id=validated.get("cloud_account_id"),
            cloud_region=validated.get("cloud_region"),
            cloud_service=validated.get("cloud_service"),
            raw=_build_raw_event(raw_event, validated),
            _tags=[str(tag) for tag in (validated.get("tags") or [])],
            event_id=validated.get("event_id"),
            logon_type=validated.get("logon_type"),
            ingested_at=datetime.now(timezone.utc),
        )

    async def ingest_batch(
        self,
        events: List[Dict[str, Any]],
        source: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        pre_rejected: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Ingest multiple events with ONE alert evaluation and ONE commit.
        
        Uses nested transactions (SAVEPOINTs) to isolate each event's ingestion.
        If one event fails, only that event is rolled back while previously
        successful events are preserved.
        """
        results: Dict[str, Any] = {
            "ingested": 0,
            "failed": len(pre_rejected or []),
            "rejected": len(pre_rejected or []),
            "alerts": [],
            "results": list(pre_rejected or []),
        }

        context = context or {}
        tenant = context.get("tenant")
        
        created_events = []
        
        for idx, event_data in enumerate(events):
            try:
                async with self.session.begin_nested():
                    resolved_source = resolve_source(source, event_data)
                    normalized = self.normalizer.normalize_event(event_data, resolved_source)

                    # Apply tenant from context before validation
                    batch_context = context or {}
                    context_tenant = batch_context.get("tenant")
                    if context_tenant:
                        normalized["tenant"] = context_tenant

                    # Validate through NormalizedEvent (Pydantic v2 schema)
                    validated, validation_error = validate_normalized(normalized)
                    if validation_error is not None:
                        raise ValidationError(
                            f"Normalization validation failed: {validation_error['error']}"
                        )

                    event_tenant = tenant or validated.get("tenant") or settings.INGEST_DEFAULT_TENANT
                    if not event_tenant or not str(event_tenant).strip():
                        raise ValidationError("Tenant could not be determined for this event.")
                    event_tenant = str(event_tenant).strip().lower()

                    event = self._build_event(event_data, validated, resolved_source, event_tenant)
                    existing_event = await self.session.get(Event, (event.id, event.ts)) if event.id else None
                    if existing_event is None:
                        self.session.add(event)
                        await self.session.flush()
                
                if existing_event is None:
                    created_events.append(event)
                results["ingested"] += 1
                results["results"].append({
                    "index": idx,
                    "success": True,
                    "eventId": event.id,
                    "duplicate": existing_event is not None,
                })
            except Exception as e:
                message = getattr(e, "message", None) or str(e)
                results["failed"] += 1
                results["results"].append({
                    "index": idx,
                    "success": False,
                    "error": message,
                })
        
        if created_events:
            alerts = await self.alerting_engine.evaluate_batch(created_events)
            results["alerts"] = alerts

            try:
                await enqueue_cache_invalidation("logs:*")
            except Exception as exc:
                logger.warning("cache invalidation enqueue failed: %s", exc)

        await self.session.commit()

        return results

    async def ingest_file(
        self,
        content: bytes,
        filename: str,
        mime_type: Optional[str],
        source: Optional[str] = None,
        tenant: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Parse an uploaded file and ingest every record it contains."""
        from app.ingest.batch import parse_batch_records, validate_upload

        validate_upload(filename, len(content))
        events, rejected, fmt = parse_batch_records(content, filename, mime_type or "")

        file_context = {**(context or {})}
        if tenant:
            file_context["tenant"] = tenant

        results = await self.ingest_batch(events, source, file_context, pre_rejected=rejected)
        results["format"] = fmt
        results["filename"] = filename
        results["parsed"] = len(events) + len(rejected)
        return results
