import asyncio
import json

import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from ephoros_api.adapters.db.events import SqlEventStore
from ephoros_api.adapters.redis_streams import DLQ_STREAM, GROUP, RAW_STREAM, RedisEventBus
from ephoros_api.services.ingest import IngestService
from ephoros_detection.ids import uuid7


def envelope(n: int) -> dict[str, str]:
    raw = {
        "requestReceivedTimestamp": f"2026-01-05T08:00:0{n}Z",
        "verb": "create",
        "user": {"username": "alice"},
        "sourceIPs": ["10.0.0.1"],
        "objectRef": {"resource": "pods", "namespace": "ci", "name": f"p{n}", "uid": f"u{n}"},
        "responseStatus": {"code": 201},
    }
    return {"event_id": str(uuid7()), "source": "k8s", "raw": json.dumps(raw)}


async def count_events(engine: AsyncEngine) -> int:
    async with engine.connect() as conn:
        return (await conn.execute(text("select count(*) from core.events"))).scalar_one()


@pytest.mark.anyio
async def test_worker_drains_the_stream(redis: Redis, engine: AsyncEngine) -> None:
    bus = RedisEventBus(redis, "worker-1")
    await bus.ensure_group()
    for n in range(5):
        await redis.xadd(RAW_STREAM, envelope(n))
    await redis.xadd(RAW_STREAM, {"event_id": str(uuid7()), "source": "k8s", "raw": "garbage"})

    stop = asyncio.Event()
    task = asyncio.create_task(IngestService(SqlEventStore(engine), bus).run(stop))
    async with asyncio.timeout(10):
        while await count_events(engine) < 5 or await redis.xlen(DLQ_STREAM) < 1:  # noqa: ASYNC110 -- polls external state
            await asyncio.sleep(0.05)
    stop.set()
    await task

    assert await count_events(engine) == 5
    assert await redis.xlen(DLQ_STREAM) == 1
    assert (await redis.xpending(RAW_STREAM, GROUP))["pending"] == 0


@pytest.mark.anyio
async def test_stuck_pending_message_is_reclaimed(redis: Redis, engine: AsyncEngine) -> None:
    crashed, survivor = RedisEventBus(redis, "crashed"), RedisEventBus(redis, "survivor")
    await crashed.ensure_group()
    await redis.xadd(RAW_STREAM, envelope(1))
    assert len(await crashed.read(10, 100)) == 1  # read, then "crash" before acking

    stale = await survivor.claim_stale(min_idle_ms=0, count=10)
    assert len(stale) == 1
    await IngestService(SqlEventStore(engine), survivor).handle(stale)

    assert await count_events(engine) == 1
    assert (await redis.xpending(RAW_STREAM, GROUP))["pending"] == 0
