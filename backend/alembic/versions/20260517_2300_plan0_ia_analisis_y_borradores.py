"""Plan 0 IA — tablas analisis_bases y borradores_propuesta

Revision ID: plan0_ia_analisis
Revises: sprint4_radar_pipeline
Create Date: 2026-05-17 23:00:00.000000+00:00

Tablas cubiertas:
- analisis_status: nuevo tipo ENUM para estado de análisis IA.
- analisis_bases: resultado del análisis LLM de bases técnicas por licitación.
- borradores_propuesta: borrador de propuesta técnica por empresa + licitación.

Esta migración es idempotente (IF NOT EXISTS / DO $$ ... EXCEPTION).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "plan0_ia_analisis"
down_revision: Union[str, None] = "sprint4_radar_pipeline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Enum analisis_status
    conn.execute(
        sa.text(
            """
            DO $$ BEGIN
                CREATE TYPE analisis_status AS ENUM (
                    'pendiente', 'procesando', 'listo', 'error'
                );
            EXCEPTION WHEN duplicate_object THEN NULL;
            END $$;
            """
        )
    )

    # analisis_bases
    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS analisis_bases (
                id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
                licitacion_codigo varchar(50) NOT NULL
                    REFERENCES licitaciones(codigo) ON DELETE CASCADE,
                version smallint NOT NULL DEFAULT 1,
                status analisis_status NOT NULL DEFAULT 'pendiente',
                requisitos_tecnicos jsonb,
                criterios_extraidos jsonb,
                documentos_obligatorios jsonb,
                plazos_clave jsonb,
                restricciones jsonb,
                resumen_ejecutivo text,
                modelo_usado varchar(100),
                prompt_version smallint,
                tokens_input int,
                tokens_output int,
                error_mensaje text,
                created_at timestamptz NOT NULL DEFAULT now(),
                updated_at timestamptz NOT NULL DEFAULT now(),
                CONSTRAINT uq_analisis_licitacion_version
                    UNIQUE (licitacion_codigo, version)
            );
            """
        )
    )

    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS idx_analisis_licitacion "
            "ON analisis_bases (licitacion_codigo);"
        )
    )
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS idx_analisis_status "
            "ON analisis_bases (status);"
        )
    )

    # borradores_propuesta
    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS borradores_propuesta (
                id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
                licitacion_codigo varchar(50) NOT NULL
                    REFERENCES licitaciones(codigo) ON DELETE CASCADE,
                empresa_id uuid NOT NULL
                    REFERENCES empresas(id) ON DELETE CASCADE,
                analisis_id uuid
                    REFERENCES analisis_bases(id) ON DELETE SET NULL,
                version smallint NOT NULL DEFAULT 1,
                status analisis_status NOT NULL DEFAULT 'pendiente',
                titulo varchar(500),
                secciones jsonb,
                documentos_pendientes jsonb,
                notas_revision jsonb,
                modelo_usado varchar(100),
                prompt_version smallint,
                tokens_input int,
                tokens_output int,
                error_mensaje text,
                created_at timestamptz NOT NULL DEFAULT now(),
                updated_at timestamptz NOT NULL DEFAULT now(),
                CONSTRAINT uq_borrador_licitacion_empresa_version
                    UNIQUE (licitacion_codigo, empresa_id, version)
            );
            """
        )
    )

    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS idx_borrador_licitacion "
            "ON borradores_propuesta (licitacion_codigo);"
        )
    )
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS idx_borrador_empresa "
            "ON borradores_propuesta (empresa_id);"
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS borradores_propuesta;"))
    conn.execute(sa.text("DROP TABLE IF EXISTS analisis_bases;"))
    conn.execute(sa.text("DROP TYPE IF EXISTS analisis_status;"))
