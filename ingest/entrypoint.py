from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

INGEST_DIR = Path(__file__).resolve().parent
BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
for path in (str(BACKEND_DIR), str(INGEST_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from app.integrations.syslog import (  # noqa: E402
    enabled_listeners,
    start_tcp_syslog_listener,
    start_udp_syslog_listener,
    syslog_counters,
)
from app.core.config import get_settings  # noqa: E402
from app.core.database import async_session_maker, EFFECTIVE_DB_TARGET  # noqa: E402
from health import build_health_payload, start_health_server  # noqa: E402

settings = get_settings()
logger = logging.getLogger("ingest.syslog")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


async def start_listeners(session_factory):
    """Start only the listeners that are enabled.

    ``SYSLOG_ENABLED=false`` suppresses both protocols, and a port of ``0``
    disables that protocol individually (used by UDP-only deployments).
    """
    udp_enabled, tcp_enabled = enabled_listeners()

    if not getattr(settings, "SYSLOG_ENABLED", True):
        logger.info("SYSLOG_ENABLED=false; native UDP/TCP listeners are disabled")
        return None, None, udp_enabled, tcp_enabled

    udp_transport = None
    tcp_server = None

    if udp_enabled:
        udp_transport = await start_udp_syslog_listener(session_factory)
        logger.info("UDP syslog listener started on port %s", settings.SYSLOG_UDP_PORT)
    else:
        logger.info("UDP syslog listener disabled")

    if tcp_enabled:
        tcp_server = await start_tcp_syslog_listener(session_factory)
        logger.info("TCP syslog listener started on port %s", settings.SYSLOG_TCP_PORT)
    else:
        logger.info("TCP syslog listener disabled")

    return udp_transport, tcp_server, udp_enabled, tcp_enabled


async def main() -> None:
    logger.info("Starting syslog ingest service")
    logger.info("  DB target: %s", EFFECTIVE_DB_TARGET)
    logger.info("  SYSLOG_ENABLED: %s", settings.SYSLOG_ENABLED)
    logger.info("  UDP port: %s", settings.SYSLOG_UDP_PORT)
    logger.info("  TCP port: %s", settings.SYSLOG_TCP_PORT)
    logger.info("  Bind address: %s", settings.SYSLOG_BIND_IP)
    logger.info("  Default tenant: %s", settings.SYSLOG_TENANT)
    logger.info("  Default source: %s", settings.SYSLOG_SOURCE)

    runtime = {"udp_transport": None, "tcp_server": None}
    health_server = None
    try:
        udp_transport, tcp_server, udp_enabled, tcp_enabled = await start_listeners(
            async_session_maker
        )
        runtime["udp_transport"] = udp_transport
        runtime["tcp_server"] = tcp_server

        health_server = await start_health_server(
            settings.INGEST_HEALTH_PORT,
            lambda: build_health_payload(runtime, udp_enabled, tcp_enabled),
        )

        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        logger.info("Shutdown signal received")
    finally:
        if health_server is not None:
            health_server.close()
            await health_server.wait_closed()
        if runtime["tcp_server"] is not None:
            runtime["tcp_server"].close()
            await runtime["tcp_server"].wait_closed()
        if runtime["udp_transport"] is not None:
            runtime["udp_transport"].close()
        logger.info("Syslog ingest service stopped; counters: %s", syslog_counters.snapshot())


if __name__ == "__main__":
    asyncio.run(main())
