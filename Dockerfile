FROM python:3.11-slim

ENV PYTHONUNBUFFERED=True \
    PYTHONDONTWRITEBYTECODE=True \
    PYTHONPATH=/app \
    PORT=8080

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    exiftool \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py settings.py ./
COPY services/ ./services/
COPY utils/ ./utils/
COPY templates/ ./templates/

CMD exec gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 2 --timeout 120 app:app
