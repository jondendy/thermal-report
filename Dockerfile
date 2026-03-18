# Thermal Report Docker Image
# Build: docker build -t thermal-report:latest .
# Run: docker run -p 8080:8080 thermal-report:latest

FROM python:3.11-slim

# Install system dependencies
# libGL1 + libglib2.0 are required by opencv-python (used by flirimageextractor)
# Use opencv-python-headless in requirements.txt to avoid X11/display deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libimage-exiftool-perl \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py settings.py ./
COPY services/ ./services/
COPY lib/ ./lib/
COPY templates/ ./templates/
COPY static/ ./static/

# Use /tmp for ephemeral storage (Cloud Run filesystem is read-only except /tmp)
ENV UPLOAD_FOLDER=/tmp/.images
ENV REPORTS_FOLDER=/tmp/.reports
ENV PYTHONUNBUFFERED=1

# Cloud Run injects $PORT (default 8080); gunicorn binds to it
CMD exec gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 2 --timeout 120 app:app
