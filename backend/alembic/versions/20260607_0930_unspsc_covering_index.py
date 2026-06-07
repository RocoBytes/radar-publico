"""Reemplaza idx_items_unspsc por índice covering con text_pattern_ops.

El índice btree estándar en unspsc_codigo (varchar) no soporta LIKE 'prefix%'
con locales UTF-8 — genera sequential scan en producción. text_pattern_ops
habilita la búsqueda por prefijo correctamente en cualquier locale.

La segunda columna (licitacion_codigo) hace el índice "covering" para la
cláusula EXISTS correlacionada que usa licitaciones.py y ejecuta_radares.py.
Con este índice, la subquery EXISTS se resuelve en un solo index scan en lugar
de dos scans separados (unspsc + licitacion_codigo).

Revision ID: 20260607_0930
Revises: 20260607_0900
Create Date: 2026-06-07
"""

from alembic import op

revision = "20260607_0930"
down_revision = "20260607_0900"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_items_unspsc")
    op.execute(
        """
        CREATE INDEX idx_items_unspsc_covering
        ON licitacion_items (unspsc_codigo text_pattern_ops, licitacion_codigo)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_items_unspsc_covering")
    op.execute(
        "CREATE INDEX idx_items_unspsc ON licitacion_items (unspsc_codigo)"
    )
