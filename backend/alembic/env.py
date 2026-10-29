import asyncio
import os
from logging.config import fileConfig

from alembic import context
from dotenv import dotenv_values
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import ENV_FILE
from app.models import Base

config = context.config

if config.config_file_name is not None and not config.attributes.get("database_url"):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _database_url() -> str:
    """Tests pass the URL via config.attributes; otherwise use DATABASE_URL from the env or backend/.env.
    Only the URL is read here, so migrations don't need the Meta secrets to be configured."""
    url = (
        config.attributes.get("database_url")
        or os.environ.get("DATABASE_URL")
        or dotenv_values(ENV_FILE).get("DATABASE_URL")
    )
    if not url:
        raise RuntimeError("DATABASE_URL is not set (see backend/.env.example)")
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(_database_url(), poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
