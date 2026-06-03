"""documentos_bases y documento_chunks

Revision ID: c3e10ad43fd7
Revises:
Create Date: 2026-05-11 04:56:12.198011+00:00

Tablas cubiertas:
- documentos_bases: documentos descargados desde el portal Mercado Público.
- documento_chunks: chunks vectorizados para búsqueda semántica (RAG, Sprint 5).
- Enums: documento_tipo, documento_status.

Esta migración es idempotente (CREATE IF NOT EXISTS) porque los entornos
inicializados desde schema.sql ya tienen estas tablas.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3e10ad43fd7"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Enums — solo crear si no existen
    conn.execute(
        sa.text(
            """
            DO $$ BEGIN
                CREATE TYPE documento_tipo AS ENUM (
                    'bases_administrativas', 'bases_tecnicas', 'anexo', 'aclaracion',
                    'consulta', 'respuesta', 'acta_apertura', 'acta_adjudicacion', 'otro'
                );
            EXCEPTION WHEN duplicate_object THEN NULL;
            END $$;
            """
        )
    )
    conn.execute(
        sa.text(
            """
            DO $$ BEGIN
                CREATE TYPE documento_status AS ENUM ('pendiente', 'descargado', 'procesado', 'error');
            EXCEPTION WHEN duplicate_object THEN NULL;
            END $$;
            """
        )
    )

    # documentos_bases
    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS documentos_bases (
                id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
                licitacion_codigo varchar(50) NOT NULL
                    REFERENCES licitaciones(codigo) ON DELETE CASCADE,
                tipo documento_tipo NOT NULL,
                nombre_original varchar(500),
                url_origen text,
                storage_path text,
                storage_bucket varchar(100),
                mime_type varchar(100),
                tamano_bytes bigint,
                num_paginas int,
                status documento_status NOT NULL DEFAULT 'pendiente',
                texto_extraido text,
                hash_contenido varchar(64),
                error_mensaje text,
                descargado_at timestamptz,
                procesado_at timestamptz,
                created_at timestamptz NOT NULL DEFAULT now()
            );
            """
        )
    )
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS idx_docs_licitacion ON documentos_bases (licitacion_codigo);"
        )
    )
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS idx_docs_status ON documentos_bases (status);"
        )
    )

    # documento_chunks (depende de documentos_bases)
    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS documento_chunks (
                id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
                documento_id uuid NOT NULL
                    REFERENCES documentos_bases(id) ON DELETE CASCADE,
                licitacion_codigo varchar(50) NOT NULL
                    REFERENCES licitaciones(codigo) ON DELETE CASCADE,
                chunk_orden int NOT NULL,
                contenido text NOT NULL,
                pagina_inicio int,
                pagina_fin int,
                tokens int,
                embedding vector(1024),
                metadata jsonb DEFAULT '{}'::jsonb,
                created_at timestamptz NOT NULL DEFAULT now()
            );
            """
        )
    )
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS idx_chunks_documento ON documento_chunks (documento_id);"
        )
    )
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS idx_chunks_licitacion ON documento_chunks (licitacion_codigo);"
        )
    )
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON documento_chunks USING hnsw (embedding vector_cosine_ops);"
        )
    )


def downgrade() -> None:
    op.drop_table("documento_chunks")
    op.drop_table("documentos_bases")
    op.execute("DROP TYPE IF EXISTS documento_status;")
    op.execute("DROP TYPE IF EXISTS documento_tipo;")
