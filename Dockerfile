FROM python:3.11-slim

LABEL maintainer="Shikhar <shikhar@example.com>"
LABEL description="ReviewForge Universal Backend API"

RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Security: Create non-root user and set permissions
RUN adduser --disabled-password --gecos "" appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app

COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY reviewforge/ ./reviewforge/
RUN pip install --no-cache-dir -e .

RUN git config --global --add safe.directory "*"

USER appuser

EXPOSE 8000

# Runs API server programmatically reading PORT env var
CMD ["python", "-m", "reviewforge.api"]

