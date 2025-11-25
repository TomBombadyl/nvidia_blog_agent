# Dockerfile for NVIDIA Blog Agent Cloud Run service
# 
# This Dockerfile builds a production-ready container for Cloud Run deployment.
# It uses a multi-stage build to keep the final image size small.

FROM python:3.14-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml ./
COPY requirements.txt ./

# Install Python dependencies
# Suppress pip warning about running as root (safe in containers)
RUN pip install --no-cache-dir --root-user-action=ignore --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --root-user-action=ignore -e .

# Final stage: minimal runtime image
FROM python:3.14-slim

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY nvidia_blog_agent/ ./nvidia_blog_agent/
COPY service/ ./service/
COPY pyproject.toml ./

# Reinstall in editable mode to ensure package structure is correct
# Suppress pip warning about running as root (safe in containers)
RUN pip install --no-cache-dir --root-user-action=ignore -e .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Expose port (Cloud Run will set PORT env var)
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Run the FastAPI service with uvicorn
# Cloud Run sets PORT env var, but uvicorn needs it as --port argument
# Use a shell form to interpolate the PORT env var
CMD uvicorn service.app:app --host 0.0.0.0 --port ${PORT:-8080}

