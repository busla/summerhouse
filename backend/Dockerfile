# Quesada Apartment Booking Backend - AgentCore Runtime Container
# Platform: linux/arm64 (required by AgentCore Runtime)

FROM --platform=linux/arm64 ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

# Copy dependency files first for better caching
# Note: README.md is required because pyproject.toml references it
COPY pyproject.toml uv.lock README.md ./

# Install production dependencies only (no dev deps)
RUN uv sync --frozen --no-cache --no-dev

# Copy source code
COPY src/ ./src/

# Force unbuffered Python output (ensures prints appear immediately in CloudWatch)
ENV PYTHONUNBUFFERED=1

# Expose the standard AgentCore Runtime port
EXPOSE 8080

# Health check for container orchestration
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/ping || exit 1

# Run the AgentCore entrypoint
# Using opentelemetry-instrument for observability when ADOT is configured
CMD ["uv", "run", "python", "-m", "src.agent_app"]

# Rebuild trigger: 2025-12-29T22:57:00Z
