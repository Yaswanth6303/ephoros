import asyncio

import pytest

from ephoros_api.adapters import health


class StalledConnection:
    """Postgres that accepted the connection, then froze (asyncpg's close() waits forever)."""

    terminated = False

    async def execute(self, *_: object, **__: object) -> None:
        await asyncio.sleep(3600)

    async def close(self, **_: object) -> None:
        await asyncio.sleep(3600)

    def terminate(self) -> None:
        self.terminated = True


@pytest.mark.anyio
async def test_ping_postgres_gives_up_on_a_stalled_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = StalledConnection()

    async def connect(*_: object, **__: object) -> StalledConnection:
        return conn

    monkeypatch.setattr(health.asyncpg, "connect", connect)
    async with asyncio.timeout(2):  # guard: a hang fails the test instead of blocking the suite
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(health.ping_postgres("postgresql://x"), 0.1)
    assert conn.terminated
