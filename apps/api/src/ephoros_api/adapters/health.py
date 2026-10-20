import asyncpg
import redis.asyncio as redis


async def ping_postgres(dsn: str) -> None:
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute("SELECT 1")
    finally:
        await conn.close()


async def ping_redis(url: str) -> None:
    client = redis.from_url(url)
    try:
        await client.ping()
    finally:
        await client.aclose()
