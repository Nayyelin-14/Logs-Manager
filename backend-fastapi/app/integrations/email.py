"""
Email Integration Module

Provides async email sending via aiosmtplib.
"""

import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Any, Dict, NamedTuple, Optional
from aiosmtplib import send
from app.core.config import get_settings
from app.core.templates import (
    render_otp_email,
    render_alert_email,
    render_alert_email_text,
)

settings = get_settings()


class EmailResult(NamedTuple):
    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None


async def send_smtp_email(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: Optional[str] = None
) -> EmailResult:
    """Send email via SMTP with TLS."""
    if not settings.SMTP_ENABLED:
        return EmailResult(False, "SMTP not enabled")
    
    if not all([settings.SMTP_HOST, settings.SMTP_PORT, settings.SMTP_USERNAME, settings.SMTP_PASSWORD]):
        return EmailResult(False, "SMTP not configured")
    
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM_EMAIL or settings.SMTP_USERNAME
    msg["To"] = to_email
    
    if text_body:
        msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))
    
    try:
        tls_context = ssl.create_default_context() if settings.SMTP_USE_TLS else None
        
        await send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USERNAME,
            password=settings.SMTP_PASSWORD,
            start_tls=settings.SMTP_USE_TLS,
            tls_context=tls_context,
            timeout=30,
        )
        
        return EmailResult(True, "Email sent successfully")
        
    except Exception as e:
        import logging
        logging.error(f"SMTP error sending to {to_email}: {e}")
        return EmailResult(False, f"Failed to send email: {type(e).__name__}")


async def send_otp_email(email: str, otp_code: int) -> Dict[str, Any]:
    """Send OTP verification email."""
    html_body = render_otp_email(email, otp_code)
    text_body = f"Your verification code is: {otp_code}\nThis code expires in 2 minutes."
    
    result = await send_smtp_email(
        to_email=email,
        subject="Verify One Time Password",
        html_body=html_body,
        text_body=text_body
    )
    return {"success": result.success, "message": result.message}


async def send_alert_email(
    email: str,
    username: str,
    tenant: str,
    title: str,
    description: str,
    severity: str
) -> Dict[str, Any]:
    """Send alert notification email."""
    severity = str(severity)
    html_body = render_alert_email(username, title, description, severity, tenant)
    text_body = render_alert_email_text(username, title, description, severity, tenant)
    
    subject = f"[ALERT] {title} - Severity: {severity.upper()} at {tenant}"
    
    result = await send_smtp_email(
        to_email=email,
        subject=subject,
        html_body=html_body,
        text_body=text_body
    )
    return {"success": result.success, "message": result.message}