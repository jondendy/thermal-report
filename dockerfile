FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y libimage-exiftool-perl
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY images/ ./images/

CMD ["python", "src/flir_processor_simple.py"]  # Replace with your main script
