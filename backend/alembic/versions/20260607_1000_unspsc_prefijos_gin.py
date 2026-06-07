"""Agrega unspsc_prefijos text[] + GIN index + trigger de mantenimiento automático.

La columna desnormaliza los prefijos UNSPSC de todos los ítems de cada
licitación (segmento 2 dígitos, familia 4, clase 6, commodity 8).

Para un ítem con unspsc_codigo='73101502' almacena: ['73','7310','731015','73101502'].
El trigger trg_items_refresh_unspsc recalcula el array completo de la licitación
cada vez que se inserta, actualiza o elimina un LicitacionItem.

El índice GIN sobre unspsc_prefijos permite el operador de contención (@>)
en O(log N) — reemplaza el correlated EXISTS + LIKE que hacía sequential scan
con locales UTF-8.

Revision ID: 20260607_1000
Revises: 20260607_0930
Create Date: 2026-06-07
"""

from alembic import op

revision = "20260607_1000"
down_revision = "20260607_0930"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Columna nullable — el backfill la puebla para licitaciones históricas.
    # Las nuevas licitaciones la reciben via trigger al cargar sus ítems.
    op.execute(
        "ALTER TABLE licitaciones ADD COLUMN IF NOT EXISTS unspsc_prefijos text[]"
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_licitaciones_unspsc_gin
        ON licitaciones USING gin (unspsc_prefijos)
        """
    )

    # Función que recalcula unspsc_prefijos para una licitación concreta.
    # generate_series(2,8,2) → 2,4,6,8 (los 4 niveles del estándar UNSPSC).
    # SUBSTRING extrae el prefijo de cada nivel a partir del código de 8 dígitos.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION fn_refresh_unspsc_prefijos() RETURNS trigger AS $$
        DECLARE
          lc text;
        BEGIN
          lc := COALESCE(NEW.licitacion_codigo, OLD.licitacion_codigo);
          UPDATE licitaciones
          SET unspsc_prefijos = (
            SELECT array_agg(DISTINCT prefijo)
            FROM licitacion_items li
            CROSS JOIN LATERAL (
              SELECT SUBSTRING(li.unspsc_codigo, 1, n) AS prefijo
              FROM generate_series(2, 8, 2) n
              WHERE LENGTH(li.unspsc_codigo) >= n
            ) AS p
            WHERE li.licitacion_codigo = lc
              AND li.unspsc_codigo IS NOT NULL
          )
          WHERE codigo = lc;
          RETURN NULL;
        END;
        $$ LANGUAGE plpgsql
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_items_refresh_unspsc
        AFTER INSERT OR DELETE OR UPDATE OF unspsc_codigo
        ON licitacion_items
        FOR EACH ROW
        EXECUTE FUNCTION fn_refresh_unspsc_prefijos()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_items_refresh_unspsc ON licitacion_items")
    op.execute("DROP FUNCTION IF EXISTS fn_refresh_unspsc_prefijos()")
    op.execute("DROP INDEX IF EXISTS idx_licitaciones_unspsc_gin")
    op.execute("ALTER TABLE licitaciones DROP COLUMN IF EXISTS unspsc_prefijos")
