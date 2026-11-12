import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select, tuple_
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


def resolve_source(
    value: Any, raw_event: Optional[dict] = None, default: Source = Source.API
) -> Source:
    # A string default (for example SYSLOG_SOURCE from settings) is resolved
    # through the same alias map so callers can pass either a Source enum or
    # its configured string value.
    if isinstance(default, str):
        dkey = default.strip().lower().replace("-", "").replace(" ", "").replace("_", "")
        for alias, source in SOURCE_ALIASES.items():
            if alias.replace("_", "") == dkey:
                default = source
                break
        else:
            default = Source.API

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
            return resolve_source(declared, default=default)
        inferred = infer_source_from_event(raw_event)
        # Only fall back to the configured default when inference cannot
        # determine a more specific source. Recognized firewall/router/etc.
        # messages keep their inferred source.
        return default if inferred == Source.API else inferred

    return default


def _json_safe(value: Any, depth: int = 0) -> Any:
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
        source_default: Source = Source.API,
    ) -> Dict[str, Any]:
        if not isinstance(raw_event, dict):
            raise ValidationError(
                f"Event must be a JSON object, got {type(raw_event).__name__}."
            )

        resolved_source = resolve_source(source, raw_event, default=source_default)
        normalized = self.normalizer.normalize_event(raw_event, resolved_source)


        context = context or {}
        context_tenant = context.get("tenant")
        if context_tenant:
            normalized["tenant"] = context_tenant


        validated, validation_error = validate_normalized(normalized)
        if validation_error is not None:
            raise ValidationError(f"Normalization validation failed: {validation_error['error']}")

        tenant = context.get("tenant") or validated.get("tenant") or settings.INGEST_DEFAULT_TENANT
        if not tenant or not str(tenant).strip():
            raise ValidationError("Tenant could not be determined for this event.")
        tenant = str(tenant).strip().lower()

        event = self._build_event(raw_event, validated, resolved_source, tenant)



        existing_event = await self.session.get(Event, (event.id, event.ts)) if event.id else None
        if existing_event is not None:
            return {"event": existing_event, "alerts": []}

        self.session.add(event)
        await self.session.flush()


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
            event_id_value = validated.get("id")

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
        results: Dict[str, Any] = {
            "ingested": 0,
            "failed": len(pre_rejected or []),
            "rejected": len(pre_rejected or []),
            "alerts": [],
            "results": list(pre_rejected or []),
        }

        context = context or {}
        tenant = context.get("tenant")




        prepared: list[tuple[int, Event]] = []
        for idx, event_data in enumerate(events):
            try:
                resolved_source = resolve_source(source, event_data)
                normalized = self.normalizer.normalize_event(event_data, resolved_source)


                context_tenant = context.get("tenant")
                if context_tenant:
                    normalized["tenant"] = context_tenant


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
                prepared.append((idx, event))
            except Exception as e:
                message = getattr(e, "message", None) or str(e)
                results["failed"] += 1
                results["results"].append({
                    "index": idx,
                    "success": False,
                    "error": message,
                })


        existing_keys: set[tuple[Any, Any]] = set()
        keys = list({(event.id, event.ts) for _, event in prepared if event.id})
        if keys:
            existing_rows = await self.session.execute(
                select(Event.id, Event.ts).where(tuple_(Event.id, Event.ts).in_(keys))
            )
            existing_keys = {(row[0], row[1]) for row in existing_rows}

        created_events: list[Event] = []
        seen_keys: set[tuple[Any, Any]] = set()
        for idx, event in prepared:
            key = (event.id, event.ts)
            duplicate = key in existing_keys or key in seen_keys
            seen_keys.add(key)
            if not duplicate:
                created_events.append(event)
            results["ingested"] += 1
            results["results"].append({
                "index": idx,
                "success": True,
                "eventId": event.id,
                "duplicate": duplicate,
            })

        if created_events:
            try:


                async with self.session.begin_nested():
                    self.session.add_all(created_events)
                    await self.session.flush()
            except Exception:




                created_events = await self._insert_events_individually(
                    prepared, existing_keys, results
                )

        if created_events:
            alerts = await self.alerting_engine.evaluate_batch(created_events)
            results["alerts"] = alerts

            try:
                await enqueue_cache_invalidation("logs:*")
            except Exception as exc:
                logger.warning("cache invalidation enqueue failed: %s", exc)

        await self.session.commit()

        return results

    async def _insert_events_individually(
        self,
        prepared: List[tuple[int, Event]],
        existing_keys: set[tuple[Any, Any]],
        results: Dict[str, Any],
    ) -> List[Event]:
        by_index = {
            entry["index"]: entry
            for entry in results["results"]
            if isinstance(entry, dict) and "index" in entry
        }
        inserted: List[Event] = []
        inserted_keys: set[tuple[Any, Any]] = set()
        for idx, event in prepared:
            key = (event.id, event.ts)
            entry = by_index.get(idx)


            if key in existing_keys or key in inserted_keys:
                continue
            try:
                async with self.session.begin_nested():
                    self.session.add(event)
                    await self.session.flush()
                inserted.append(event)
                inserted_keys.add(key)
                if entry is not None:
                    entry.update({
                        "success": True,
                        "eventId": event.id,
                        "duplicate": False,
                    })
                    entry.pop("error", None)
            except Exception as exc:
                message = getattr(exc, "message", None) or str(exc)
                results["ingested"] = max(0, results["ingested"] - 1)
                results["failed"] += 1
                if entry is not None:
                    entry.update({"success": False, "error": message})
                    entry.pop("eventId", None)
        return inserted

    async def ingest_batch_atomic(
        self,
        events: List[tuple[int, Dict[str, Any]]],
        source: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        pre_rejected: Optional[List[Dict[str, Any]]] = None,
        source_default: Source = Source.API,
    ) -> Dict[str, Any]:
        """Ingest a batch in one transaction.

        ``events`` is ``(original_line_index, raw_event)`` so per-line errors
        keep their position in the caller's input. Preparation/validation is
        isolated per line, but persistence is all-or-nothing: a database error
        rolls the whole batch back and is re-raised so the transport can return
        a 5xx and the forwarder can retry without duplicating committed rows.

        Unlike :meth:`ingest_batch`, this method never falls back to per-event
        inserts, because that would turn an infrastructure failure into a
        partial success.
        """
        results: Dict[str, Any] = {
            "ingested": 0,
            "failed": len(pre_rejected or []),
            "rejected": len(pre_rejected or []),
            "duplicates": 0,
            "persisted": 0,
            "alerts": [],
            "results": list(pre_rejected or []),
        }

        context = context or {}
        tenant = context.get("tenant")

        prepared: list[tuple[int, Event]] = []
        for idx, event_data in events:
            try:
                event_source = event_data.get("source") or source
                resolved_source = resolve_source(
                    event_source, event_data, default=source_default
                )
                normalized = self.normalizer.normalize_event(event_data, resolved_source)

                context_tenant = context.get("tenant")
                if context_tenant:
                    normalized["tenant"] = context_tenant

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
                prepared.append((idx, event))
            except Exception as e:
                message = getattr(e, "message", None) or str(e)
                results["failed"] += 1
                results["rejected"] += 1
                results["results"].append({
                    "index": idx,
                    "success": False,
                    "error": message,
                })

        existing_keys: set[tuple[Any, Any]] = set()
        keys = list({(event.id, event.ts) for _, event in prepared if event.id})
        if keys:
            existing_rows = await self.session.execute(
                select(Event.id, Event.ts).where(tuple_(Event.id, Event.ts).in_(keys))
            )
            existing_keys = {(row[0], row[1]) for row in existing_rows}

        created_events: list[Event] = []
        seen_keys: set[tuple[Any, Any]] = set()
        for idx, event in prepared:
            key = (event.id, event.ts)
            duplicate = key in existing_keys or key in seen_keys
            seen_keys.add(key)
            if duplicate:
                results["duplicates"] += 1
            else:
                created_events.append(event)
            results["ingested"] += 1
            results["results"].append({
                "index": idx,
                "success": True,
                "eventId": event.id,
                "duplicate": duplicate,
            })

        try:
            if created_events:
                self.session.add_all(created_events)
                await self.session.flush()

            if created_events:
                results["alerts"] = await self.alerting_engine.evaluate_batch(created_events)

            if created_events:
                try:
                    await enqueue_cache_invalidation("logs:*")
                except Exception as exc:
                    logger.warning("cache invalidation enqueue failed: %s", exc)

            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

        results["persisted"] = len(created_events)
        results["results"].sort(key=lambda entry: entry.get("index", 0))
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
