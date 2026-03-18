# Thermal Report — Production Docker Image
# Build:  docker build -t thermal-report:latest .
# Or via compose: docker compose up --build -d

FROM python:3.11-slim

LABEL maintainer="thermal-report"
LABEL description="Thermal survey report web application"

# ── System dependencies ────────────────────────────────────────────────────
# libimage-exiftool-perl  : EXIF date extraction from FLIR images
# Cairo / Pango stack     : required by weasyprint for PDF generation
# pkg-config              : needed by pycairo build
# libgdk-pixbuf2.0-0      : image support for weasyprint
# shared-mime-info        : MIME type detection
RUN apt-get update && apt-get install -y --no-install-recommends \
    libimage-exiftool-perl \
    libcairo2 \
    libcairo2-dev \
    libpango-1.0-0 \
    libpango1.0-dev \
    libpangocairo-1.0-0 \
    libpangoft2-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libgdk-pixbuf2.0-dev \
    libffi-dev \
    pkg-config \
    shared-mime-info \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# ── Python dependencies ────────────────────────────────────────────────────
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Application files ──────────────────────────────────────────────────────
COPY . .

# ── Runtime directories (owned by app before dropping root) ───────────────
RUN mkdir -p upload reports .Images \
    && useradd -m -u 1001 appuser \
    && chown -R appuser:appuser /app

USER appuser

# ── Environment ────────────────────────────────────────────────────────────
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV FLASK_ENV=production

EXPOSE 8000

# ── Entrypoint ─────────────────────────────────────────────────────────────
# gunicorn binds on 8000 (internal); Nginx on the host handles 8080 → 8000
# 2 workers is safe for a single-core GCP e2-micro; raise for bigger VMs
CMD ["gunicorn", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "app:app"]
