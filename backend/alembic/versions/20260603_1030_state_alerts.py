"""feat(notifications): alertas de cambio de estado externo

Revision ID: 20260603_1030
Revises: 20260603_1000
Create Date: 2026-06-03 10:30:00.000000

Cambios:
1. Renombra notif_tipo.cambio_estado -> cambio_estado_externo (para ChileCompra)
2. Agrega notif_tipo.cambio_estado_interno (para movimientos de pipeline del usuario)
3. Reclasifica histórico: las filas existentes eran siempre internas
4. Agrega ultimo_estado_licitacion en pipeline_items
5. Crea índice único parcial para idempotencia de alertas de cambio externo

NOTA DOWNGRADE: ALTER TYPE RENAME VALUE no es trivialmente reversible
si hay filas usando el value renombrado. El downgrade está documentado
como degradación parcial — requiere intervención manual si hay datos.
Ver comentarios en downgrade().
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260603_1030"
down_revision = "20260603_1000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Renombrar el value existente en el enum:
    #    cambio_estado (genérico) -> cambio_estado_externo (ChileCompra)
    op.execute(
        "ALTER TYPE notif_tipo RENAME VALUE 'cambio_estado' TO 'cambio_estado_externo';"
    )

    # 2. Agregar el nuevo value para cambios internos del usuario sobre su pipeline
    op.execute(
        "ALTER TYPE notif_tipo ADD VALUE IF NOT EXISTS 'cambio_estado_interno';"
    )

    # PostgreSQL marca el nuevo value como "pending" dentro de la transacción actual.
    # No se puede usar hasta que esa transacción haga COMMIT. Se commitea explícitamente
    # para que el UPDATE del paso 3 pueda referenciar el nuevo value.
    op.get_bind().execute(sa.text("COMMIT"))

    # 3. Reclasificar histórico: todas las notificaciones existentes con el
    #    value (ahora renombrado) fueron generadas por acciones internas del
    #    usuario en pipeline.py — no por ChileCompra. Se pasan a cambio_estado_interno.
    op.execute("""
        UPDATE notificaciones
           SET tipo = 'cambio_estado_interno'
         WHERE tipo = 'cambio_estado_externo';
    """)

    # 4. Campo nuevo en pipeline_items para rastrear el último estado
    #    de ChileCompra conocido para esa licitación (por empresa).
    op.execute("""
        ALTER TABLE pipeline_items
            ADD COLUMN IF NOT EXISTS ultimo_estado_licitacion licitacion_estado;
    """)

    # 5. Índice único parcial para idempotencia de alertas externas.
    #    La columna 'datos' es JSONB (DEFAULT '{}'::jsonb en notificaciones).
    #    Clave: (empresa_id, licitacion_codigo, estado_anterior, estado_nuevo)
    #    Solo aplica para notificaciones de tipo cambio_estado_externo.
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_notif_state_change_dedup
            ON notificaciones (
                empresa_id,
                licitacion_codigo,
                (datos->>'estado_anterior'),
                (datos->>'estado_nuevo')
            )
            WHERE tipo = 'cambio_estado_externo';
    """)


def downgrade() -> None:
    # NOTA: Este downgrade es parcial.
    # ALTER TYPE ... RENAME VALUE no es reversible de forma directa en PostgreSQL
    # si hay filas usando ese value. Se documenta la limitación.
    #
    # Para un downgrade completo se requeriría:
    # 1. Crear un nuevo tipo temporal
    # 2. Migrar columnas
    # 3. Dropear el viejo tipo
    # Lo cual es destructivo. Se acepta como deuda documentada.

    op.execute("DROP INDEX IF EXISTS uq_notif_state_change_dedup;")

    op.execute("""
        ALTER TABLE pipeline_items
            DROP COLUMN IF EXISTS ultimo_estado_licitacion;
    """)

    # Revertir filas reclasificadas (sin garantía si hay nuevas notificaciones
    # internas creadas después del upgrade — esas también quedarían como externo)
    op.execute("""
        UPDATE notificaciones
           SET tipo = 'cambio_estado_externo'
         WHERE tipo = 'cambio_estado_interno';
    """)

    # No se puede RENAME VALUE de vuelta fácilmente.
    # cambio_estado_externo queda en el enum — limitación documentada.
    # cambio_estado_interno tampoco se puede eliminar de un enum en PG.
