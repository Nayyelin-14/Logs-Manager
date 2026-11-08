from __future__ import annotations
import asyncio
import logging
import sys
from pathlib import Path
BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
from app.integrations.syslog import (
    start_udp_syslog_listener,
    start_tcp_syslog_listener,
)
from app.core.config import get_settings
from app.core.database import async_session_maker, EFFECTIVE_DB_TARGET
settings = get_settings()
logger = logging.getLogger("ingest.syslog")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
async def main() -> None:
    logger.info("Starting syslog ingest service")
    logger.info("  DB target: %s", EFFECTIVE_DB_TARGET)
    logger.info("  UDP port: %s", settings.SYSLOG_UDP_PORT)
    logger.info("  TCP port: %s", settings.SYSLOG_TCP_PORT)
    logger.info("  Default tenant: %s", settings.SYSLOG_TENANT)
    logger.info("  Default source: %s", settings.SYSLOG_SOURCE)

    udp_transport = None
    tcp_server = None
    try:
        if settings.SYSLOG_UDP_PORT:
            udp_transport = await start_udp_syslog_listener(async_session_maker)
            logger.info("UDP syslog listener started on port %s", settings.SYSLOG_UDP_PORT)
        if settings.SYSLOG_TCP_PORT:
            tcp_server = await start_tcp_syslog_listener(async_session_maker)
            logger.info("TCP syslog listener started on port %s", settings.SYSLOG_TCP_PORT)
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        logger.info("Shutdown signal received")
    finally:
        if tcp_server is not None:
            tcp_server.close()
            await tcp_server.wait_closed()
        if udp_transport is not None:
            udp_transport.close()
        logger.info("Syslog ingest service stopped")

if __name__ == "__main__":
    asyncio.run(main())
