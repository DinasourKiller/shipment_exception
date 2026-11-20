# Multi-stage Dockerfile for Enterprise Shipment Exception Control Tower
# Stage 1: Build dependencies
FROM python:3.13-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip wheel --no-cache-dir --no-deps --wheel-dir /build/wheels -r requirements.txt

# Stage 2: Production Runtime image
FROM python:3.13-slim AS runner

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create dedicated non-root application user
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

COPY --from=builder /build/wheels /wheels
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir /wheels/* \
    && rm -rf /wheels

# Copy application source code
COPY . /app

# Configure entrypoint script permissions
RUN chmod +x /app/docker-entrypoint.sh \
    && chown -R appuser:appgroup /app

USER appuser

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    ENVIRONMENT=production

EXPOSE 8000

HEALTHCHECK --interval=20s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health/live || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]
