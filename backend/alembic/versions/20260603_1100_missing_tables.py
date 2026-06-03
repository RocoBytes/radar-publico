"""feat(schema): tablas faltantes — ordenes_compra, plan_anual_lineas, pipeline_archivos

Revision ID: 20260603_1100
Revises: 20260603_1030
Create Date: 2026-06-03 11:00:00.000000

Cambios:
1. Crea tipo enum plan_anual_status (oc_estado ya existe)
2. Crea tabla ordenes_compra con índices
3. Crea tabla plan_anual_lineas con índices (GIN y HNSW via op.execute)
4. Crea tabla pipeline_archivos con índice
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260603_1100"
down_revision = "20260603_1030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Crear el enum plan_anual_status
    op.execute("""
        CREATE TYPE plan_anual_status AS ENUM (
            'planificada',
            'publicada',
            'adjudicada',
            'cancelada'
        );
    """)

    # 2. Crear tabla ordenes_compra
    op.create_table(
        "ordenes_compra",
        sa.Column("codigo", sa.String(50), primary_key=True),
        sa.Column(
            "licitacion_codigo",
            sa.String(50),
            sa.ForeignKey("licitaciones.codigo", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "codigo_organismo",
            sa.Integer(),
            sa.ForeignKey("organismos.codigo_organismo", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "rut_proveedor",
            sa.String(20),
            sa.ForeignKey("proveedores.rut", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "estado",
            sa.Enum("emitida", "aceptada", "rechazada", "cancelada", "en_proceso",
                    "recepcion_conforme", "pagada", "desconocido",
                    name="oc_estado", create_type=False),
            nullable=False,
        ),
        sa.Column("estado_codigo", sa.SmallInteger(), nullable=True),
        sa.Column("nombre", sa.String(1000), nullable=True),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("moneda", sa.String(10), nullable=True, server_default="'CLP'"),
        sa.Column("total_neto", sa.Numeric(18, 2), nullable=True),
        sa.Column("total_impuestos", sa.Numeric(18, 2), nullable=True),
        sa.Column("total", sa.Numeric(18, 2), nullable=True),
        sa.Column("fecha_envio", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fecha_aceptacion", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("idx_oc_licitacion", "ordenes_compra", ["licitacion_codigo"])
    op.create_index("idx_oc_organismo", "ordenes_compra", ["codigo_organismo"])
    op.create_index("idx_oc_proveedor", "ordenes_compra", ["rut_proveedor"])
    op.create_index(
        "idx_oc_fecha_envio",
        "ordenes_compra",
        [sa.text("fecha_envio DESC")],
    )

    # 3. Crear tabla plan_anual_lineas
    op.create_table(
        "plan_anual_lineas",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column("ano", sa.SmallInteger(), nullable=False),
        sa.Column(
            "codigo_organismo",
            sa.Integer(),
            sa.ForeignKey("organismos.codigo_organismo", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column(
            "unspsc_codigo",
            sa.String(8),
            sa.ForeignKey("unspsc_codigos.codigo", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("unspsc_nombre", sa.String(500), nullable=True),
        sa.Column("monto_estimado", sa.Numeric(18, 2), nullable=True),
        sa.Column("moneda", sa.String(10), nullable=True, server_default="'CLP'"),
        sa.Column("mes_estimado", sa.SmallInteger(), nullable=True),
        sa.Column("modalidad", sa.String(50), nullable=True),
        sa.Column(
            "status",
            sa.Enum("planificada", "publicada", "adjudicada", "cancelada",
                    name="plan_anual_status", create_type=False),
            nullable=False,
            server_default="'planificada'",
        ),
        sa.Column(
            "licitacion_codigo",
            sa.String(50),
            sa.ForeignKey("licitaciones.codigo", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Columna vector(1024) — Alembic no soporta pgvector nativamente
    op.execute("ALTER TABLE plan_anual_lineas ADD COLUMN embedding vector(1024)")

    op.create_index(
        "idx_plan_organismo_ano", "plan_anual_lineas", ["codigo_organismo", "ano"]
    )
    op.create_index("idx_plan_unspsc", "plan_anual_lineas", ["unspsc_codigo"])
    op.create_index("idx_plan_status", "plan_anual_lineas", ["status"])

    # Índice GIN para búsqueda full-text sobre search_vector
    op.execute("""
        CREATE INDEX idx_plan_search_vector
            ON plan_anual_lineas USING gin(search_vector);
    """)

    # Índice HNSW para búsqueda semántica (cosine) — requiere pgvector instalado
    op.execute("""
        CREATE INDEX idx_plan_embedding_hnsw
            ON plan_anual_lineas USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64);
    """)

    # 4. Crear tabla pipeline_archivos
    op.create_table(
        "pipeline_archivos",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "pipeline_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pipeline_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("nombre_original", sa.String(500), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("tamano_bytes", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "idx_archivos_pipeline_item", "pipeline_archivos", ["pipeline_item_id"]
    )


def downgrade() -> None:
    # Orden inverso: tablas primero, luego el enum
    op.drop_index("idx_archivos_pipeline_item", table_name="pipeline_archivos")
    op.drop_table("pipeline_archivos")

    op.drop_index("idx_plan_embedding_hnsw", table_name="plan_anual_lineas")
    op.drop_index("idx_plan_search_vector", table_name="plan_anual_lineas")
    op.drop_index("idx_plan_status", table_name="plan_anual_lineas")
    op.drop_index("idx_plan_unspsc", table_name="plan_anual_lineas")
    op.drop_index("idx_plan_organismo_ano", table_name="plan_anual_lineas")
    op.drop_table("plan_anual_lineas")

    op.drop_index("idx_oc_fecha_envio", table_name="ordenes_compra")
    op.drop_index("idx_oc_proveedor", table_name="ordenes_compra")
    op.drop_index("idx_oc_organismo", table_name="ordenes_compra")
    op.drop_index("idx_oc_licitacion", table_name="ordenes_compra")
    op.drop_table("ordenes_compra")

    op.execute("DROP TYPE IF EXISTS plan_anual_status;")
