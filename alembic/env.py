from __future__ import annotations

import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.config import settings
from app.db import models  # noqa: F401 — efeito colateral: registra os modelos
from app.db.base import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _sync_url(url: str) -> str:
    """Alembic não fala asyncpg — converte para psycopg."""
    return url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)


# ALEMBIC_DATABASE_URL permite migrar o banco de teste sem tocar no .env.
url = os.getenv("ALEMBIC_DATABASE_URL") or settings.database_url
config.set_main_option("sqlalchemy.url", _sync_url(url))

target_metadata = Base.metadata

# Schemas que este projeto gerencia. Com include_schemas=True o autogenerate
# enxerga TODOS os schemas do banco e quereria dropar o que não é nosso.
MANAGED_SCHEMAS = {None, "public", "auth"}


def include_name(name, type_, parent_names) -> bool:  # noqa: ANN001
    if type_ == "schema":
        return name in MANAGED_SCHEMAS
    return True


_OPTS = dict(
    target_metadata=target_metadata,
    compare_type=True,
    compare_server_default=True,
    include_schemas=True,
    include_name=include_name,
)


def run_migrations_offline() -> None:
    """Gera SQL sem conectar: `alembic upgrade head --sql`."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **_OPTS,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, **_OPTS)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
