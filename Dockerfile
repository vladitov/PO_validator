FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run injects the PORT env var (defaults to 8080). Uvicorn must bind to it on 0.0.0.0.
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
