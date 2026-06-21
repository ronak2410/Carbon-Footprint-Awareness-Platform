FROM python:3.11-slim

# Prevent Python from writing .pyc files and force unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=7860

WORKDIR /code

# Install dependencies first (separate layer for Docker cache efficiency)
COPY requirements.txt /code/requirements.txt
RUN pip install --upgrade pip \
 && pip install --no-cache-dir -r /code/requirements.txt

# Copy application source files
COPY . /code

# Expose the default Hugging Face Spaces port
EXPOSE 7860

# Health check so the platform knows when the app is ready
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7860/api/health', timeout=5)"

# Start uvicorn server
CMD ["sh", "-c", "uvicorn agent_core:app --host 0.0.0.0 --port ${PORT:-7860} --log-level info"]
