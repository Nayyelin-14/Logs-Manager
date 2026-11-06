# Worker and Email Architecture Design

**Version:** 1.0  
**Date:** 2026-11-03  
**Status:** Design Phase

---

## 1. Background Job System Selection: `arq`

### 1.1 Why `arq`?

| Criterion | `arq` | Dramatiq | Celery | BullMQ (current) |
|-----------|-------|----------|--------|------------------|
| **Async Native** | ✅ | ✅ | ⚠️ (prefork) | ✅ (Node) |
| **Redis Only** | ✅ | ✅ | ❌ (needs broker) | ✅ |
| **Retry/Backoff** | ✅ Built-in | ✅ Built-in | ✅ Built-in | ✅ Built-in |
| **Job Timeout** | ✅ | ✅ | ✅ | ✅ |
| **Cron Jobs** | ✅ (via `arq.cron`) | ❌ (needs apscheduler) | ✅ (beat) | ✅ (node-cron) |
| **Deployment** | Single Python process | Single Python process | Multiple processes | Node process |
| **Dependencies** | `redis`, `msgpack` | `redis`, `dramatiq` | `celery`, `redis/rabbitmq` | `bullmq`, `ioredis` |
| **Monitoring** | Basic | Dashboard available | Flower | Bull Board |

**Decision:** `arq` — simplest deployment, async-native, Redis-only, built-in cron, used in production FastAPI apps.

### 1.2 `arq` Architecture

```
┌─────────────────┐     Redis      ┌─────────────────┐
│   API Server    │ ◄─────────────► │  arq Workers    │
│  (enqueues jobs)│   Queues       │ (execute jobs)  │
└─────────────────┘                └─────────────────┘
        │                                  │
        │                                  ├── email_worker.py
        │                                  ├── retention_worker.py
        │                                  └── cache_worker.py
        ▼
   PostgreSQL
```

---

## 2. Queue Definitions

### 2.1 Queue Configuration (`app/integrations/queue.py`)

```python
# app/integrations/queue.py
import os
from arq import create_pool
from arq.connections import RedisSettings
from app.core.config import settings

# Redis connection pool for enqueueing
async def get_redis_pool():
    return await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))

# Job definitions for workers
class JobDefs:
    # Email queue
    OTP_EMAIL = "otp_email"
    ALERT_EMAIL = "alert_email"
    
    # Cache invalidation
    INVALIDATE_LOG_CACHE = "invalidate_log_cache"
    INVALIDATE_RULE_CACHE = "invalidate_rule_cache"

# Enqueue functions (called from API/services)
async def enqueue_otp_email(email: str, otp_code: int, otp_id: int):
    pool = await get_redis_pool()
    await pool.enqueue_job(
        JobDefs.OTP_EMAIL,
        email=email,
        otp_code=otp_code,
        otp_id=otp_id,
        _job_id=f"OTP:{otp_id}:email",
        _queue_name="email_queue",
    )

async def enqueue_alert_email(
    email: str,
    username: str,
    tenant: str,
    title: str,
    description: str,
    severity: str
):
    pool = await get_redis_pool()
    await pool.enqueue_job(
        JobDefs.ALERT_EMAIL,
        email=email,
        username=username,
        tenant=tenant,
        title=title,
        description=description,
        severity=severity,
        _job_id=f"ALERT:{tenant}:{int(time.time())}",
        _queue_name="email_queue",
    )

async def enqueue_cache_invalidation(pattern: str, queue: str = "cache_invalidation"):
    pool = await get_redis_pool()
    await pool.enqueue_job(
        "invalidate_cache",
        pattern=pattern,
        _job_id=f"cache:{pattern}:{int(time.time())}",
        _queue_name=queue,
    )
```

### 2.2 Worker Settings (`app/workers/email_worker.py`)

```python
# app/workers/email_worker.py
import time
from arq import Worker
from arq.connections import RedisSettings
from app.integrations.email import send_otp_email, send_alert_email
from app.core.config import settings

async def otp_email_job(ctx, email: str, otp_code: int, otp_id: int):
    """Send OTP email with retry."""
    result = await send_otp_email(email, otp_code)
    if not result["success"]:
        raise Exception(result["message"])  # Triggers retry
    return result

async def alert_email_job(ctx, email: str, username: str, tenant: str, 
                          title: str, description: str, severity: str):
    """Send alert email with retry."""
    result = await send_alert_email(email, username, tenant, title, description, severity)
    if not result["success"]:
        raise Exception(result["message"])  # Triggers retry
    return result

# Worker configuration
class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    functions = [otp_email_job, alert_email_job]
    queue_name = "email_queue"
    max_jobs = 10
    job_timeout = 60  # seconds
    keep_result = 3600  # 1 hour
    max_tries = 3
    retry_delay = 5  # Base delay, exponential backoff handled by arq
    
    # Cron jobs (optional - can run retention here too)
    # cron_jobs = [
    #     cron(run_retention_cleanup, hour=5, minute=0),
    # ]

def create_worker() -> Worker:
    return Worker(WorkerSettings)
```

---

## 3. Email Integration (`app/integrations/email.py`)

### 3.1 SMTP Configuration

```python
# app/integrations/email.py
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from aiosmtplib import send
from app.core.config import settings
from app.core.templates import render_otp_email, render_alert_email

class EmailResult:
    def __init__(self, success: bool, message: str, details: dict = None):
        self.success = success
        self.message = message
        self.details = details or {}

async def send_smtp_email(to_email: str, subject: str, html_body: str, text_body: str = None) -> EmailResult:
    """Send email via SMTP with TLS."""
    # Master SMTP switch
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
        # Use aiosmtplib for async sending
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
        # Log full error for debugging, return sanitized message
        import logging
        logging.error(f"SMTP error sending to {to_email}: {e}")
        return EmailResult(False, f"Failed to send email: {type(e).__name__}")

async def send_otp_email(email: str, otp_code: int) -> dict:
    """Send OTP email if OTP_EMAIL_ENABLED."""
    if not settings.OTP_EMAIL_ENABLED:
        return {"success": False, "message": "OTP email disabled"}
    
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
) -> dict:
    """Send alert email if ALERT_EMAIL_ENABLED."""
    if not settings.ALERT_EMAIL_ENABLED:
        return {"success": False, "message": "Alert email disabled"}
    
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
```

# send_otp_email and send_alert_email are defined above with feature toggles
```

### 3.2 Email Templates (`app/core/templates.py`)

```python
# app/core/templates.py
# Ported from backend/src/emailTemplates.ts/

def render_otp_email(email: str, otp_code: int) -> str:
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Verify OTP</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f9f9f9; margin: 0; padding: 20px;">
    <div style="max-width: 480px; margin: 0 auto; background: white; border-radius: 8px; border: 1px solid #ddd; padding: 20px;">
        <h2 style="color: #333; margin-top: 0;">Verify One Time Password</h2>
        <p>Hello <strong>{email}</strong>,</p>
        <p>Your verification code is:</p>
        <div style="text-align: center; margin: 24px 0;">
            <span style="font-size: 32px; font-weight: bold; letter-spacing: 4px; color: #0066cc; font-family: monospace;">{otp_code}</span>
        </div>
        <p style="color: #666; font-size: 14px;">This code expires in <strong>2 minutes</strong>.</p>
        <p>If you didn't request this, please ignore this email.</p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="color: #999; font-size: 12px;">Log Manager Security System</p>
    </div>
</body>
</html>
"""

def render_alert_email(username: str, title: str, description: str, severity: str, tenant: str) -> str:
    severity_colors = {
        "low": "#28a745",
        "medium": "#ffc107",
        "high": "#dc3545",
        "critical": "#8B0000",
    }
    color = severity_colors.get(severity.lower(), "#007bff")
    
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Alert Notification</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f9f9f9; margin: 0; padding: 20px;">
    <div style="max-width: 480px; margin: 0 auto; background: white; border-radius: 8px; border: 1px solid #ddd; padding: 20px;">
        <p>Hello <strong>{username}</strong>,</p>
        
        <div style="display: inline-block; padding: 6px 12px; border-radius: 6px; background-color: {color}; color: white; font-weight: bold; font-size: 12px; margin-bottom: 16px;">
            {severity.upper()}
        </div>
        
        <h2 style="font-size: 20px; font-weight: bold; color: {color}; margin: 12px 0;">{title}</h2>
        <p style="font-size: 14px; line-height: 1.5; margin: 8px 0 16px 0;">{description}</p>
        
        <p>Tenant: <strong>{tenant}</strong></p>
        <p>Please review this alert in the Log Manager dashboard.</p>
        
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="color: #999; font-size: 12px;">Log Manager Security System</p>
    </div>
</body>
</html>
"""

def render_alert_email_text(username: str, title: str, description: str, severity: str, tenant: str) -> str:
    return f"""
Hello {username},

A security alert has been triggered.

Alert: {title}
Severity: {severity.upper()}
Tenant: {tenant}

{description}

Please review this alert in the Log Manager dashboard.

---
Log Manager Security System
"""
```

---

## 4. Email Notification Tracking (New Feature)

### 4.1 Database Model Addition

```python
# app/models/email_notification.py
from sqlalchemy import Column, String, DateTime, Enum as SQLEnum, Text, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from app.models.base import Base
import enum

class EmailType(str, enum.Enum):
    ALERT = "alert"
    OTP = "otp"

class EmailStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    RETRYING = "retrying"

class EmailNotification(Base):
    __tablename__ = "email_notifications"
    
    # Stable notification ID (primary key): alert:{alert_id}:type:{email_type}:to:{recipient_email}
    # e.g., alert:abc123:type:alert:to:user@example.com
    #      otp:type:otp:to:user@example.com
    id = Column(String(150), primary_key=True)
    
    alert_id = Column(String(25), ForeignKey("alerts.id"), nullable=True)
    email_type = Column(SQLEnum(EmailType, name="EmailType", native_enum=True), nullable=False)
    tenant = Column(String(100), nullable=False)
    recipient_email = Column(String(255), nullable=False)
    subject = Column(String(500), nullable=False)
    status = Column(SQLEnum(EmailStatus, name="EmailStatus", native_enum=True), default=EmailStatus.PENDING)
    attempts = Column(Integer, default=0)
    last_attempt_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default="now()", nullable=False)
    
    # Unique constraint matching stable ID components (alert_id, email_type, recipient_email)
    # Primary key already enforces uniqueness; this constraint supports queries and explicit intent
    __table_args__ = (
        UniqueConstraint('alert_id', 'email_type', 'recipient_email', name='uq_email_notification_alert_type_recipient'),
        Index('ix_email_notifications_tenant_status', 'tenant', 'status'),
        Index('ix_email_notifications_alert_id', 'alert_id'),
        Index('ix_email_notifications_created_at', 'created_at'),
    )
```

**Key idempotency features:**
- **Stable primary key**: `alert:{alert_id}:type:{email_type}:to:{recipient_email}` (or `otp:type:otp:to:{recipient_email}`) prevents duplicate records on retry
- **Unique constraint** on `(alert_id, email_type, recipient_email)` matches stable key components and supports queries
- Worker retries update existing record (via stable PK) rather than creating new ones
- `email_type` column distinguishes alert vs OTP notifications for the same alert/recipient

### 4.2 Tracking in Email Worker

```python
# app/workers/email_worker.py (updated)
from app.models.email_notification import EmailNotification, EmailStatus
from app.core.database import get_session
import time

def build_notification_id(alert_id: str | None, email_type: str, recipient_email: str) -> str:
    """Build stable notification ID for idempotency."""
    if alert_id:
        return f"alert:{alert_id}:type:{email_type}:to:{recipient_email}"
    return f"otp:{email_type}:to:{recipient_email}"

async def alert_email_job(ctx, email: str, username: str, tenant: str, 
                          title: str, description: str, severity: str,
                          alert_id: str = None):
    """Send alert email with idempotent tracking."""
    session = get_session()
    notification_id = build_notification_id(alert_id, "alert", email)
    
    # Upsert notification record (idempotent on retries)
    notification = await session.get(EmailNotification, notification_id)
    if not notification:
        notification = EmailNotification(
            id=notification_id,
            alert_id=alert_id,
            tenant=tenant,
            recipient_email=email,
            subject=f"[ALERT] {title} - Severity: {severity.upper()} at {tenant}",
            status=EmailStatus.PENDING,
            attempts=0,
        )
        session.add(notification)
    
    # Update attempt tracking
    notification.status = EmailStatus.RETRYING
    notification.attempts += 1
    notification.last_attempt_at = datetime.now(timezone.utc)
    await session.commit()
    
    try:
        result = await send_alert_email(email, username, tenant, title, description, severity)
        
        if result["success"]:
            notification.status = EmailStatus.SENT
            notification.sent_at = datetime.now(timezone.utc)
            notification.last_error = None
        else:
            notification.status = EmailStatus.FAILED
            notification.last_error = result["message"]
        
        await session.commit()
        return {"success": result.success, "message": result.message}
        
    except Exception as e:
        notification.status = EmailStatus.FAILED
        notification.last_error = str(e)
        await session.commit()
        raise  # Triggers arq retry (updates existing record)

async def otp_email_job(ctx, email: str, otp_code: int, otp_id: int):
    """Send OTP email with idempotent tracking."""
    session = get_session()
    notification_id = build_notification_id(None, "otp", email)
    
    notification = await session.get(EmailNotification, notification_id)
    if not notification:
        notification = EmailNotification(
            id=notification_id,
            alert_id=None,
            tenant="system",
            recipient_email=email,
            subject="Verify One Time Password",
            status=EmailStatus.PENDING,
            attempts=0,
        )
        session.add(notification)
    
    notification.status = EmailStatus.RETRYING
    notification.attempts += 1
    notification.last_attempt_at = datetime.now(timezone.utc)
    await session.commit()
    
    try:
        result = await send_otp_email(email, otp_code)
        
        if result["success"]:
            notification.status = EmailStatus.SENT
            notification.sent_at = datetime.now(timezone.utc)
            notification.last_error = None
        else:
            notification.status = EmailStatus.FAILED
            notification.last_error = result["message"]
        
        await session.commit()
        return {"success": result.success, "message": result.message}
        
    except Exception as e:
        notification.status = EmailStatus.FAILED
        notification.last_error = str(e)
        await session.commit()
        raise
```

**Idempotency guarantees:**
- Stable `notification_id` ensures retries update the same record
- Unique constraint prevents duplicate alert notifications per recipient
- Alert creation succeeds independently of SMTP delivery (notification created asynchronously)

### 4.3 Preventing Duplicate Emails

Idempotency is enforced at three levels:

1. **Alert deduplication**: Existing alert `dedupeKey` + cooldown window prevents duplicate alerts
2. **Notification stable ID**: `alert:{alert_id}:type:{email_type}:to:{recipient_email}` (or `otp:type:otp:to:{recipient_email}`) ensures retries update same record
3. **Database unique constraint**: `(alert_id, email_type, recipient_email)` matches stable ID components and prevents duplicate notification records per alert per recipient per type

Alert creation succeeds independently of SMTP delivery. Notification records are created/updated asynchronously.

---

## 5. Retention Worker (`app/workers/retention_worker.py`)

### 5.1 APScheduler Integration

```python
# app/workers/retention_worker.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app.services.retention_service import cleanup_old_logs
from app.core.config import settings
from app.core.database import get_session_factory
import logging

logger = logging.getLogger(__name__)

async def run_retention_cleanup():
    """Scheduled job: delete events older than RETENTION_DAYS based on ingested_at."""
    try:
        async with get_session_factory()() as session:
            deleted_count = await cleanup_old_logs(
                session,
                days=settings.RETENTION_DAYS,
                timestamp_field="ingested_at"  # Uses ingested_at, not original timestamp
            )
            logger.info(f"Retention cleanup: deleted {deleted_count} events older than {settings.RETENTION_DAYS} days")
    except Exception as e:
        logger.error(f"Retention cleanup failed: {e}")
        # Don't raise - let scheduler continue

def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    
    # Parse cron expression from settings (default: "0 5 * * *" = 05:00 daily)
    cron_parts = settings.RETENTION_SCHEDULE.split()
    if len(cron_parts) == 5:
        minute, hour, day, month, dow = cron_parts
        trigger = CronTrigger(
            minute=minute, hour=hour, day=day, month=month, day_of_week=dow, timezone="UTC"
        )
    else:
        trigger = CronTrigger(hour=5, minute=0, timezone="UTC")
    
    scheduler.add_job(
        run_retention_cleanup,
        trigger=trigger,
        id="retention_cleanup",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,  # 1 hour grace
    )
    
    return scheduler

async def main():
    scheduler = create_scheduler()
    scheduler.start()
    logger.info("Retention worker started")
    
    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        scheduler.shutdown()
        logger.info("Retention worker stopped")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

### 5.2 Retention Service

```python
# app/services/retention_service.py
from sqlalchemy import delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.security_event import SecurityEvent
from datetime import datetime, timedelta, timezone

async def cleanup_old_logs(
    session: AsyncSession,
    days: int = 7,
    timestamp_field: str = "ingested_at"
) -> int:
    """
    Delete SecurityEvent records older than `days` based on `timestamp_field`.
    
    Uses ingested_at (when event was ingested) not original timestamp.
    This ensures sample data with old timestamps doesn't cause new events to be deleted.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Build dynamic column reference
    column = getattr(SecurityEvent, timestamp_field)
    
    stmt = delete(SecurityEvent).where(column < cutoff)
    result = await session.execute(stmt)
    await session.commit()
    
    return result.rowcount
```

---

## 6. Cache Invalidation Worker (`app/workers/cache_worker.py`)

```python
# app/workers/cache_worker.py
from arq import Worker
from arq.connections import RedisSettings
from app.core.config import settings
from app.core.database import get_redis_pool

async def invalidate_cache(ctx, pattern: str):
    """Invalidate Redis keys matching pattern using SCAN."""
    redis = await get_redis_pool()
    
    deleted = 0
    async for key in redis.scan_iter(match=pattern, count=100):
        await redis.delete(key)
        deleted += 1
    
    return {"pattern": pattern, "deleted": deleted}

class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    functions = [invalidate_cache]
    queue_name = "cache_invalidation"
    max_jobs = 5
    job_timeout = 30

def create_worker() -> Worker:
    return Worker(WorkerSettings)
```

---

## 7. Syslog Listeners (Asyncio)

### 7.1 UDP Listener (`app/integrations/syslog.py`)

```python
# app/integrations/syslog.py
import asyncio
import socket
from app.services.ingest_service import IngestService
from app.core.config import settings
from app.parsers.router import NormalizationService
import logging

logger = logging.getLogger(__name__)

class SyslogUDPProtocol(asyncio.DatagramProtocol):
    def __init__(self, ingest_service: IngestService):
        self.ingest_service = ingest_service
    
    def datagram_received(self, data: bytes, addr: tuple):
        try:
            message = data.decode("utf-8", errors="replace")
            parsed = parse_syslog_message(message)
            if parsed:
                parsed["remote_address"] = addr[0]
                parsed["remote_port"] = addr[1]
                
                # Fire and forget - don't block UDP
                asyncio.create_task(
                    self.ingest_service.ingest(
                        parsed,
                        parsed.get("source") or settings.SYSLOG_SOURCE,
                        {"tenant": settings.SYSLOG_TENANT, "username": settings.SYSLOG_USERNAME}
                    )
                )
        except Exception as e:
            logger.error(f"Failed to process syslog UDP from {addr}: {e}")

async def start_udp_syslog_listener(ingest_service: IngestService):
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: SyslogUDPProtocol(ingest_service),
        local_addr=("0.0.0.0", settings.SYSLOG_UDP_PORT),
    )
    logger.info(f"Syslog UDP listener on 0.0.0.0:{settings.SYSLOG_UDP_PORT}")
    return transport
```

### 7.2 TCP Listener (`app/integrations/syslog.py`)

```python
# app/integrations/syslog.py (continued)
class SyslogTCPProtocol:
    def __init__(self, ingest_service: IngestService):
        self.ingest_service = ingest_service
        self.buffer = ""
    
    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr = writer.get_extra_info("peername")
        logger.debug(f"Syslog TCP connection from {addr}")
        
        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    break
                
                self.buffer += data.decode("utf-8", errors="replace")
                await self._process_buffer(addr)
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Syslog TCP error from {addr}: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
    
    async def _process_buffer(self, addr: tuple):
        # Handle both octet-counted framing and newline-delimited
        while True:
            # Try octet framing: <length> <message>\n
            if self.buffer and self.buffer[0].isdigit():
                space_idx = self.buffer.find(" ")
                if space_idx > 0:
                    try:
                        length = int(self.buffer[:space_idx])
                        msg_start = space_idx + 1
                        if len(self.buffer) >= msg_start + length:
                            line = self.buffer[msg_start:msg_start + length]
                            self.buffer = self.buffer[msg_start + length:]
                            await self._ingest_line(line, addr)
                            continue
                    except ValueError:
                        pass
            
            # Fallback: newline delimited
            newline_idx = self.buffer.find("\n")
            if newline_idx >= 0:
                line = self.buffer[:newline_idx].rstrip("\r")
                self.buffer = self.buffer[newline_idx + 1:]
                if line.strip():
                    await self._ingest_line(line, addr)
                continue
            
            break  # Need more data
    
    async def _ingest_line(self, line: str, addr: tuple):
        parsed = parse_syslog_message(line)
        if parsed:
            parsed["remote_address"] = addr[0]
            parsed["remote_port"] = addr[1]
            await self.ingest_service.ingest(
                parsed,
                parsed.get("source") or settings.SYSLOG_SOURCE,
                {"tenant": settings.SYSLOG_TENANT, "username": settings.SYSLOG_USERNAME}
            )

async def start_tcp_syslog_listener(ingest_service: IngestService):
    protocol = SyslogTCPProtocol(ingest_service)
    server = await asyncio.start_server(
        protocol.handle_client,
        "0.0.0.0",
        settings.SYSLOG_TCP_PORT,
    )
    logger.info(f"Syslog TCP listener on 0.0.0.0:{settings.SYSLOG_TCP_PORT}")
    return server
```

### 7.3 Syslog Parsing (Ported from the Legacy Backend)

```python
# app/integrations/syslog.py (parsing functions)
import re
from datetime import datetime, timezone

MONTHS = {
    "Jan": 0, "Feb": 1, "Mar": 2, "Apr": 3, "May": 4, "Jun": 5,
    "Jul": 6, "Aug": 7, "Sep": 8, "Oct": 9, "Nov": 10, "Dec": 11,
}

KEY_VALUE_PATTERN = re.compile(r'(?:^|\s)([A-Za-z_][\w.-]*)=(?:"([^"]*)"|\'([^\']*)\'|(\S+))')

def parse_syslog_message(input_str: str) -> dict | None:
    original = input_str.strip()
    if not original:
        return None
    
    priority = None
    rest = original
    
    # Parse PRI
    pri_match = re.match(r"^<(\d{1,3})>", rest)
    if pri_match:
        priority = int(pri_match.group(1))
        rest = rest[pri_match.end():]
    
    timestamp = datetime.now(timezone.utc).isoformat()
    hostname = None
    message = rest
    
    # Try RFC5424
    rfc5424 = re.match(r"^1\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(?:-|\[[^\]]*\])\s*(.*)$", rest, re.DOTALL)
    if rfc5424:
        timestamp = normalize_timestamp(rfc5424.group(1)) or timestamp
        hostname = rfc5424.group(2) if rfc5424.group(2) != "-" else None
        message = rfc5424.group(6)
    else:
        # Try RFC3164
        rfc3164 = re.match(r"^([A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+(\S+)\s+(.*)$", rest, re.DOTALL)
        if rfc3164:
            timestamp = parse_rfc3164_timestamp(rfc3164.group(1)) or timestamp
            hostname = rfc3164.group(2)
            message = rfc3164.group(3)
    
    # Extract key-value pairs
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

def parse_key_values(message: str) -> dict:
    fields = {}
    for match in KEY_VALUE_PATTERN.finditer(message):
        value = match.group(2) or match.group(3) or match.group(4) or ""
        fields[match.group(1)] = value
    return fields

def parse_rfc3164_timestamp(value: str) -> str | None:
    match = re.match(r"^([A-Z][a-z]{2})\s+(\d{1,2})\s+(\d{2}):(\d{2}):(\d{2})$", value)
    if not match:
        return None
    
    month = MONTHS.get(match.group(1))
    if month is None:
        return None
    
    now = datetime.now(timezone.utc)
    dt = datetime(now.year, month + 1, int(match.group(2)), int(match.group(3)), int(match.group(4)), int(match.group(5)), tzinfo=timezone.utc)
    
    # Handle year rollover
    if dt > datetime.now(timezone.utc) + timedelta(days=1):
        dt = dt.replace(year=dt.year - 1)
    
    return dt.isoformat()

def normalize_timestamp(value: str) -> str | None:
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
```

---

## 8. Worker Deployment (Docker)

### 8.1 Dockerfile (Multi-stage)

```dockerfile
# backend/Dockerfile
FROM python:3.12-slim AS base
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && rm -rf /var/lib/apt/lists/*

FROM base AS deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM base AS runtime
COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin
COPY . .
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 4500 5514/udp 5514/tcp
```

### 8.2 No Separate Worker Processes (FastAPI)

FastAPI runs all background work in-process; there are **no separate worker containers** in `backend-fastapi/docker-compose.yml`.

- **Retention**: Runs via APScheduler inside the main FastAPI application (`app/services/retention.py`), triggered by cron schedule `0 5 * * *` (daily at 05:00 UTC). No separate `retention-worker` service.
- **Email**: Alert/OTP emails are enqueued to Redis via `arq` but **no worker process runs** by default (`SMTP_ENABLED=false`). Emails are queued but never consumed or delivered unless an explicit worker is added. The `email_notifications` table tracks status.
- **Cache invalidation**: Enqueued as `arq` jobs; no consumer process exists. Cache invalidation is currently a no-op since no code reads a cached response.

This simplifies deployment (single backend container) and operations.

---

## 9. Graceful Shutdown

```python
# app/workers/email_worker.py (shutdown handling)
import signal
import asyncio
from arq import Worker

class GracefulWorker(Worker):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._shutdown = False
    
    async def start(self):
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._handle_shutdown)
        await super().start()
    
    def _handle_shutdown(self):
        self._shutdown = True
        logger.info("Shutdown signal received, finishing current job...")
    
    async def run_job(self, *args, **kwargs):
        if self._shutdown:
            raise RuntimeError("Worker shutting down")
        return await super().run_job(*args, **kwargs)
```

---

## 10. Monitoring & Observability

### 10.1 Structured Logging

```python
# app/core/logging.py
import structlog
import logging

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()
```

### 10.2 Key Metrics to Log

| Event | Log Fields |
|-------|------------|
| Email sent | `event=email_sent`, `tenant`, `recipient`, `alert_id`, `duration_ms` |
| Email failed | `event=email_failed`, `tenant`, `recipient`, `alert_id`, `error`, `attempt` |
| Retention cleanup | `event=retention_cleanup`, `deleted_count`, `duration_ms` |
| Cache invalidated | `event=cache_invalidated`, `pattern`, `deleted_count` |
| Syslog received | `event=syslog_received`, `protocol`, `remote_addr`, `source` |
| Alert triggered | `event=alert_triggered`, `rule_id`, `tenant`, `severity`, `event_ids` |

---

## 11. Testing Workers

```python
# tests/test_workers.py
import pytest
from unittest.mock import AsyncMock, patch
from app.workers.email_worker import otp_email_job, alert_email_job
from app.integrations.email import send_otp_email, send_alert_email

@pytest.mark.asyncio
async def test_otp_email_job_success():
    with patch("app.workers.email_worker.send_otp_email", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = {"success": True, "message": "Sent"}
        
        ctx = {}
        result = await otp_email_job(ctx, "test@example.com", 123456, 1)
        
        assert result["success"] is True
        mock_send.assert_called_once_with("test@example.com", 123456)

@pytest.mark.asyncio
async def test_otp_email_job_failure_triggers_retry():
    with patch("app.workers.email_worker.send_otp_email", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = {"success": False, "message": "SMTP error"}
        
        ctx = {}
        with pytest.raises(Exception, match="SMTP error"):
            await otp_email_job(ctx, "test@example.com", 123456, 1)
```

---

**End of Worker and Email Design**