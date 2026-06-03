"""feat(schema): restricción UNIQUE en plan_anual_lineas para upsert idempotente

Revision ID: 20260603_1200
Revises: 20260603_1100
Create Date: 2026-06-03 12:00:00.000000

Agrega la restricción uq_plan_anual_organismo_ano_descripcion, requerida por
la tarea sync_plan_anual para hacer upsert por ON CONFLICT DO UPDATE sin
duplicar filas.
"""

from __future__ import annotations

from alembic import op

revision = "20260603_1200"
down_revision = "20260603_1100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_plan_anual_organismo_ano_descripcion",
        "plan_anual_lineas",
        ["codigo_organismo", "ano", "descripcion"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_plan_anual_organismo_ano_descripcion",
        "plan_anual_lineas",
        type_="unique",
    )
