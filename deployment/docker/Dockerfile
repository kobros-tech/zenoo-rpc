# Zenoo RPC - MCP HTTP Server Docker Image
# This image runs the MCP HTTP proxy server on port 8080

FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory for building
WORKDIR /build

# Copy files needed for pip install
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install dependencies - core + mcp + aiohttp (for http proxy)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir . && \
    pip install --no-cache-dir "aiohttp>=3.9.0" "mcp>=1.0.0"


# Production stage
FROM python:3.11-slim as production

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user
RUN groupadd -r zenoo && useradd -r -g zenoo zenoo

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy application source code
COPY src/ ./src/

# Copy MCP HTTP Proxy server
COPY mcp_http_proxy.py ./mcp_http_proxy.py

# Create necessary directories and set ownership
RUN mkdir -p /app/logs /app/tmp && \
    chown -R zenoo:zenoo /app

# Set environment variables
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# MCP HTTP Server defaults (port 8080)
ENV MCP_PORT=8080
ENV MCP_HOST=0.0.0.0

# Switch to non-root user
USER zenoo

# Expose port 8080 (MCP HTTP Server default)
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${MCP_PORT}/health || exit 1

# Start MCP HTTP Server
CMD ["python", "mcp_http_proxy.py"]
