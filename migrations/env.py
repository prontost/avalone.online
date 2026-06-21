import asyncio
import os

from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config

from counta.db.models import Base

config = context.config
target_metadata = Base.metadata

database_url = os.environ.get(
    "COUNTA_DATABASE_URL", "postgresql+asyncpg://localhost/counta"
)
config.set_main_option("sqlalchemy.url", database_url)


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_offline() -> None:
    context.configure(url=database_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
