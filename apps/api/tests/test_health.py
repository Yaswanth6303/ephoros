import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_healthz_is_ok(client: AsyncClient) -> None:
    r = await client.get("/api/v1/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_operation_ids_are_function_names(client: AsyncClient) -> None:
    spec = (await client.get("/openapi.json")).json()
    assert spec["paths"]["/api/v1/healthz"]["get"]["operationId"] == "healthz"
