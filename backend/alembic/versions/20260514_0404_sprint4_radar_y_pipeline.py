"""Sprint 4 — modelos radar y pipeline

Revision ID: sprint4_radar_pipeline
Revises: c3e10ad43fd7
Create Date: 2026-05-14 04:04:00.000000+00:00

Tablas cubiertas:
- radares: búsquedas guardadas con filtros JSON y configuración de alertas.
- pipeline_items: seguimiento de licitaciones por empresa (estado, score, notas).
- pipeline_notas: notas textuales por ítem del pipeline.

Esta migración es idempotente (CREATE IF NOT EXISTS) porque los entornos
inicializados desde schema.sql ya tienen estas tablas.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "sprint4_radar_pipeline"
down_revision: Union[str, None] = "c3e10ad43fd7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Enum pipeline_estado — solo crear si no existe
    conn.execute(
        sa.text(
            """
            DO $$ BEGIN
                CREATE TYPE pipeline_estado AS ENUM (
                    'nueva', 'vista', 'interesado', 'postulando', 'postulada',
                    'adjudicada', 'perdida', 'descartada'
                );
            EXCEPTION WHEN duplicate_object THEN NULL;
            END $$;
            """
        )
    )

    # radares
    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS radares (
                id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
                empresa_id uuid NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
                nombre varchar(100) NOT NULL,
                descripcion text,
                filtros jsonb NOT NULL,
                activo boolean NOT NULL DEFAULT true,
                notif_canal varchar(20) NOT NULL DEFAULT 'email',
                notif_frecuencia varchar(20) NOT NULL DEFAULT 'instantaneo',
                notif_score_minimo smallint DEFAULT 70,
                ultima_ejecucion_at timestamptz,
                created_at timestamptz NOT NULL DEFAULT now(),
                updated_at timestamptz NOT NULL DEFAULT now()
            );
            """
        )
    )
    conn.execute(
        sa.text(
            """
            CREATE INDEX IF NOT EXISTS idx_radares_empresa_activo
            ON radares (empresa_id, activo);
            """
        )
    )

    # pipeline_items
    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS pipeline_items (
                id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
                empresa_id uuid NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
                licitacion_codigo varchar(50) NOT NULL
                    REFERENCES licitaciones(codigo) ON DELETE CASCADE,
                estado pipeline_estado NOT NULL DEFAULT 'nueva',
                score smallint CHECK (score BETWEEN 0 AND 100),
                score_justificacion jsonb,
                razon_descarte text,
                monto_postulado numeric(18, 2),
                resultado_observaciones text,
                detected_by_radar_id uuid REFERENCES radares(id) ON DELETE SET NULL,
                created_at timestamptz NOT NULL DEFAULT now(),
                updated_at timestamptz NOT NULL DEFAULT now(),
                UNIQUE (empresa_id, licitacion_codigo)
            );
            """
        )
    )
    conn.execute(
        sa.text(
            """
            CREATE INDEX IF NOT EXISTS idx_pipeline_empresa_estado
            ON pipeline_items (empresa_id, estado);
            """
        )
    )
    conn.execute(
        sa.text(
            """
            CREATE INDEX IF NOT EXISTS idx_pipeline_licitacion
            ON pipeline_items (licitacion_codigo);
            """
        )
    )

    # pipeline_notas
    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS pipeline_notas (
                id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
                pipeline_item_id uuid NOT NULL
                    REFERENCES pipeline_items(id) ON DELETE CASCADE,
                contenido text NOT NULL,
                created_at timestamptz NOT NULL DEFAULT now()
            );
            """
        )
    )
    conn.execute(
        sa.text(
            """
            CREATE INDEX IF NOT EXISTS idx_notas_item
            ON pipeline_notas (pipeline_item_id, created_at DESC);
            """
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS pipeline_notas CASCADE;"))
    conn.execute(sa.text("DROP TABLE IF EXISTS pipeline_items CASCADE;"))
    conn.execute(sa.text("DROP TABLE IF EXISTS radares CASCADE;"))
    conn.execute(sa.text("DROP TYPE IF EXISTS pipeline_estado;"))
