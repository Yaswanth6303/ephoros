import asyncpg
import redis.asyncio as redis


async def ping_postgres(dsn: str) -> None:
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute("SELECT 1")
    finally:
        # terminate, not close: close() waits forever on a stalled server and would hang /readyz
        conn.terminate()


async def ping_redis(url: str) -> None:
    client = redis.from_url(url)
    try:
        await client.ping()
    finally:
        await client.aclose()
