# Thermal Report Docker Image
# Build: docker build -t thermal-report:latest .
# Run: docker run -it --rm -v $(pwd)/Images:/app/Images thermal-report:latest

FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libimage-exiftool-perl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY *.py .
COPY test1.py .

# Create directories for images and reports
RUN mkdir -p Images reports test_images

# Set environment variable
ENV PYTHONUNBUFFERED=1

# Default command
CMD ["/bin/bash"]
