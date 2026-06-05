FROM python:3.14-slim

# Match local deployment: install deps with uv (pinned to the local uv version).
COPY --from=ghcr.io/astral-sh/uv:0.11.14 /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_NO_CACHE=1

WORKDIR /app

# Install locked dependencies first for better layer caching.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev

COPY . .

# Put the synced project environment on PATH so uvicorn is available.
ENV PATH="/app/.venv/bin:$PATH"

# Cloud Run injects the PORT env var (defaults to 8080). Uvicorn must bind to it on 0.0.0.0.
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
