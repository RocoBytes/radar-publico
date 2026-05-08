"""Entrypoint de Alembic para migraciones async.

Lee DATABASE_URL_SYNC desde las variables de entorno (no desde config.py
para evitar importar la app completa durante las migraciones).
"""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Importar Base para que Alembic detecte los modelos automáticamente
# Se van agregando los modelos aquí cuando se creen en Sprint 1+
from app.db.base import Base  # noqa: F401

# import app.models  # noqa: F401  ← descomentar cuando existan modelos

config = context.config

# Leer logging desde alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata de los modelos (para autogenerate)
target_metadata = Base.metadata

# Leer DATABASE_URL desde el entorno (sync, porque Alembic no es async)
database_url_sync = os.environ.get(
    "DATABASE_URL_SYNC",
    "postgresql://radar:radar_dev_password@localhost:5432/radar",
)
config.set_main_option("sqlalchemy.url", database_url_sync)


def run_migrations_offline() -> None:
    """Ejecuta migraciones en modo offline (sin conexión activa)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Ejecuta migraciones en modo online (con conexión activa)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
