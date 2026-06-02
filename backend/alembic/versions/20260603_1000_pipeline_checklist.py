"""feat(pipeline): checklist documental - tabla y tipos PG

Revision ID: 20260603_1000
Revises: plan0_ia_analisis
Create Date: 2026-06-03 10:00:00.000000

Crea la tabla pipeline_checklist_items con sus enums PG:
- checklist_item_estado: pendiente | en_preparacion | completado | no_aplica
- checklist_item_origen: ia_generado | manual
- Índice idx_checklist_pipeline_item en pipeline_item_id
- Índice único parcial uq_checklist_ia_dedup para idempotencia de bootstrap IA
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260603_1000"
down_revision = "plan0_ia_analisis"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enums — idempotentes con DO $$ ... EXCEPTION WHEN duplicate_object
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE checklist_item_estado AS ENUM (
                'pendiente', 'en_preparacion', 'completado', 'no_aplica'
            );
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE checklist_item_origen AS ENUM ('ia_generado', 'manual');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)

    # Tabla
    op.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_checklist_items (
            id                uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
            pipeline_item_id  uuid NOT NULL
                                REFERENCES pipeline_items(id) ON DELETE CASCADE,
            nombre            varchar(255) NOT NULL,
            descripcion       text,
            obligatorio       boolean NOT NULL DEFAULT false,
            estado            checklist_item_estado NOT NULL DEFAULT 'pendiente',
            origen            checklist_item_origen NOT NULL,
            orden             smallint NOT NULL DEFAULT 0,
            completed_at      timestamptz,
            created_at        timestamptz NOT NULL DEFAULT now(),
            updated_at        timestamptz NOT NULL DEFAULT now()
        );
    """)

    # Índice de consulta por pipeline_item
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_checklist_pipeline_item
            ON pipeline_checklist_items (pipeline_item_id);
    """)

    # Índice único parcial para idempotencia del bootstrap IA:
    # dos llamadas al bootstrap no pueden generar el mismo ítem IA
    # para el mismo pipeline_item (comparación case-insensitive en nombre).
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_checklist_ia_dedup
            ON pipeline_checklist_items (pipeline_item_id, lower(nombre))
            WHERE origen = 'ia_generado';
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS pipeline_checklist_items;")
    op.execute("DROP TYPE IF EXISTS checklist_item_origen;")
    op.execute("DROP TYPE IF EXISTS checklist_item_estado;")
