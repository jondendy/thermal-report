# Use Python 3.11 slim image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=True \
    PYTHONDONTWRITEBYTECODE=True \
    PYTHONPATH=/app \
    PORT=8080

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    exiftool \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Upgrade pip and install Python dependencies
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/processed_thermal /app/reports /app/upload

# Run with gunicorn using better settings for Cloud Run
CMD exec gunicorn \
    --bind :$PORT \
    --workers 1 \
    --threads 4 \
    --worker-class sync \
    --timeout 600 \
    --graceful-timeout 60 \
    --keep-alive 5 \
    --log-level info \
    --access-logfile - \
    --error-logfile - \
    app:app
