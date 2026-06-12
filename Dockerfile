# Use official Python 3.10 slim image for a reduced attack surface and smaller footprint
FROM python:3.10-slim as builder

# Set environment variables to optimize Python runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set the working directory
WORKDIR /app

# Install system dependencies required for building asyncpg and pandas
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create a non-root user for security (OWASP Best Practice)
RUN addgroup --system botgroup && adduser --system --group botuser

# Copy the application code
COPY src/ ./src/
COPY config/config.yaml ./config/config.yaml

# Create logs directory and assign permissions to the non-root user
RUN mkdir logs && chown -R botuser:botgroup /app

# Switch to the non-root user
USER botuser

# Command to run the orchestrator
CMD ["python", "-m", "src.main"]
