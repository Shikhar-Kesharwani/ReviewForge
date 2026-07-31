FROM python:3.11-slim

LABEL maintainer="Shikhar <shikhar@example.com>"
LABEL description="ReviewForge Universal Backend API"

RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY reviewforge/ ./reviewforge/
RUN pip install --no-cache-dir -e .

RUN git config --global --add safe.directory "*"

EXPOSE 8000

# Runs API server programmatically reading PORT env var
CMD ["python", "-m", "reviewforge.api"]
