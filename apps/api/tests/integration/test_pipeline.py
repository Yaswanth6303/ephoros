"""Spec §12 "Pipeline e2e": simulator → events.raw → ingest → core.events, labels kept apart."""

from datetime import UTC, datetime

import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from ephoros_api.adapters.db.events import SqlEventStore
from ephoros_api.adapters.redis_streams import DLQ_STREAM, GROUP, RAW_STREAM, RedisEventBus
from ephoros_api.services.ingest import IngestService
from ephoros_sim.generate import generate
from ephoros_sim.labels import write_labels
from ephoros_sim.replay import publish

START = datetime(2026, 1, 5, 8, 0, tzinfo=UTC)


async def scalar(engine: AsyncEngine, sql: str) -> int:
    async with engine.connect() as conn:
        return (await conn.execute(text(sql))).scalar_one()


@pytest.mark.anyio
async def test_write_labels_is_idempotent(postgres_url: str, engine: AsyncEngine) -> None:
    records = generate(7, START)
    await write_labels(postgres_url, records, run_id="seed7")
    await write_labels(postgres_url, records, run_id="seed7")
    assert await scalar(engine, "select count(*) from core.event_labels") == len(records)


@pytest.mark.anyio
async def test_simulated_run_lands_in_postgres(
    postgres_url: str, engine: AsyncEngine, redis: Redis
) -> None:
    records = generate(7, START)
    await write_labels(postgres_url, records, run_id="seed7")
    await publish(redis, records)

    bus = RedisEventBus(redis, "pipeline")
    await bus.ensure_group()
    service = IngestService(SqlEventStore(engine), bus)
    while batch := await bus.read(500, 100):
        await service.handle(batch)

    assert await scalar(engine, "select count(*) from core.events") == len(records)
    assert await redis.xlen(DLQ_STREAM) == 0
    assert (await redis.xpending(RAW_STREAM, GROUP))["pending"] == 0
    assert await redis.xlen(RAW_STREAM) == 0  # processed entries are deleted, replays don't grow it
    joined = "select count(*) from core.events join core.event_labels using (event_id)"
    assert await scalar(engine, joined) == len(records)
