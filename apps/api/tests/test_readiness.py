import asyncio
import time

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from ephoros_api.api.v1.health import Check, get_checks


async def ok() -> None:
    pass


async def refused() -> None:
    raise ConnectionRefusedError("postgres://ephoros:secret@db:5432")


async def hangs() -> None:
    await asyncio.sleep(30)


def use(app: FastAPI, checks: dict[str, Check]) -> None:
    app.dependency_overrides[get_checks] = lambda: checks


@pytest.mark.anyio
async def test_readyz_all_ok(app: FastAPI, client: AsyncClient) -> None:
    use(app, {"postgres": ok, "redis": ok})
    r = await client.get("/api/v1/readyz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "checks": {"postgres": "ok", "redis": "ok"}}


@pytest.mark.anyio
async def test_readyz_reports_failed_dependency(app: FastAPI, client: AsyncClient) -> None:
    use(app, {"postgres": refused, "redis": ok})
    r = await client.get("/api/v1/readyz")
    assert r.status_code == 503
    assert r.headers["content-type"] == "application/problem+json"
    body = r.json()
    assert body["status"] == 503 and body["title"] == "Service Unavailable"
    assert body["checks"] == {"postgres": "fail: ConnectionRefusedError", "redis": "ok"}


@pytest.mark.anyio
async def test_readyz_hides_error_details(app: FastAPI, client: AsyncClient) -> None:
    use(app, {"postgres": refused, "redis": ok})
    assert "secret" not in (await client.get("/api/v1/readyz")).text


@pytest.mark.anyio
async def test_readyz_times_out_slow_dependency(app: FastAPI, client: AsyncClient) -> None:
    use(app, {"postgres": hangs, "redis": hangs})
    start = time.monotonic()
    r = await client.get("/api/v1/readyz")
    assert r.status_code == 503
    assert r.json()["checks"] == {"postgres": "fail: TimeoutError", "redis": "fail: TimeoutError"}
    assert time.monotonic() - start < 3.0  # checks run concurrently, readiness_timeout_s = 2.0
