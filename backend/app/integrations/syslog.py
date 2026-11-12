import asyncio
import ipaddress
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Optional
from zoneinfo import ZoneInfo

from app.core.config import get_settings
from app.core.exceptions import ValidationError, is_transient_db_error

settings = get_settings()
logger = logging.getLogger(__name__)

MAX_TCP_BUFFER = 1_048_576
MAX_OCTET_LENGTH = 1_048_576


class SyslogCounters:
    """Process-local counters for native Syslog ingestion.

    Exposed through the local health endpoint so operators can see drops
    without scraping logs. Counters are not persisted; they reset on restart.
    """

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.received = 0
        self.accepted = 0
        self.invalid = 0
        self.denied = 0
        self.overloaded = 0
        self.retried = 0
        self.retry_exhausted = 0
        self.dropped = 0

    def snapshot(self) -> Dict[str, int]:
        return {
            "received": self.received,
            "accepted": self.accepted,
            "invalid": self.invalid,
            "denied": self.denied,
            "overloaded": self.overloaded,
            "retried": self.retried,
            "retry_exhausted": self.retry_exhausted,
            "dropped": self.dropped,
        }


syslog_counters = SyslogCounters()


_network_cache: Optional[tuple[str, tuple]] = None


def allowed_networks() -> tuple:
    """Parse ``SYSLOG_ALLOWED_CIDRS`` lazily, caching by raw value."""
    global _network_cache
    raw = str(getattr(settings, "SYSLOG_ALLOWED_CIDRS", "") or "").strip()
    if _network_cache is not None and _network_cache[0] == raw:
        return _network_cache[1]

    networks = []
    if raw:
        for token in raw.split(","):
            token = token.strip()
            if not token:
                continue
            try:
                networks.append(ipaddress.ip_network(token, strict=False))
            except ValueError:
                logger.warning("ignoring invalid SYSLOG_ALLOWED_CIDRS entry %r", token)
    _network_cache = (raw, tuple(networks))
    return _network_cache[1]


def is_source_allowed(ip: Optional[str]) -> bool:
    """Return True when the peer is allowed (empty allowlist means allow all)."""
    networks = allowed_networks()
    if not networks:
        return True
    if not ip:
        return False
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(address in network for network in networks)


def enabled_listeners() -> tuple[bool, bool]:
    """Return ``(udp_enabled, tcp_enabled)`` for the native listener."""
    enabled = bool(getattr(settings, "SYSLOG_ENABLED", True))
    udp = enabled and bool(getattr(settings, "SYSLOG_UDP_PORT", 0))
    tcp = enabled and bool(getattr(settings, "SYSLOG_TCP_PORT", 0))
    return udp, tcp


MONTHS: Dict[str, int] = {
    "Jan": 0, "Feb": 1, "Mar": 2, "Apr": 3, "May": 4, "Jun": 5,
    "Jul": 6, "Aug": 7, "Sep": 8, "Oct": 9, "Nov": 10, "Dec": 11,
}

KEY_VALUE_PATTERN = re.compile(r'(?:^|\s)([A-Za-z_][\w.-]*)=(?:"([^"]*)"|\'([^\']*)\'|(\S+))')


def parse_syslog_message(input_str: str) -> Optional[Dict[str, Any]]:
    original = input_str.strip()
    if not original:
        return None

    priority: Optional[int] = None
    rest = original


    pri_match = re.match(r"^<(\d{1,3})>", rest)
    if pri_match:
        priority = int(pri_match.group(1))
        rest = rest[pri_match.end():]

    timestamp = datetime.now(timezone.utc).isoformat()
    hostname: Optional[str] = None
    message = rest


    rfc5424 = re.match(
        r"^1\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(?:-|\[[^\]]*\])\s*(.*)$",
        rest, re.DOTALL
    )
    if rfc5424:
        timestamp = normalize_timestamp(rfc5424.group(1)) or timestamp
        hostname = rfc5424.group(2) if rfc5424.group(2) != "-" else None
        message = rfc5424.group(6)
    else:

        rfc3164 = re.match(
            r"^([A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+(\S+)\s+(.*)$",
            rest, re.DOTALL
        )
        if rfc3164:
            timestamp = parse_rfc3164_timestamp(rfc3164.group(1)) or timestamp
            hostname = rfc3164.group(2)
            message = rfc3164.group(3)


    fields = parse_key_values(message)
    parsed = {
        **fields,
        "priority": priority,
        "timestamp": timestamp,
        "host": fields.get("host") or hostname,
        "hostname": hostname,
        "message": original,
    }

    if not fields.get("msg"):
        parsed["msg"] = message

    return parsed


def parse_key_values(message: str) -> Dict[str, str]:
    fields: Dict[str, str] = {}
    for match in KEY_VALUE_PATTERN.finditer(message):
        value = match.group(2) or match.group(3) or match.group(4) or ""
        fields[match.group(1)] = value
    return fields


def resolve_syslog_timezone():
    name = str(settings.SYSLOG_TIMEZONE or "UTC").strip()
    if name.lower() == "utc":
        return timezone.utc
    if name.lower() == "local":
        return datetime.now(timezone.utc).astimezone().tzinfo
    try:
        return ZoneInfo(name)
    except Exception as exc:
        logger.warning(
            "invalid SYSLOG_TIMEZONE=%r (%s); falling back to UTC", name, exc
        )
        return timezone.utc


def parse_rfc3164_timestamp(value: str) -> Optional[str]:
    match = re.match(r"^([A-Z][a-z]{2})\s+(\d{1,2})\s+(\d{2}):(\d{2}):(\d{2})$", value)
    if not match:
        return None

    month = MONTHS.get(match.group(1))
    if month is None:
        return None

    now = datetime.now(timezone.utc)
    dt = datetime(
        now.year,
        month + 1,
        int(match.group(2)),
        int(match.group(3)),
        int(match.group(4)),
        int(match.group(5)),
        tzinfo=resolve_syslog_timezone(),
    )


    if dt > datetime.now(timezone.utc) + timedelta(days=1):
        dt = dt.replace(year=dt.year - 1)

    return dt.isoformat()


def normalize_timestamp(value: str) -> Optional[str]:
    if not value or value == "-":
        return None

    try:
        num = float(value)
        ms = num * 1000 if num < 1e12 else num
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()
    except ValueError:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
        except ValueError:
            return None


def syslog_ingest_context() -> Dict[str, Any]:
    return {"tenant": settings.SYSLOG_TENANT, "username": settings.SYSLOG_USERNAME}


async def ingest_parsed(
    session_factory: Callable[[], Any],
    parsed: Dict[str, Any],
    remote: Dict[str, Any],
) -> str:
    """Persist one parsed message, retrying only transient DB failures.

    Returns one of ``persisted``, ``invalid`` or ``dropped``. Validation
    errors are never retried; infrastructure errors get a small bounded
    exponential backoff so a brief database blip does not lose the message.
    """
    from app.services.ingest_service import IngestionService

    event = dict(parsed)
    event.update(remote)
    # Only a message-level ``source=`` field is honored as a declaration;
    # otherwise the source is inferred from the message keys
    # (see infer_source_from_event) rather than forced by SYSLOG_SOURCE.
    source = event.get("source")

    attempts = max(1, int(getattr(settings, "SYSLOG_DB_RETRY_ATTEMPTS", 1)))
    backoff = max(0.0, float(getattr(settings, "SYSLOG_DB_RETRY_BACKOFF_SECS", 0.0)))
    remote_label = remote.get("remoteAddress") or "unknown"

    for attempt in range(1, attempts + 1):
        session = None
        try:
            session = session_factory()
            service = IngestionService(session)
            await service.ingest(
                event,
                source,
                syslog_ingest_context(),
                source_default=settings.SYSLOG_SOURCE,
            )
            syslog_counters.accepted += 1
            return "persisted"
        except ValidationError as exc:
            syslog_counters.invalid += 1
            logger.warning(
                "Dropping invalid syslog message from %s: %s", remote_label, exc.message
            )
            return "invalid"
        except Exception as exc:  # noqa: BLE001 - never let one message kill the listener
            transient = is_transient_db_error(exc)
            if not transient or attempt >= attempts:
                syslog_counters.dropped += 1
                if transient:
                    syslog_counters.retry_exhausted += 1
                logger.error(
                    "Dropping syslog message from %s after %d attempt(s) (transient=%s): %s: %s",
                    remote_label,
                    attempt,
                    transient,
                    type(exc).__name__,
                    exc,
                )
                return "dropped"

            syslog_counters.retried += 1
            delay = backoff * (2 ** (attempt - 1))
            logger.warning(
                "Transient syslog DB failure from %s (attempt %d/%d), retrying in %.2fs: %s: %s",
                remote_label,
                attempt,
                attempts,
                delay,
                type(exc).__name__,
                exc,
            )
            await asyncio.sleep(delay)
        finally:
            if session is not None:
                try:
                    await session.close()
                except Exception:
                    pass

    return "dropped"


class SyslogUDPProtocol(asyncio.DatagramProtocol):

    def __init__(self, session_factory: Callable[[], Any]):
        self.session_factory = session_factory
        self._tasks: "set[asyncio.Task]" = set()
        self._semaphore = asyncio.Semaphore(
            max(1, int(getattr(settings, "SYSLOG_MAX_INFLIGHT", 1)))
        )

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        source_ip = addr[0] if addr else None
        if not is_source_allowed(source_ip):
            syslog_counters.denied += 1
            logger.warning("Rejected syslog UDP datagram from disallowed source %s", source_ip)
            return

        syslog_counters.received += 1
        if self._semaphore.locked():
            syslog_counters.overloaded += 1
            logger.warning(
                "Syslog UDP in-flight limit (%s) reached; dropping datagram from %s",
                getattr(settings, "SYSLOG_MAX_INFLIGHT", 1),
                addr,
            )
            return

        task = asyncio.create_task(self._handle(data, addr))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _handle(self, data: bytes, addr: tuple) -> None:
        async with self._semaphore:
            try:
                message = data.decode("utf-8", errors="replace")
                parsed = parse_syslog_message(message)
                if not parsed:
                    syslog_counters.invalid += 1
                    logger.debug("syslog UDP unparsable datagram from %s", addr)
                    return
                await ingest_parsed(
                    self.session_factory,
                    parsed,
                    {"remoteAddress": addr[0], "remotePort": addr[1]},
                )
            except Exception as exc:
                syslog_counters.dropped += 1
                logger.error("Failed to process syslog UDP from %s: %s", addr, exc)


class SyslogTCPProtocol:

    def __init__(self, session_factory: Callable[[], Any]):
        self.session_factory = session_factory
        self.buffer = ""

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        addr = writer.get_extra_info("peername")
        source_ip = addr[0] if addr else None
        if not is_source_allowed(source_ip):
            syslog_counters.denied += 1
            logger.warning("Rejected syslog TCP connection from disallowed source %s", source_ip)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            return

        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    break

                self.buffer += data.decode("utf-8", errors="replace")
                if len(self.buffer) > MAX_TCP_BUFFER:
                    logger.warning("syslog TCP buffer overflow from %s, dropping", addr)
                    self.buffer = ""
                    break
                await self._process_buffer(addr)


            if self.buffer.strip():
                line, self.buffer = self.buffer, ""
                await self._ingest_line(line, addr)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error("Syslog TCP error from %s: %s", addr, exc)
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def _process_buffer(self, addr: tuple) -> None:
        while True:

            if self.buffer and self.buffer[0].isdigit():
                space_idx = self.buffer.find(" ")
                if space_idx > 0:
                    try:
                        length = int(self.buffer[:space_idx])
                    except ValueError:
                        length = -1
                    if length < 0 or length > MAX_OCTET_LENGTH:

                        pass
                    else:
                        start = space_idx + 1
                        if len(self.buffer) >= start + length:
                            line = self.buffer[start:start + length]
                            self.buffer = self.buffer[start + length:]
                            if line.strip():
                                await self._ingest_line(line, addr)
                            continue


            newline_idx = self.buffer.find("\n")
            if newline_idx >= 0:
                line = self.buffer[:newline_idx].rstrip("\r")
                self.buffer = self.buffer[newline_idx + 1:]
                if line.strip():
                    await self._ingest_line(line, addr)
                continue

            break

    async def _ingest_line(self, line: str, addr: tuple) -> None:
        try:
            parsed = parse_syslog_message(line)
        except Exception as exc:  # noqa: BLE001 - isolate a broken line
            syslog_counters.invalid += 1
            logger.warning("syslog TCP line could not be parsed from %s: %s", addr, exc)
            return
        if not parsed:
            syslog_counters.invalid += 1
            logger.debug("syslog TCP unparsable line from %s", addr)
            return
        syslog_counters.received += 1
        remote = {
            "remoteAddress": addr[0] if addr else None,
            "remotePort": addr[1] if addr and len(addr) > 1 else None,
        }
        await ingest_parsed(self.session_factory, parsed, remote)


async def start_udp_syslog_listener(session_factory: Callable[[], Any]) -> asyncio.DatagramTransport:
    loop = asyncio.get_running_loop()
    bind_ip = str(getattr(settings, "SYSLOG_BIND_IP", "0.0.0.0") or "0.0.0.0")
    transport, _protocol = await loop.create_datagram_endpoint(
        lambda: SyslogUDPProtocol(session_factory),
        local_addr=(bind_ip, settings.SYSLOG_UDP_PORT),
    )
    logger.info("Syslog UDP listener on %s:%s", bind_ip, settings.SYSLOG_UDP_PORT)
    return transport


async def start_tcp_syslog_listener(session_factory: Callable[[], Any]) -> asyncio.Server:
    bind_ip = str(getattr(settings, "SYSLOG_BIND_IP", "0.0.0.0") or "0.0.0.0")
    server = await asyncio.start_server(
        lambda reader, writer: SyslogTCPProtocol(session_factory).handle_client(reader, writer),
        bind_ip,
        settings.SYSLOG_TCP_PORT,
    )
    logger.info("Syslog TCP listener on %s:%s", bind_ip, settings.SYSLOG_TCP_PORT)
    return server
