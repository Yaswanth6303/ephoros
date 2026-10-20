"""Alembic for schema `core` only (schema `auth` belongs to Better Auth / Drizzle)."""

import asyncio
import os

from alembic import context
from sqlalchemy import text
from sqlalchemy.engine import Connection

from ephoros_api.adapters.db.engine import create_engine
from ephoros_api.adapters.db.tables import metadata

config = context.config


def run(connection: Connection) -> None:
    connection.execute(text("CREATE SCHEMA IF NOT EXISTS core"))
    context.configure(
        connection=connection,
        target_metadata=metadata,
        version_table_schema="core",
        include_schemas=True,
        include_name=lambda name, type_, _: type_ != "schema" or name == "core",
    )
    with context.begin_transaction():
        context.run_migrations()


async def main() -> None:
    engine = create_engine(config.get_main_option("sqlalchemy.url") or os.environ["DATABASE_URL"])
    async with engine.begin() as conn:
        await conn.run_sync(run)
    await engine.dispose()


asyncio.run(main())
