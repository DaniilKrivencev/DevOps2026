"""Alembic environment — async engine, reads DATABASE_URL from environment."""

import asyncio
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import create_async_engine

import app.models  # noqa: F401 — импорт регистрирует модели в Base.metadata
from alembic import context
from app.config import get_database_url
from app.database import Base

# Alembic Config object
config = context.config

# Setup Python logging from alembic.ini (не отключая логгеры pytest)
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata

# URL можно передать программно (тесты миграций): config.attributes["database_url"]
DATABASE_URL = config.attributes.get("database_url") or get_database_url()


def run_migrations_offline() -> None:
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    if connection.dialect.name == "sqlite":
        # batch-миграции в SQLite пересоздают таблицы (DROP + RENAME). При включённых
        # внешних ключах DROP deputies срабатывал как ON DELETE SET NULL и обнулял
        # commissions.chair_id — потеря данных, найденная тестом миграции с данными.
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.commit()
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=connection.dialect.name == "sqlite",
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = create_async_engine(DATABASE_URL, echo=False)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
