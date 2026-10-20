import pytest
from fastapi import FastAPI
from httpx import AsyncClient


@pytest.mark.anyio
async def test_unknown_route_is_problem_json(client: AsyncClient) -> None:
    r = await client.get("/api/v1/does-not-exist")
    assert r.status_code == 404
    assert r.headers["content-type"] == "application/problem+json"
    assert r.json()["status"] == 404


@pytest.mark.anyio
async def test_validation_error_is_problem_json(app: FastAPI, client: AsyncClient) -> None:
    @app.get("/api/v1/_echo")
    async def echo(n: int) -> int:
        return n

    r = await client.get("/api/v1/_echo", params={"n": "not-a-number"})
    assert r.status_code == 422
    assert r.headers["content-type"] == "application/problem+json"
    body = r.json()
    assert body["status"] == 422
    assert body["errors"][0]["loc"] == ["query", "n"]


@pytest.mark.anyio
async def test_error_headers_survive(client: AsyncClient) -> None:
    r = await client.post("/api/v1/healthz")
    assert r.status_code == 405
    assert r.headers["content-type"] == "application/problem+json"
    assert r.headers["allow"] == "GET"
