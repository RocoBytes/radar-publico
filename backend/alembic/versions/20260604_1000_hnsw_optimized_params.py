"""optimizar parámetros HNSW para embeddings de 1024 dimensiones

Revision ID: 20260604_1000
Revises: 20260604_0900
Create Date: 2026-06-04 10:00:00.000000

Los índices HNSW se crearon con parámetros por defecto (m=16, ef_construction=64),
subóptimos para vectores de 1024 dimensiones (Voyage AI).
Con m=32 / ef_construction=200 el recall mejora significativamente a costa de
un ~30 % más de RAM de índice y build time más largo (aceotable en migración).

Índices afectados (detectados en schema.sql):
  - idx_chunks_embedding      → documento_chunks
  - idx_licitaciones_embedding → licitaciones
  - idx_plan_embedding        → plan_anual_lineas

La migración usa DROP + CREATE CONCURRENTLY para minimizar el impacto en
producción. CONCURRENTLY no requiere lock exclusivo en la tabla.

Nota: downgrade recrea con los parámetros originales (defaults de pgvector).
"""

from __future__ import annotations

from alembic import op

revision = "20260604_1000"
down_revision = "20260604_0900"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Eliminar índices con parámetros por defecto
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_chunks_embedding;")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_licitaciones_embedding;")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_plan_embedding;")

    # Recrear con m=32 / ef_construction=200, optimizados para 1024 dims
    op.execute("""
        CREATE INDEX CONCURRENTLY idx_chunks_embedding
        ON documento_chunks
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 32, ef_construction = 200);
    """)
    op.execute("""
        CREATE INDEX CONCURRENTLY idx_licitaciones_embedding
        ON licitaciones
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 32, ef_construction = 200);
    """)
    op.execute("""
        CREATE INDEX CONCURRENTLY idx_plan_embedding
        ON plan_anual_lineas
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 32, ef_construction = 200);
    """)


def downgrade() -> None:
    # Volver a parámetros por defecto de pgvector (m=16, ef_construction=64)
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_chunks_embedding;")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_licitaciones_embedding;")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_plan_embedding;")

    op.execute("""
        CREATE INDEX CONCURRENTLY idx_chunks_embedding
        ON documento_chunks
        USING hnsw (embedding vector_cosine_ops);
    """)
    op.execute("""
        CREATE INDEX CONCURRENTLY idx_licitaciones_embedding
        ON licitaciones
        USING hnsw (embedding vector_cosine_ops);
    """)
    op.execute("""
        CREATE INDEX CONCURRENTLY idx_plan_embedding
        ON plan_anual_lineas
        USING hnsw (embedding vector_cosine_ops);
    """)
