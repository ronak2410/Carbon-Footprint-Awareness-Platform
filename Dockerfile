# ── Stage 1: Dependency builder ────────────────────────────────────────────
FROM python:3.11-slim AS builder

# Prevent bytecode files and force unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Install dependencies in an isolated layer for layer-caching efficiency
COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip install --prefix=/install --no-cache-dir -r requirements.txt


# ── Stage 2: Runtime image ──────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Default port; Hugging Face Spaces sets $PORT at runtime
    PORT=7860

# Create a non-root user for security
RUN addgroup --system appgroup \
 && adduser  --system --ingroup appgroup --no-create-home appuser

WORKDIR /code

# Copy installed packages from builder stage
COPY --from=builder /install /usr/local

# Copy application source
COPY --chown=appuser:appgroup . /code

# Drop root privileges
USER appuser

# Expose the default port
EXPOSE 7860

# Health check so container orchestrators know when the app is ready
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-7860}/api/health')"

# Run uvicorn with production settings (1 worker, no reload)
CMD ["sh", "-c", "uvicorn agent_core:app --host 0.0.0.0 --port ${PORT:-7860} --workers 1 --log-level info"]
