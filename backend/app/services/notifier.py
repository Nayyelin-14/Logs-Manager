from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


DEFAULT_RETRY_DELAYS = (1.0, 2.0, 4.0)
WEBHOOK_TIMEOUT = 5.0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_webhook_payload(
    *,
    alert_id: str,
    rule: dict[str, Any],
    tenant: str,
    severity: str,
    group_value: str,
    count: int,
    window_minutes: int,
    first_seen: str,
    last_seen: str,
    link: str,
) -> dict[str, Any]:
    return {
        "alert_id": alert_id,
        "rule": rule,
        "tenant": tenant,
        "severity": severity,
        "group": group_value,
        "count": count,
        "window": window_minutes,
        "first_seen": first_seen,
        "last_seen": last_seen,
        "link": link,
        "notified_at": _now_iso(),
    }


async def send_webhook(
    *,
    webhook_url: str,
    payload: dict[str, Any],
    retries: int = 3,
    retry_delays: tuple[float, ...] = DEFAULT_RETRY_DELAYS,
    timeout: float = WEBHOOK_TIMEOUT,
) -> list[dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    last_error: Optional[str] = None
    http_code: Optional[int] = None

    for attempt in range(1, retries + 1):
        record: dict[str, Any] = {
            "attempt": attempt,
            "timestamp": _now_iso(),
        }
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(webhook_url, json=payload)
            http_code = resp.status_code
            record["status"] = "sent" if resp.is_success else "failed"
            record["http_code"] = http_code
            record["error"] = None if resp.is_success else resp.text[:500]
            attempts.append(record)
            if resp.is_success:
                logger.info("webhook delivered: url=%s attempt=%d http=%d",
                            webhook_url, attempt, http_code)
                return attempts
            last_error = resp.text[:200]
        except httpx.TimeoutException as exc:
            record["status"] = "failed"
            record["http_code"] = None
            record["error"] = f"timeout: {exc}"
            last_error = f"timeout: {exc}"
            attempts.append(record)
            logger.warning("webhook timeout: url=%s attempt=%d", webhook_url, attempt)
        except Exception as exc:
            record["status"] = "failed"
            record["http_code"] = None
            record["error"] = f"{type(exc).__name__}: {exc}"
            last_error = f"{type(exc).__name__}: {exc}"
            attempts.append(record)
            logger.exception("webhook error: url=%s attempt=%d", webhook_url, attempt)


        if attempt < retries:
            delay = retry_delays[attempt - 1] if attempt - 1 < len(retry_delays) else (2.0 ** attempt)
            import asyncio as _asyncio
            await _asyncio.sleep(delay)

    logger.error("webhook failed after %d retries: url=%s last_error=%s",
                 retries, webhook_url, last_error)
    return attempts


async def send_email(
    *,
    recipient: str,
    subject: str,
    body: str,
    smtp_host: str,
    smtp_port: int,
    smtp_username: Optional[str],
    smtp_password: Optional[str],
    use_tls: bool = True,
) -> dict[str, Any]:
    try:
        import aiosmtplib
        from email.message import EmailMessage

        msg = EmailMessage()
        msg["From"] = smtp_username or "alerts@logmanager.local"
        msg["To"] = recipient
        msg["Subject"] = subject
        msg.set_content(body)

        await aiosmtplib.send(
            msg,
            hostname=smtp_host,
            port=smtp_port,
            username=smtp_username,
            password=smtp_password,
            use_tls=use_tls,
            timeout=10.0,
        )
        return {"status": "sent", "error": None}
    except Exception as exc:
        logger.exception("email send failed to %s", recipient)
        return {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}


def append_notification(
    existing: Optional[list[dict[str, Any]]],
    channel: str,
    attempts: list[dict[str, Any]],
    target: str,
) -> list[dict[str, Any]]:
    notifications = list(existing or [])
    notifications.append({
        "id": uuid.uuid4().hex[:16],
        "channel": channel,
        "target": target,
        "created_at": _now_iso(),
        "attempts": attempts,
        "final_status": attempts[-1]["status"] if attempts else "failed",
    })
    return notifications
