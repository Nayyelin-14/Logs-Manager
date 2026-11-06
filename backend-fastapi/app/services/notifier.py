"""
Alert notifier: webhook delivery with retries + optional SMTP.

Never raises into the alerting engine. Every attempt (status, http code, error,
timestamp) is recorded on the alert's `notifications` JSONB column.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

# Delays (seconds) for the 3 retries: 1s, 2s, 4s. Injectable for tests.
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
    """Build the webhook JSON payload."""
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
    """POST the payload to webhook_url with exponential backoff retries.

    Returns a list of attempt records, each with:
      {attempt, status, http_code, error, timestamp}
    Never raises.
    """
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
        except Exception as exc:  # noqa: BLE001 - never crash the engine
            record["status"] = "failed"
            record["http_code"] = None
            record["error"] = f"{type(exc).__name__}: {exc}"
            last_error = f"{type(exc).__name__}: {exc}"
            attempts.append(record)
            logger.exception("webhook error: url=%s attempt=%d", webhook_url, attempt)

        # Backoff before next retry (skip after the last attempt)
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
    """Send an alert email via SMTP. Returns {status, error}.

    Disabled by default (SMTP_ENABLED=false). Never raises.
    """
    try:
        import aiosmtplib  # type: ignore
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
    except Exception as exc:  # noqa: BLE001
        logger.exception("email send failed to %s", recipient)
        return {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}


def append_notification(
    existing: Optional[list[dict[str, Any]]],
    channel: str,
    attempts: list[dict[str, Any]],
    target: str,
) -> list[dict[str, Any]]:
    """Append a notification record to the alerts.notifications list."""
    notifications = list(existing or [])
    notifications.append({
        "id": uuid.uuid4().hex[:16],
        "channel": channel,          # "webhook" | "email"
        "target": target,
        "created_at": _now_iso(),
        "attempts": attempts,
        "final_status": attempts[-1]["status"] if attempts else "failed",
    })
    return notifications
