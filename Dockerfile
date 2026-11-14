# Universal AI GIS Studio — Dockerfile
# Multi-stage build for minimal production image

# =============================================================================
# Base stage - shared dependencies
# =============================================================================
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libgdal-dev \
    gdal-bin \
    libspatialindex-dev \
    libgeos-dev \
    libproj-dev \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r uagis && useradd -r -g uagis -d /app -s /bin/bash uagis

# Copy requirements first for better caching
COPY requirements/ requirements/
COPY pyproject.toml ./

# =============================================================================
# Builder stage - install dependencies
# =============================================================================
FROM base AS builder

# Install all Python dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# =============================================================================
# Production stage - minimal runtime
# =============================================================================
FROM python:3.11-slim AS production

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Install runtime system dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libgdal34 \
    gdal-bin \
    libspatialindex7 \
    libgeos-3.12.0 \
    libproj25 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r uagis && useradd -r -g uagis -d /app -s /bin/bash uagis

# Copy Python dependencies from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=uagis:uagis . .

# Create data and logs directories
RUN mkdir -p /app/data /app/logs && chown -R uagis:uagis /app

# Switch to non-root user
USER uagis

# Expose ports
EXPOSE 8765 8766 8767

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8765/health || exit 1

# Default command - run MCP server
CMD ["python", "-m", "mcp_server.main", "--transport", "streamable-http", "--port", "8766"]

# =============================================================================
# Development stage - with dev dependencies
# =============================================================================
FROM builder AS development

ENV PYTHONPATH=/app

# Install dev dependencies
RUN pip install --no-cache-dir -r requirements/dev.txt

# Install pre-commit
RUN pip install --no-cache-dir pre-commit && pre-commit install

USER uagis

CMD ["bash"]

# =============================================================================
# MCP Server only stage (minimal)
# =============================================================================
FROM production AS mcp-server

USER uagis
CMD ["python", "-m", "mcp_server.main", "--transport", "streamable-http", "--port", "8766"]

# =============================================================================
# Bridge server only stage
# =============================================================================
FROM production AS bridge-server

USER uagis
CMD ["python", "-m", "bridge.bridge_server_async"]