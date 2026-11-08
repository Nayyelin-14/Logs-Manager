from __future__ import annotations
import ssl
import urllib.parse
from typing import Any
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

def ssl_setting_from_url(database_url: str) -> Any:
    parsed = urllib.parse.urlparse(database_url)
    query_params = urllib.parse.parse_qs(parsed.query)
    sslmode = (query_params.get("sslmode", ["disable"])[0] or "disable").lower()

    if sslmode in ("disable", "allow", "prefer", ""):
        return False
    if sslmode == "require":
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    if sslmode == "verify-ca":
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_REQUIRED
        return ctx
    if sslmode == "verify-full":
        ctx = ssl.create_default_context()
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED
        return ctx
    return False
def describe_database_target(database_url: str) -> str:
    parsed = urllib.parse.urlparse(database_url)
    query_params = urllib.parse.parse_qs(parsed.query)
    sslmode = (query_params.get("sslmode", ["disable"])[0] or "disable").lower()
    host = parsed.hostname or "<unset>"
    port = parsed.port or 5432
    database = (parsed.path or "/").lstrip("/") or "<unset>"
    return f"host={host} port={port} database={database} sslmode={sslmode} ssl={'off' if sslmode in ('disable','allow','prefer','') else 'on'}"
def build_engine_args(database_url: str) -> dict:

    parsed = urllib.parse.urlparse(database_url)
    query_params = urllib.parse.parse_qs(parsed.query)
    clean_query = {
        k: v for k, v in query_params.items()
        if k not in ("sslmode", "channel_binding", "ssl")
    }
    clean_query_str = urllib.parse.urlencode(clean_query, doseq=True)
    clean_url = urllib.parse.urlunparse((
        parsed.scheme, parsed.netloc, parsed.path, parsed.params,
        clean_query_str, parsed.fragment,
    ))
    return {
        "url": clean_url,
        "connect_args": {"ssl": ssl_setting_from_url(database_url)},
    }
def create_engine(database_url: str, **kwargs) -> AsyncEngine:
    args = build_engine_args(database_url)
    return create_async_engine(
        args["url"],
        connect_args=args["connect_args"],
        **kwargs,
    )
