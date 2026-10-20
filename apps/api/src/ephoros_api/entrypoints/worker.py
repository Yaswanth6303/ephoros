"""Worker process: consumes events.raw until SIGTERM/SIGINT (spec §3.1)."""

import asyncio
import logging
import os
import signal
import socket

from redis.asyncio import Redis

from ephoros_api.adapters.db.engine import create_engine
from ephoros_api.adapters.db.events import SqlEventStore
from ephoros_api.adapters.redis_streams import RedisEventBus
from ephoros_api.config import Settings
from ephoros_api.services.ingest import IngestService


async def _run() -> None:
    settings = Settings()  # fields come from env
    engine = create_engine(settings.database_url)
    client = Redis.from_url(settings.redis_url, decode_responses=True)
    bus = RedisEventBus(client, f"{socket.gethostname()}-{os.getpid()}")
    await bus.ensure_group()
    stop = asyncio.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        asyncio.get_running_loop().add_signal_handler(sig, stop.set)
    try:
        await IngestService(SqlEventStore(engine), bus).run(stop)
    finally:
        await client.aclose()
        await engine.dispose()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    asyncio.run(_run())
