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

COPY pyproject.toml poetry.lock* requirements.txt* ./

# Soporte para ambos: poetry o requirements.txt
RUN if [ -f poetry.lock ]; then \
        pip install poetry==1.8.3 && \
        poetry config virtualenvs.in-project true && \
        poetry install --no-root --without dev; \
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
ENV PATH="/app/.venv/bin:$PATH"

# El código fuente se monta como volumen en docker-compose,
# pero copiamos aquí para que la imagen sea self-contained
COPY . .

EXPOSE 8000

# El comando real viene del docker-compose (uvicorn o celery)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ============================================================
# Production: imagen mínima, sin código fuente innecesario
# ============================================================
FROM base AS production

# Usuario no-root para seguridad
RUN groupadd -r radar && useradd -r -g radar -d /app -s /bin/bash radar

COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

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
