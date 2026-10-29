import socket
import time
from typing import Annotated

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from jwt_factory import FakeJWKClient, make_token

from ephoros_api.api.auth import Principal, get_jwk_client, require_role
from ephoros_api.app import create_app
from ephoros_api.config import Settings

KEY = Ed25519PrivateKey.generate()


@pytest.fixture(autouse=True)
def trusted_key(app: FastAPI) -> None:
    app.dependency_overrides[get_jwk_client] = lambda: FakeJWKClient(KEY)


@pytest.fixture
def admin_route(app: FastAPI) -> None:
    @app.get("/api/v1/_admin")
    def admin_only(user: Annotated[Principal, Depends(require_role("admin"))]) -> str:
        return user.sub


def bearer(token: str) -> dict[str, str]:
    return {"authorization": f"Bearer {token}"}


async def status_for(client: AsyncClient, token: str) -> int:
    return (await client.get("/api/v1/me", headers=bearer(token))).status_code


@pytest.mark.anyio
async def test_me_returns_the_principal(client: AsyncClient) -> None:
    r = await client.get("/api/v1/me", headers=bearer(make_token(KEY)))
    assert r.status_code == 200
    assert r.json() == {
        "sub": "user-1",
        "email": "ana@ephoros.test",
        "name": "Ana",
        "role": "analyst",
    }


PUBLIC_PATHS = {"/api/v1/healthz", "/api/v1/readyz"}  # probes and healthchecks call these


@pytest.mark.anyio
async def test_every_api_route_except_probes_requires_a_token(
    app: FastAPI, client: AsyncClient
) -> None:
    # the OpenAPI document lists every operation (FastAPI 0.150 nests included routers privately)
    operations = [
        (method, path)
        for path, ops in app.openapi()["paths"].items()
        if path not in PUBLIC_PATHS
        for method in ops
    ]
    assert operations
    for method, path in operations:
        assert (await client.request(method, path)).status_code == 401, (method, path)


@pytest.mark.anyio
async def test_missing_token_is_401_with_challenge(client: AsyncClient) -> None:
    r = await client.get("/api/v1/me")
    assert r.status_code == 401
    assert r.headers["content-type"] == "application/problem+json"
    assert r.headers["www-authenticate"] == "Bearer"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"exp": int(time.time()) - 60}, id="expired"),
        pytest.param({"aud": "someone-else"}, id="wrong-audience"),
        pytest.param({"iss": "https://evil.test"}, id="wrong-issuer"),
        pytest.param({"role": "root"}, id="unknown-role"),
    ],
)
async def test_invalid_claims_are_401(client: AsyncClient, overrides: dict[str, object]) -> None:
    assert await status_for(client, make_token(KEY, **overrides)) == 401


@pytest.mark.anyio
async def test_token_signed_by_another_key_is_401(client: AsyncClient) -> None:
    assert await status_for(client, make_token(Ed25519PrivateKey.generate())) == 401


@pytest.mark.anyio
async def test_hs256_token_is_401(client: AsyncClient) -> None:
    # alg confusion: HMAC "signed" with the server's public key bytes
    public = KEY.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    forged = jwt.decode(make_token(KEY), options={"verify_signature": False})
    assert await status_for(client, jwt.encode(forged, public, algorithm="HS256")) == 401


@pytest.mark.anyio
async def test_unsigned_token_is_401(client: AsyncClient) -> None:
    claims = jwt.decode(make_token(KEY), options={"verify_signature": False})
    assert await status_for(client, jwt.encode(claims, None, algorithm="none")) == 401


@pytest.mark.anyio
@pytest.mark.parametrize(
    "error",
    [jwt.PyJWKClientConnectionError("jwks down"), jwt.PyJWKClientError("unknown kid")],
    ids=["jwks-unreachable", "unknown-kid"],
)
async def test_jwks_failures_are_401(app: FastAPI, client: AsyncClient, error: Exception) -> None:
    app.dependency_overrides[get_jwk_client] = lambda: FakeJWKClient(error=error)
    assert await status_for(client, make_token(KEY)) == 401


@pytest.mark.anyio
async def test_analyst_on_admin_route_is_403(client: AsyncClient, admin_route: None) -> None:
    r = await client.get("/api/v1/_admin", headers=bearer(make_token(KEY)))
    assert r.status_code == 403
    assert r.headers["content-type"] == "application/problem+json"


@pytest.mark.anyio
async def test_admin_on_admin_route_is_200(client: AsyncClient, admin_route: None) -> None:
    r = await client.get("/api/v1/_admin", headers=bearer(make_token(KEY, role="admin")))
    assert r.status_code == 200


@pytest.mark.anyio
async def test_hanging_jwks_endpoint_fails_fast(settings: Settings) -> None:
    # accepts TCP connections but never answers, like a paused auth container
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen()
        port = server.getsockname()[1]
        app = create_app(settings.model_copy(update={"jwks_url": f"http://127.0.0.1:{port}/jwks"}))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            start = time.monotonic()
            r = await c.get("/api/v1/me", headers=bearer(make_token(KEY)))
        assert r.status_code == 401
        assert time.monotonic() - start < 3.5
