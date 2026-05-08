"""Base declarativa de SQLAlchemy.

Todos los modelos deben importar Base desde aquí.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base para todos los modelos SQLAlchemy del proyecto."""

    pass
