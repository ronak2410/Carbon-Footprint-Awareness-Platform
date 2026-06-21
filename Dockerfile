FROM python:3.11-slim

# Prevent Python from writing .pyc files
ENV PYTHONDONTWRITEBYTECODE=1
# Force stdout and stderr streams to be unbuffered
ENV PYTHONUNBUFFERED=1

WORKDIR /code

# Copy and install dependencies
COPY requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Copy the rest of the application files
COPY . /code

# Expose port (FastAPI default, overridden by platform PORT environment variables)
EXPOSE 7860

# Run uvicorn server, falling back to port 7860 if PORT is not set
CMD ["sh", "-c", "uvicorn agent_core:app --host 0.0.0.0 --port ${PORT:-7860}"]
