"""feat(schema): tablas faltantes — ordenes_compra, plan_anual_lineas, pipeline_archivos

Revision ID: 20260603_1100
Revises: 20260603_1030
Create Date: 2026-06-03 11:00:00.000000

Cambios:
1. Crea tipo enum plan_anual_status (idempotente — schema.sql lo puede crear antes)
2. Crea tabla ordenes_compra con índices
3. Crea tabla plan_anual_lineas con índices (GIN y HNSW via op.execute)
4. Crea tabla pipeline_archivos con índice

Esta migración es idempotente (CREATE IF NOT EXISTS / DO $$ EXCEPTION) porque los
entornos inicializados desde schema.sql ya tienen estas tablas y tipos.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260603_1100"
down_revision = "20260603_1030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Enum plan_anual_status — idempotente
    conn.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE plan_anual_status AS ENUM (
                'planificada', 'publicada', 'adjudicada', 'cancelada'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """))

    # 2. Tabla ordenes_compra
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS ordenes_compra (
            codigo varchar(50) PRIMARY KEY,
            licitacion_codigo varchar(50) REFERENCES licitaciones(codigo) ON DELETE SET NULL,
            codigo_organismo int REFERENCES organismos(codigo_organismo) ON DELETE SET NULL,
            rut_proveedor varchar(20) REFERENCES proveedores(rut) ON DELETE SET NULL,
            estado oc_estado NOT NULL,
            estado_codigo smallint,
            nombre varchar(1000),
            descripcion text,
            moneda varchar(10) DEFAULT 'CLP',
            total_neto numeric(18, 2),
            total_impuestos numeric(18, 2),
            total numeric(18, 2),
            fecha_envio timestamptz,
            fecha_aceptacion timestamptz,
            raw_payload jsonb,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_oc_licitacion ON ordenes_compra (licitacion_codigo)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_oc_organismo ON ordenes_compra (codigo_organismo)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_oc_proveedor ON ordenes_compra (rut_proveedor)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_oc_fecha_envio ON ordenes_compra (fecha_envio DESC)"))

    # 3. Tabla plan_anual_lineas
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS plan_anual_lineas (
            id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
            ano smallint NOT NULL,
            codigo_organismo int NOT NULL REFERENCES organismos(codigo_organismo) ON DELETE RESTRICT,
            descripcion text NOT NULL,
            unspsc_codigo varchar(8) REFERENCES unspsc_codigos(codigo) ON DELETE SET NULL,
            unspsc_nombre varchar(500),
            monto_estimado numeric(18, 2),
            moneda varchar(10) DEFAULT 'CLP',
            mes_estimado smallint,
            modalidad varchar(50),
            status plan_anual_status NOT NULL DEFAULT 'planificada',
            licitacion_codigo varchar(50) REFERENCES licitaciones(codigo) ON DELETE SET NULL,
            search_vector tsvector,
            raw_payload jsonb,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
    """))

    # vector(1024) requiere pgvector — se agrega con IF NOT EXISTS para idempotencia
    conn.execute(sa.text(
        "ALTER TABLE plan_anual_lineas ADD COLUMN IF NOT EXISTS embedding vector(1024)"
    ))

    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_plan_organismo_ano ON plan_anual_lineas (codigo_organismo, ano)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_plan_unspsc ON plan_anual_lineas (unspsc_codigo)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_plan_status ON plan_anual_lineas (status)"))
    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS idx_plan_search_vector
            ON plan_anual_lineas USING gin(search_vector)
    """))
    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS idx_plan_embedding_hnsw
            ON plan_anual_lineas USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
    """))

    # 4. Tabla pipeline_archivos
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS pipeline_archivos (
            id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
            pipeline_item_id uuid NOT NULL REFERENCES pipeline_items(id) ON DELETE CASCADE,
            nombre_original varchar(500) NOT NULL,
            storage_path text NOT NULL,
            mime_type varchar(100),
            tamano_bytes bigint,
            created_at timestamptz NOT NULL DEFAULT now()
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS idx_archivos_pipeline_item ON pipeline_archivos (pipeline_item_id)"
    ))


def downgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text("DROP INDEX IF EXISTS idx_archivos_pipeline_item"))
    conn.execute(sa.text("DROP TABLE IF EXISTS pipeline_archivos"))

    conn.execute(sa.text("DROP INDEX IF EXISTS idx_plan_embedding_hnsw"))
    conn.execute(sa.text("DROP INDEX IF EXISTS idx_plan_search_vector"))
    conn.execute(sa.text("DROP INDEX IF EXISTS idx_plan_status"))
    conn.execute(sa.text("DROP INDEX IF EXISTS idx_plan_unspsc"))
    conn.execute(sa.text("DROP INDEX IF EXISTS idx_plan_organismo_ano"))
    conn.execute(sa.text("DROP TABLE IF EXISTS plan_anual_lineas"))

    conn.execute(sa.text("DROP INDEX IF EXISTS idx_oc_fecha_envio"))
    conn.execute(sa.text("DROP INDEX IF EXISTS idx_oc_proveedor"))
    conn.execute(sa.text("DROP INDEX IF EXISTS idx_oc_organismo"))
    conn.execute(sa.text("DROP INDEX IF EXISTS idx_oc_licitacion"))
    conn.execute(sa.text("DROP TABLE IF EXISTS ordenes_compra"))

    conn.execute(sa.text("DROP TYPE IF EXISTS plan_anual_status"))
