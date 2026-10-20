from collections.abc import Sequence
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import ResponseError

from ephoros_api.domain.ports import StreamMessage

RAW_STREAM = "events.raw"
DLQ_STREAM = "events.dlq"
GROUP = "workers"


class RedisEventBus:
    """Consumer-group reader for events.raw. The client must use decode_responses=True."""

    def __init__(self, client: Redis, consumer: str) -> None:
        self.client, self.consumer = client, consumer

    async def ensure_group(self) -> None:
        try:
            await self.client.xgroup_create(RAW_STREAM, GROUP, id="0", mkstream=True)
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def read(self, count: int, block_ms: int) -> list[StreamMessage]:
        # redis-py types replies loosely; shapes per the Streams docs
        response: Any = await self.client.xreadgroup(
            GROUP, self.consumer, {RAW_STREAM: ">"}, count=count, block=block_ms
        )
        return [
            StreamMessage(id, fields)
            for _stream, entries in response or []
            for id, fields in entries
        ]

    async def claim_stale(self, min_idle_ms: int, count: int) -> list[StreamMessage]:
        reply: Any = await self.client.xautoclaim(
            RAW_STREAM, GROUP, self.consumer, min_idle_time=min_idle_ms, start_id="0-0", count=count
        )
        _next, entries, _deleted = reply
        return [StreamMessage(id, fields) for id, fields in entries]

    async def ack(self, ids: Sequence[str]) -> None:
        if ids:
            await self.client.xack(RAW_STREAM, GROUP, *ids)

    async def dead_letter(self, fields: dict[str, str]) -> None:
        await self.client.xadd(DLQ_STREAM, fields)  # type: ignore[arg-type]
