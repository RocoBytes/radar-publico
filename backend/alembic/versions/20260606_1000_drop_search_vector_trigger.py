"""Reemplaza trigger search_vector con columna GENERATED ALWAYS AS STORED.

El trigger anterior se ejecutaba en cada INSERT y UPDATE, generando I/O
destructivo durante los backfills masivos nocturnos. La columna generada
logra el mismo resultado nativo en PostgreSQL 12+ sin overhead de trigger.

Revision ID: 20260606_1000
Revises: 20260604_1000
Create Date: 2026-06-06
"""

from alembic import op

revision = "20260606_1000"
down_revision = "20260604_1000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_licitaciones_search_vector ON licitaciones")
    op.execute("DROP FUNCTION IF EXISTS update_licitacion_search_vector()")
    op.execute("DROP INDEX IF EXISTS idx_licitaciones_search")
    op.execute("ALTER TABLE licitaciones DROP COLUMN search_vector")
    op.execute(
        """
        ALTER TABLE licitaciones ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('es_unaccent', coalesce(nombre, '')), 'A') ||
            setweight(to_tsvector('es_unaccent', coalesce(descripcion, '')), 'B')
        ) STORED
        """
    )
    op.execute(
        "CREATE INDEX idx_licitaciones_search ON licitaciones USING gin (search_vector)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_licitaciones_search")
    op.execute("ALTER TABLE licitaciones DROP COLUMN search_vector")
    op.execute("ALTER TABLE licitaciones ADD COLUMN search_vector tsvector")
    op.execute(
        "CREATE INDEX idx_licitaciones_search ON licitaciones USING gin (search_vector)"
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_licitacion_search_vector() RETURNS trigger AS $$
        BEGIN
          NEW.search_vector :=
            setweight(to_tsvector('es_unaccent', coalesce(NEW.nombre, '')), 'A') ||
            setweight(to_tsvector('es_unaccent', coalesce(NEW.descripcion, '')), 'B');
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_licitaciones_search_vector
        BEFORE INSERT OR UPDATE OF nombre, descripcion ON licitaciones
        FOR EACH ROW EXECUTE FUNCTION update_licitacion_search_vector()
        """
    )
