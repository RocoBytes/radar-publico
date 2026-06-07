"""Agrega índices compuestos parciales en licitaciones para búsquedas multidimensionales.

Sin estos índices, las queries combinadas (estado + organismo + fecha_cierre + monto)
fuerzan a PostgreSQL a hacer bitmap-AND entre índices de una sola columna, degenerando
en scans parciales con tablas de 500k+ filas.

Todos los índices son WHERE estado = 'publicada' porque el 80%+ del tráfico de búsqueda
recae sobre licitaciones publicadas. El subconjunto cabe en RAM y se usa en O(log N).

Revision ID: 20260607_0900
Revises: 20260606_1000
Create Date: 2026-06-07
"""

from alembic import op

revision = "20260607_0900"
down_revision = "20260606_1000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Caso de uso más frecuente: publicadas + organismo + fecha de cierre
    # Sirve el filtro combinado de la vista de oportunidades activas por organismo
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_licitaciones_organismo_cierre_pub
        ON licitaciones (codigo_organismo, fecha_cierre DESC NULLS LAST)
        WHERE estado = 'publicada'
        """
    )

    # Rango de monto para el filtro de presupuesto disponible
    # monto_estimado IS NOT NULL filtra las licitaciones sin presupuesto declarado
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_licitaciones_monto_pub
        ON licitaciones (monto_estimado)
        WHERE estado = 'publicada' AND monto_estimado IS NOT NULL
        """
    )

    # Tipo de licitación (L1, LE, LP, LS, CO, AG, CM) + ordenamiento por fecha_publicacion
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_licitaciones_tipo_pub
        ON licitaciones (tipo, fecha_publicacion DESC NULLS LAST)
        WHERE estado = 'publicada'
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_licitaciones_organismo_cierre_pub")
    op.execute("DROP INDEX IF EXISTS idx_licitaciones_monto_pub")
    op.execute("DROP INDEX IF EXISTS idx_licitaciones_tipo_pub")
