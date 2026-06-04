# Radar Público — Backend Dockerfile
# Multi-stage: development (con auto-reload) y production (optimizado)

# ============================================================
# Base: Python 3.12 slim con dependencias del sistema
# ============================================================
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

# Dependencias del sistema:
# - build-essential: compilar paquetes nativos
# - libpq-dev: cliente Postgres
# - curl: healthchecks
# - poppler-utils, tesseract-ocr: parseo de PDFs (pymupdf y OCR)
# - libmagic1: detección de tipo MIME
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-spa \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ============================================================
# Builder: instala dependencias en venv
# ============================================================
FROM base AS builder

COPY pyproject.toml poetry.lock* requirements.txt* requirements-prod.txt* ./

# Preferencia: poetry (con dev deps excluidos) > requirements-prod.txt > requirements.txt
RUN if [ -f poetry.lock ]; then \
        pip install poetry==1.8.3 && \
        poetry config virtualenvs.in-project true && \
        poetry install --no-root --without dev; \
    elif [ -f requirements-prod.txt ]; then \
        python -m venv .venv && \
        .venv/bin/pip install -r requirements-prod.txt; \
    elif [ -f requirements.txt ]; then \
        python -m venv .venv && \
        .venv/bin/pip install -r requirements.txt; \
    else \
        echo "No dependency file found" && exit 1; \
    fi

# ============================================================
# Development: hot reload, dev tools
# ============================================================
FROM base AS development

# Copiar el venv ya construido con todas las dependencias
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app

# El código fuente se monta como volumen en docker-compose,
# pero copiamos aquí para que la imagen sea self-contained
COPY . .

EXPOSE 8000

# El comando real viene del docker-compose (uvicorn o celery)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ============================================================
# Playwright: worker de scraping con browsers Chromium instalados.
# Usa la imagen oficial de Playwright para evitar lidiar con libs nativas
# (libnss3, libatk-bridge2.0-0, libxkbcommon0, libdrm2, etc.) en slim.
# Imagen ~1.5 GB — solo se usa para el servicio worker_scraper.
# ============================================================
FROM mcr.microsoft.com/playwright/python:v1.49.0-noble AS playwright

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Deps adicionales del sistema que la imagen base de Playwright no incluye
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar deps con pip del sistema de la imagen Playwright.
# No copiamos el venv del builder (arm64) porque esta imagen puede correr
# bajo emulación amd64 en Apple Silicon y los binarios serían incompatibles.
COPY requirements.txt* requirements-prod.txt* ./
RUN if [ -f requirements-prod.txt ]; then \
        pip install --no-cache-dir -r requirements-prod.txt; \
    elif [ -f requirements.txt ]; then \
        pip install --no-cache-dir -r requirements.txt; \
    fi

COPY . .

# Usuario no-root: Chromium no necesita root en un contenedor Docker
RUN groupadd -r radar && useradd -r -g radar --home /app radar && \
    chown -R radar:radar /app
USER radar

CMD ["python", "-m", "celery", "-A", "app.celery_app", "worker", "-Q", "scraping", "--concurrency=2", "--loglevel=info"]

# ============================================================
# Production: imagen mínima, sin código fuente innecesario
# ============================================================
FROM base AS production

# Usuario no-root para seguridad
RUN groupadd -r radar && useradd -r -g radar -d /app -s /bin/bash radar

COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app

COPY --chown=radar:radar . .

USER radar

EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["gunicorn", "app.main:app", \
     "-w", "4", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
