"""make documento_chunks embedding nullable

Revision ID: 20260604_0900
Revises: 20260603_1200
Create Date: 2026-06-04 09:00:00.000000

El task procesar_pdf inserta chunks sin embedding; embed_chunks_documento lo llena después.
La constraint NOT NULL era incorrecta para este flujo de dos pasos.
"""

from __future__ import annotations

from alembic import op

revision = "20260604_0900"
down_revision = "20260603_1200"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            ALTER TABLE documento_chunks ALTER COLUMN embedding DROP NOT NULL;
        EXCEPTION
            WHEN others THEN NULL;
        END $$;
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE documento_chunks ALTER COLUMN embedding SET NOT NULL;
    """)
