# ==========================================
# Etapa 1: Builder
# ==========================================
FROM python:3.12-slim-bookworm AS builder

# Copiar ejecutable oficial de uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Dependencias del sistema requeridas para compilación de extensiones C
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar archivos de definición de dependencias
COPY pyproject.toml uv.lock ./

# Instalar dependencias en el entorno virtual
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Copiar código fuente
COPY app /app/app
COPY alembic /app/alembic
COPY alembic.ini /app/alembic.ini
COPY README.md /app/README.md

# Instalar proyecto
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


# ==========================================
# Etapa 2: Runtime
# ==========================================
FROM python:3.12-slim-bookworm AS runtime

# Dependencias mínimas de ejecución y utilidades de comprobación de salud
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Usuario no-root para seguridad estricta
RUN groupadd -g 1000 pampero && \
    useradd -u 1000 -g pampero -m -s /bin/bash pampero

WORKDIR /app

# Copiar el entorno virtual preparado en el builder
COPY --from=builder --chown=pampero:pampero /app/.venv /app/.venv
COPY --from=builder --chown=pampero:pampero /app/app /app/app
COPY --from=builder --chown=pampero:pampero /app/alembic /app/alembic
COPY --from=builder --chown=pampero:pampero /app/alembic.ini /app/alembic.ini

# Crear volumen de uploads con permisos de usuario pampero
RUN mkdir -p /app/data/uploads && \
    chown -R pampero:pampero /app/data

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    STORAGE_PATH="/app/data/uploads"

USER pampero

EXPOSE 8000

# Por defecto arranca el servidor HTTP FastAPI
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

