FROM python:3.13-slim AS runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ ./backend/

COPY ingest/ ./ingest/

RUN pip install --no-cache-dir flask

RUN groupadd -r logsuser && useradd -r -g logsuser -d /app -s /sbin/nologin logsuser
RUN chown -R logsuser:logsuser /app
USER logsuser

ARG APP_VERSION=unknown
ARG GIT_SHA=unknown
ENV APP_VERSION=${APP_VERSION} GIT_SHA=${GIT_SHA}

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 5514/udp 5514/tcp 8090/tcp 8000/tcp

HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
    CMD python3 ingest/healthcheck.py || exit 1

CMD ["python3", "ingest/entrypoint.py"]
