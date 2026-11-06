# Dockerfile for the syslog ingest service and webhook receiver
# Multi-stage: runtime only, non-root user

FROM python:3.12-slim AS runtime

WORKDIR /app

# Install runtime dependencies including flask for webhook-receiver
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Install shared backend dependencies first (cached layer)
COPY backend-fastapi/requirements.txt ./backend-fastapi/requirements.txt
RUN pip install --no-cache-dir -r backend-fastapi/requirements.txt

# Copy backend-fastapi source (shared normalizers, parsers, syslog listener)
COPY backend-fastapi/ ./backend-fastapi/

# Copy ingest code (entrypoint + webhook_receiver)
COPY ingest/ ./ingest/

# Extra dependency for the webhook receiver
RUN pip install --no-cache-dir flask

# Create non-root user
RUN groupadd -r logsuser && useradd -r -g logsuser -d /app -s /sbin/nologin logsuser
RUN chown -R logsuser:logsuser /app
USER logsuser

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Expose container ports
EXPOSE 5514/udp 5514/tcp 8000/tcp

HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
    CMD python3 -c "import socket; s=socket.socket(); s.settimeout(2); s.connect(('127.0.0.1', 5514)); s.close()" || exit 1

# Default entrypoint: syslog listener. Override via compose `command` for webhook-receiver.
CMD ["python3", "ingest/entrypoint.py"]
