# Fixed Dockerfile for pg-airman-mcp with proper libpq dependencies
# Based on https://github.com/EnterpriseDB/pg-airman-mcp/blob/main/Dockerfile
# but with libpq5 added to runtime stage

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Clone and build pg-airman-mcp
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*
RUN git clone https://github.com/EnterpriseDB/pg-airman-mcp.git /tmp/pg-airman-mcp

WORKDIR /tmp/pg-airman-mcp

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev || \
    uv sync --frozen --no-dev

# Runtime stage
FROM python:3.12-slim-bookworm

# Install runtime dependencies including libpq5 (the actual library, not just dev headers)
RUN apt-get update && apt-get install -y --no-install-recommends \
    dnsutils \
    iputils-ping \
    libpq5 \
    libpq-dev \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

# Copy application and virtual environment from builder
COPY --from=builder --chown=app:app /tmp/pg-airman-mcp /app

WORKDIR /app

# Create non-root user for OpenShift compatibility
RUN groupadd --gid 1000 app && \
    useradd --uid 1000 --gid 1000 --create-home app && \
    chown -R app:app /app

# Switch to non-root user
USER 1000

# Set PATH to include .venv
ENV PATH="/app/.venv/bin:$PATH"

# Expose port
EXPOSE 8000

# Use the entrypoint script
COPY --from=builder /tmp/pg-airman-mcp/docker-entrypoint.sh /app/
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["pg-airman-mcp"]
