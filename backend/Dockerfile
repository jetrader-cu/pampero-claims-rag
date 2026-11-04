# syntax=docker/dockerfile:1.7
# Dos imágenes desde el mismo código:
#   target api    → FastAPI y beat, sin Docling (imagen pequeña, arranque rápido)
#   target worker → Celery con Docling, torch CPU y modelos de layout/tablas/OCR precargados

FROM python:3.12-slim-bookworm AS base
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

FROM base AS deps-api
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

FROM base AS deps-worker
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev --extra worker

FROM python:3.12-slim-bookworm AS runtime-base
# libgl/libglib: dependencias nativas de OpenCV que usa el OCR de Docling
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl libpq5 libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -g 1000 pampero && useradd -u 1000 -g pampero -m -s /bin/bash pampero \
    && mkdir -p /app/data/uploads && chown -R pampero:pampero /app/data
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    STORAGE_PATH="/app/data/uploads" \
    HF_HOME="/app/.cache/huggingface"

FROM runtime-base AS api
COPY --from=deps-api --chown=pampero:pampero /app/.venv /app/.venv
COPY --chown=pampero:pampero app /app/app
COPY --chown=pampero:pampero alembic /app/alembic
COPY --chown=pampero:pampero alembic.ini /app/alembic.ini
USER pampero
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM runtime-base AS worker
COPY --from=deps-worker /app/.venv /app/.venv
COPY app /app/app
# Los modelos se descargan aquí, en una capa cacheable, y nunca en tiempo de ejecución.
RUN python -m app.ingest.warmup \
    && mkdir -p /app/.cache && chown -R pampero:pampero /app/.venv /app/.cache /app/app
ENV PARSER=docling
USER pampero
CMD ["celery", "-A", "app.worker.celery_app", "worker", "-l", "INFO", "-c", "2"]
