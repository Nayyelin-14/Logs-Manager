from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


DEFAULT_RETRY_DELAYS = (1.0, 2.0, 4.0)
WEBHOOK_TIMEOUT = 5.0


def _resolve_retry_delays(retry_delays: tuple[float, ...] | None) -> tuple[float, ...]:
    if retry_delays is not None:
        return retry_delays
    raw = os.environ.get("WEBHOOK_RETRY_DELAYS")
    if not raw:
        return DEFAULT_RETRY_DELAYS
    try:
        parsed = tuple(float(part.strip()) for part in raw.split(",") if part.strip())
    except ValueError:
        return DEFAULT_RETRY_DELAYS
    if not parsed or any(delay < 0 for delay in parsed):
        return DEFAULT_RETRY_DELAYS
    return parsed


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
    retry_delays: tuple[float, ...] | None = None,
    timeout: float = WEBHOOK_TIMEOUT,
) -> list[dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    last_error: Optional[str] = None
    http_code: Optional[int] = None
    delays = _resolve_retry_delays(retry_delays)

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
            delay = delays[attempt - 1] if attempt - 1 < len(delays) else (2.0 ** attempt)
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


RESEND_API_URL = "https://api.resend.com/emails"
RESEND_TIMEOUT = 10.0


def is_valid_email(address: Optional[str]) -> bool:
    if not address or not isinstance(address, str):
        return False
    address = address.strip()
    if not address or "@" not in address or " " in address:
        return False
    local, _, domain = address.rpartition("@")
    return bool(local) and bool(domain) and "." in domain


async def send_resend_email(
    *,
    recipient: str,
    subject: str,
    html_body: Optional[str] = None,
    text_body: Optional[str] = None,
    from_email: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout: float = RESEND_TIMEOUT,
    transport: Any = None,
) -> dict[str, Any]:
    """Send a transactional email via the Resend HTTPS API.

    Returns a dict with ``status`` ("sent"/"failed"), an optional ``error``,
    and an optional ``message_id`` when the provider accepts the message.
    Does not log the API key or recipient body content.
    """
    if not api_key:
        return {"status": "failed", "error": "missing_resend_api_key"}
    if not is_valid_email(recipient):
        return {"status": "failed", "error": "invalid_recipient"}
    if not is_valid_email(from_email):
        return {"status": "failed", "error": "invalid_sender"}
    if not html_body and not text_body:
        return {"status": "failed", "error": "empty_body"}

    payload: dict[str, Any] = {
        "from": from_email,
        "to": [recipient],
        "subject": subject,
    }
    if html_body:
        payload["html"] = html_body
    if text_body:
        payload["text"] = text_body

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=timeout, transport=transport) as client:
            resp = await client.post(RESEND_API_URL, json=payload, headers=headers)
        if resp.is_success:
            data = resp.json() or {}
            message_id = data.get("id")
            logger.info(
                "resend email accepted: recipient=%s status=%s message_id=%s",
                recipient,
                resp.status_code,
                message_id,
            )
            return {"status": "sent", "error": None, "message_id": message_id}
        logger.error(
            "resend email rejected: recipient=%s http=%d error=%s",
            recipient,
            resp.status_code,
            resp.text[:200],
        )
        return {
            "status": "failed",
            "error": f"http_{resp.status_code}: {resp.text[:200]}",
        }
    except httpx.TimeoutException as exc:
        logger.warning("resend email timeout: recipient=%s", recipient)
        return {"status": "failed", "error": f"timeout: {type(exc).__name__}"}
    except Exception as exc:  # noqa: BLE001 - never crash notification flow
        logger.exception("resend email error: recipient=%s", recipient)
        return {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}


async def send_email_notification(
    *,
    recipient: str,
    subject: str,
    html_body: Optional[str] = None,
    text_body: Optional[str] = None,
) -> dict[str, Any]:
    """Dispatch an alert email through the configured provider.

    Routes to Resend when ``EMAIL_PROVIDER=resend`` and settings are present,
    otherwise falls back to SMTP. Returns a provider-neutral result dict.
    Email is disabled when no provider is configured.
    """
    settings = get_settings()

    if not settings.EMAIL_ENABLED:
        return {"status": "skipped", "error": "email_disabled"}

    if settings.EMAIL_PROVIDER == "resend":
        return await send_resend_email(
            recipient=recipient,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            from_email=settings.ALERT_EMAIL_FROM,
            api_key=settings.RESEND_API_KEY,
        )

    # SMTP fallback (existing behaviour)
    return await send_email(
        recipient=recipient,
        subject=subject,
        body=html_body or text_body or subject,
        smtp_host=settings.SMTP_HOST or "",
        smtp_port=settings.SMTP_PORT,
        smtp_username=settings.SMTP_USERNAME,
        smtp_password=settings.SMTP_PASSWORD,
        use_tls=settings.SMTP_USE_TLS,
    )
