# syntax=docker/dockerfile:1

FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl gcc build-essential && rm -rf /var/lib/apt/lists/*

FROM base AS deps
COPY requirements.txt requirements.txt
COPY requirements-dev.txt requirements-dev.txt
COPY backend/requirements.txt backend/requirements.txt
COPY backend/requirements-dev.txt backend/requirements-dev.txt
RUN pip install -r requirements.txt && \
    if [ -f requirements-dev.txt ]; then pip install -r requirements-dev.txt; fi

FROM base AS runtime
COPY --from=deps /usr/local/lib/python3.12 /usr/local/lib/python3.12
COPY --from=deps /usr/local/bin /usr/local/bin
COPY . /app
RUN mkdir -p /app/data
ENV BULLBEAR_DB_URL="sqlite:////app/data/app.db" \
    BULLBEAR_ENV="production" \
    BULLBEAR_RATE_LIMIT_BACKEND="memory" \
    BULLBEAR_MIGRATE_ON_START="true" \
    PORT=8000
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/health || exit 1
ENTRYPOINT ["/entrypoint.sh"]
