# syntax=docker/dockerfile:1.7
FROM python:3.12-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Build-time basics. The browser system deps are pulled in by `scrapling install`
# below (it shells out to `playwright install-deps`), so we keep this layer tiny.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies — copied first so this layer caches when only app code changes.
COPY requirements.txt .
RUN pip install -r requirements.txt

# Download Chromium + Camoufox + system deps Scrapling needs for StealthyFetcher
# and DynamicFetcher. Equivalent to `playwright install-deps chromium && playwright install chromium`
# plus the fingerprint-manipulation extras Scrapling layers on top.
RUN scrapling install

# App source.
COPY app ./app

EXPOSE 8080

# One worker — Playwright Chromium is heavy and the deploy box has 1 vCPU.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
