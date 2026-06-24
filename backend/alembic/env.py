"""Alembic environment configuration for async SQLAlchemy engine.

This env.py is wired to the application's async engine and metadata so
``alembic revision --autogenerate`` detects model changes automatically.
"""

import asyncio
import logging
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.core.database import Base

# -- Load all models so Base.metadata is fully populated -------------------
# Import order ensures FKs are resolved correctly.
import app.models.memo          # noqa: F401
import app.models.wiki          # noqa: F401
import app.models.chat          # noqa: F401
import app.models.compile_job   # noqa: F401
import app.models.game          # noqa: F401
import app.models.multi_agent   # noqa: F401
import app.models.settings      # noqa: F401
import app.models.user          # noqa: F401

# Alembic Config object (provides access to .ini values)
config = context.config

# Set up Python logging from alembic.ini [loggers] section
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

logger = logging.getLogger("alembic.env")

# -- Metadata --------------------------------------------------------------
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generate SQL script).

    Requires a sqlalchemy.url in alembic.ini or passed via -x.
    """
    url = config.get_main_option("sqlalchemy.url") or settings.database_url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    """Synchronous callback executed inside run_sync()."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode using an async engine."""
    database_url = settings.database_url

    # Support async SQLite (the default) as well as asyncpg
    connectable = create_async_engine(database_url, echo=False)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
