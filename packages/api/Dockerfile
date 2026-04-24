# syntax=docker/dockerfile:1.7
FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv==0.4.*

WORKDIR /app

# Copy engine first so the editable/path install works; release builds still
# resolve via the tagged git ref from [project.dependencies] when
# `uv sync --no-sources` is used in CI.
COPY packages/valuation_engine /app/packages/valuation_engine
COPY packages/api /app/packages/api

WORKDIR /app/packages/api
RUN uv sync --frozen --no-dev

RUN useradd --system --uid 1001 appuser
USER appuser

ENV PORT=8000
EXPOSE 8000

CMD ["uv", "run", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
