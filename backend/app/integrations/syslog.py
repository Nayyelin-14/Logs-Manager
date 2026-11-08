import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Optional
from zoneinfo import ZoneInfo

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

MAX_TCP_BUFFER = 1_048_576
MAX_OCTET_LENGTH = 1_048_576

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
) -> None:
    from app.services.ingest_service import IngestionService

    event = dict(parsed)
    event.update(remote)
    source = event.get("source") or settings.SYSLOG_SOURCE

    session = session_factory()
    try:
        service = IngestionService(session)
        await service.ingest(event, source, syslog_ingest_context())
    finally:
        await session.close()


class SyslogUDPProtocol(asyncio.DatagramProtocol):

    def __init__(self, session_factory: Callable[[], Any]):
        self.session_factory = session_factory
        self._tasks: "set[asyncio.Task]" = set()

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        task = asyncio.create_task(self._handle(data, addr))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _handle(self, data: bytes, addr: tuple) -> None:
        try:
            message = data.decode("utf-8", errors="replace")
            parsed = parse_syslog_message(message)
            if not parsed:
                logger.debug("syslog UDP unparsable datagram from %s", addr)
                return
            await ingest_parsed(
                self.session_factory,
                parsed,
                {"remoteAddress": addr[0], "remotePort": addr[1]},
            )
        except Exception as exc:
            logger.error("Failed to process syslog UDP from %s: %s", addr, exc)


class SyslogTCPProtocol:

    def __init__(self, session_factory: Callable[[], Any]):
        self.session_factory = session_factory
        self.buffer = ""

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        addr = writer.get_extra_info("peername")
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
        parsed = parse_syslog_message(line)
        if not parsed:
            logger.debug("syslog TCP unparsable line from %s", addr)
            return
        remote = {
            "remoteAddress": addr[0] if addr else None,
            "remotePort": addr[1] if addr and len(addr) > 1 else None,
        }
        await ingest_parsed(self.session_factory, parsed, remote)


async def start_udp_syslog_listener(session_factory: Callable[[], Any]) -> asyncio.DatagramTransport:
    loop = asyncio.get_running_loop()
    transport, _protocol = await loop.create_datagram_endpoint(
        lambda: SyslogUDPProtocol(session_factory),
        local_addr=("0.0.0.0", settings.SYSLOG_UDP_PORT),
    )
    logger.info("Syslog UDP listener on 0.0.0.0:%s", settings.SYSLOG_UDP_PORT)
    return transport


async def start_tcp_syslog_listener(session_factory: Callable[[], Any]) -> asyncio.Server:
    server = await asyncio.start_server(
        lambda reader, writer: SyslogTCPProtocol(session_factory).handle_client(reader, writer),
        "0.0.0.0",
        settings.SYSLOG_TCP_PORT,
    )
    logger.info("Syslog TCP listener on 0.0.0.0:%s", settings.SYSLOG_TCP_PORT)
    return server
