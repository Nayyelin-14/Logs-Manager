"""Local health endpoint for the native Syslog ingest container.

The endpoint binds to loopback only and is consumed by the container
health check. It reports:

* database reachability (``SELECT 1``),
* the state of every *enabled* listener (UDP and/or TCP), and
* in-process ingestion counters.

A socket being open is not enough: if the database is unavailable the
service is reported unhealthy so containers are restarted / taken out of
rotation instead of silently dropping messages.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable, Dict, Optional

logger = logging.getLogger("ingest.health")

DB_CHECK_TIMEOUT_SECONDS = 3.0


async def database_ok(timeout: float = DB_CHECK_TIMEOUT_SECONDS) -> bool:
    from sqlalchemy import text

    from app.core.database import async_session_maker

    try:
        async with async_session_maker() as session:
            await asyncio.wait_for(session.execute(text("SELECT 1")), timeout=timeout)
        return True
    except Exception as exc:  # noqa: BLE001 - health must never raise
        logger.warning("health: database check failed: %s: %s", type(exc).__name__, exc)
        return False


def listener_health(
    runtime: Dict[str, Any],
    udp_enabled: bool,
    tcp_enabled: bool,
) -> Dict[str, bool]:
    udp_transport = runtime.get("udp_transport")
    tcp_server = runtime.get("tcp_server")

    udp_ok = (not udp_enabled) or (
        udp_transport is not None and not udp_transport.is_closing()
    )
    tcp_ok = (not tcp_enabled) or (
        tcp_server is not None and tcp_server.is_serving()
    )
    return {
        "udp_enabled": udp_enabled,
        "tcp_enabled": tcp_enabled,
        "udp": bool(udp_ok),
        "tcp": bool(tcp_ok),
    }


async def build_health_payload(
    runtime: Dict[str, Any],
    udp_enabled: bool,
    tcp_enabled: bool,
    *,
    db_checker: Optional[Callable[[], Awaitable[bool]]] = None,
) -> Dict[str, Any]:
    db_ok = await (db_checker or database_ok)()
    listeners = listener_health(runtime, udp_enabled, tcp_enabled)

    from app.integrations.syslog import syslog_counters

    healthy = db_ok and listeners["udp"] and listeners["tcp"]
    return {
        "status": "ok" if healthy else "unhealthy",
        "database": db_ok,
        "listeners": listeners,
        "counters": syslog_counters.snapshot(),
    }


def health_http_status(payload: Dict[str, Any]) -> int:
    return 200 if payload.get("status") == "ok" else 503


async def start_health_server(
    port: int,
    payload_provider: Callable[[], Awaitable[Dict[str, Any]]],
    host: str = "127.0.0.1",
) -> asyncio.AbstractServer:
    """Start a minimal loopback-only HTTP server exposing ``/healthz``."""

    async def handle(
        reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            request_line = await asyncio.wait_for(reader.readline(), timeout=2)
            while True:
                line = await asyncio.wait_for(reader.readline(), timeout=2)
                if line in (b"\r\n", b"\n", b""):
                    break

            parts = request_line.split()
            path = parts[1].decode("latin-1") if len(parts) > 1 else "/"

            if path != "/healthz":
                status_line = "404 Not Found"
                body = b'{"detail":"not found"}'
            else:
                payload = await payload_provider()
                status_line = (
                    "200 OK"
                    if health_http_status(payload) == 200
                    else "503 Service Unavailable"
                )
                body = json.dumps(payload).encode("utf-8")

            writer.write(
                (
                    f"HTTP/1.1 {status_line}\r\n"
                    "Content-Type: application/json\r\n"
                    f"Content-Length: {len(body)}\r\n"
                    "Connection: close\r\n\r\n"
                ).encode("latin-1")
                + body
            )
            await writer.drain()
        except Exception as exc:  # noqa: BLE001 - a health probe must not crash
            logger.debug("health request failed: %s: %s", type(exc).__name__, exc)
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    server = await asyncio.start_server(handle, host, port)
    logger.info("Health endpoint on http://%s:%s/healthz", host, port)
    return server
