FROM python:3.11-slim

LABEL maintainer="Shikhar <shikhar@example.com>"
LABEL description="ReviewForge — AI pair programming in your terminal"
LABEL version="0.1.0"

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml ./
COPY reviewforge/ ./reviewforge/

# Install ReviewForge
RUN pip install --no-cache-dir -e .

# Set git safe directory for mounted volumes
RUN git config --global --add safe.directory /workspace

# Default working directory for mounted projects
WORKDIR /workspace

ENTRYPOINT ["reviewforge"]
CMD ["--help"]
