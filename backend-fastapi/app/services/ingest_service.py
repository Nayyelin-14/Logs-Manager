"""
Ingestion Service

Orchestrates the log ingestion pipeline:
source resolution -> normalization -> validation -> tenant assignment ->
SecurityEvent persistence -> alert processing.
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
from app.models.security_event import SecurityEvent
from app.parsers.canonical import infer_source_from_event
from app.parsers.router import NormalizationService
from app.services.alert_service import AlertService

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

    async def ingest(
        self,
        raw_event: Dict[str, Any],
        source: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Ingest a single event through the full pipeline."""
        if not isinstance(raw_event, dict):
            raise ValidationError(
                f"Event must be a JSON object, got {type(raw_event).__name__}."
            )

        resolved_source = resolve_source(source, raw_event)
        normalized = self.normalizer.normalize_event(raw_event, resolved_source)

        # Tenant comes from the trusted ingestion context only.
        context = context or {}
        tenant = context.get("tenant") or normalized.get("tenant") or settings.INGEST_DEFAULT_TENANT
        if not tenant or not str(tenant).strip():
            raise ValidationError("Tenant could not be determined for this event.")
        tenant = str(tenant).strip().lower()  # Normalize to lowercase for tenant isolation

        event = self._build_event(raw_event, normalized, resolved_source, tenant)

        self.session.add(event)
        await self.session.flush()

        alerts = await self.alert_service.check_alerts(event)

        # Cache invalidation is an optimization: never fail ingestion on it.
        try:
            await enqueue_cache_invalidation("logs:*")
        except Exception as exc:  # pragma: no cover - depends on Redis availability
            logger.warning("cache invalidation enqueue failed: %s", exc)

        await self.session.commit()

        return {"event": event, "alerts": alerts}

    def _build_event(
        self,
        raw_event: Dict[str, Any],
        normalized: Dict[str, Any],
        source: Source,
        tenant: str,
    ) -> SecurityEvent:
        """Build a SecurityEvent from normalized data with strict field handling."""
        timestamp = None
        raw_timestamp = normalized.get("timestamp")
        if raw_timestamp:
            try:
                timestamp = datetime.fromisoformat(str(raw_timestamp).replace("Z", "+00:00"))
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                logger.warning("unparseable timestamp %r, using ingestion time", raw_timestamp)
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        raw_action = normalized.get("action")
        action = (
            str(raw_action).upper()
            if raw_action and str(raw_action).upper() in _ACTION_NAMES
            else None
        )

        severity = normalized.get("severity")
        try:
            severity = int(severity) if severity is not None else 0
        except (TypeError, ValueError):
            severity = 0
        severity = max(0, min(severity, 10))

        src_port_raw = normalized.get("src_port")
        dst_port_raw = normalized.get("dst_port")

        return SecurityEvent(
            id=uuid.uuid4().hex[:25],
            timestamp=timestamp,
            tenant=tenant,
            source=source,
            vendor=normalized.get("vendor"),
            product=normalized.get("product"),
            event_type=normalized.get("event_type") or "unknown",
            canonical_event_type=normalized.get("canonical_event_type"),
            original_event_type=normalized.get("original_event_type"),
            event_subtype=normalized.get("event_subtype"),
            severity=severity,
            action=action,
            src_ip=normalized.get("src_ip"),
            src_port=str(src_port_raw) if src_port_raw is not None else None,
            dst_ip=normalized.get("dst_ip"),
            dst_port=str(dst_port_raw) if dst_port_raw is not None else None,
            protocol=normalized.get("protocol"),
            user=normalized.get("user"),
            host=normalized.get("host"),
            process=normalized.get("process"),
            url=normalized.get("url"),
            http_method=normalized.get("http_method"),
            status_code=normalized.get("status_code"),
            rule_name=normalized.get("rule_name"),
            rule_id=normalized.get("rule_id"),
            cloud_account_id=normalized.get("cloud_account_id"),
            cloud_region=normalized.get("cloud_region"),
            cloud_service=normalized.get("cloud_service"),
            raw=_build_raw_event(raw_event, normalized),
            tags=[str(tag) for tag in (normalized.get("tags") or [])],
            ip=normalized.get("ip"),
            description=normalized.get("description"),
            event_id=normalized.get("event_id"),
            login_type=normalized.get("login_type"),
            priority=normalized.get("priority"),
            sha256=normalized.get("sha256"),
            status=normalized.get("status"),
            interface=normalized.get("interface"),
            mac=normalized.get("mac"),
            ingested_at=datetime.now(timezone.utc),
        )

    async def ingest_batch(
        self,
        events: List[Dict[str, Any]],
        source: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        pre_rejected: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Ingest multiple events, isolating per-record failures."""
        results: Dict[str, Any] = {
            "ingested": 0,
            "failed": 0,
            "alerts": [],
            "results": list(pre_rejected or []),
        }
        results["failed"] += len(pre_rejected or [])

        for idx, event_data in enumerate(events):
            try:
                result = await self.ingest(event_data, source, context)
                results["ingested"] += 1
                results["alerts"].extend(result["alerts"])
                results["results"].append({
                    "index": idx,
                    "success": True,
                    "eventId": result["event"].id,
                })
            except Exception as e:
                # A failed record must not poison the session for later records.
                await self.session.rollback()
                results["failed"] += 1
                message = getattr(e, "message", None) or str(e)
                results["results"].append({
                    "index": idx,
                    "success": False,
                    "error": message,
                })

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
