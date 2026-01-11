FROM python:3.11-slim

ENV PYTHONUNBUFFERED=True
WORKDIR /app
COPY . .

# Install system dependencies
RUN apt-get update && \
    apt-get install -y exiftool && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

ENV PYTHONPATH=/app
ENV PORT=8080
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 300 app:app
