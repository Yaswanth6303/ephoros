"""Real Postgres for integration tests (Testcontainers), migrated with Alembic."""

from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from testcontainers.community.postgres import PostgresContainer
from testcontainers.community.redis import RedisContainer

from ephoros_api.adapters.db.engine import create_engine

ALEMBIC_INI = Path(__file__).parents[2] / "alembic.ini"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if "/integration/" in str(item.path):
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    with PostgresContainer("postgres:17.11-alpine", driver=None) as pg:
        url = pg.get_connection_url()
        config = Config(str(ALEMBIC_INI))
        config.set_main_option("sqlalchemy.url", url)
        command.upgrade(config, "head")
        yield url


@pytest.fixture
async def engine(postgres_url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_engine(postgres_url)
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE core.events, core.event_labels"))
    yield engine
    await engine.dispose()


@pytest.fixture(scope="session")
def redis_url() -> Iterator[str]:
    with RedisContainer("redis:7.4.11-alpine") as container:
        yield f"redis://{container.get_container_host_ip()}:{container.get_exposed_port(6379)}/0"


@pytest.fixture
async def redis(redis_url: str) -> AsyncIterator[Redis]:
    client = Redis.from_url(redis_url, decode_responses=True)
    await client.flushdb()
    yield client
    await client.aclose()
