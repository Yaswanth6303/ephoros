from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI
from httpx import AsyncClient
from jwt_factory import FakeJWKClient, make_token

from ephoros_api.api.auth import get_jwk_client
from ephoros_api.api.v1.events import get_event_store
from ephoros_detection.events import Event
from ephoros_detection.ids import uuid7

KEY = Ed25519PrivateKey.generate()
T0 = datetime(2026, 1, 5, 8, 0, tzinfo=UTC)


def make_event(minute: int) -> Event:
    at = T0 + timedelta(minutes=minute)
    return Event.model_validate(
        {
            "event_id": uuid7(int(at.timestamp() * 1000)),
            "source": "identity",
            "category": "session",
            "action": "login",
            "outcome": "success",
            "observed_at": at,
            "actor": {"principal_id": "ana", "principal_type": "user"},
            "resource": {"resource_uid": "s1", "kind": "Session"},
            "raw": {"secret_evidence": "do-not-leak"},
        }
    )


class FakeStore:
    def __init__(self, events: list[Event]) -> None:
        self.events = sorted(events, key=lambda e: (e.observed_at, e.event_id))

    async def add_many(self, events: Sequence[Event]) -> int:
        raise NotImplementedError

    async def page(self, *, limit: int, after: tuple[datetime, UUID] | None) -> list[Event]:
        rest = [e for e in self.events if after is None or (e.observed_at, e.event_id) > after]
        return rest[:limit]


@pytest.fixture(autouse=True)
def wiring(app: FastAPI) -> None:
    app.dependency_overrides[get_jwk_client] = lambda: FakeJWKClient(KEY)
    store = FakeStore([make_event(i) for i in range(3)])  # one store per test: ids stay stable
    app.dependency_overrides[get_event_store] = lambda: store


AUTH = {"authorization": f"Bearer {make_token(KEY)}"}


@pytest.mark.anyio
async def test_events_requires_auth(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/events")).status_code == 401


@pytest.mark.anyio
async def test_first_page_and_cursor(client: AsyncClient) -> None:
    first = (await client.get("/api/v1/events", params={"limit": 2}, headers=AUTH)).json()
    assert len(first["items"]) == 2 and first["next_cursor"]
    second = await client.get(
        "/api/v1/events", params={"limit": 2, "cursor": first["next_cursor"]}, headers=AUTH
    )
    ids = [e["event_id"] for e in first["items"] + second.json()["items"]]
    assert len(ids) == len(set(ids)) == 3


@pytest.mark.anyio
async def test_last_page_has_no_cursor(client: AsyncClient) -> None:
    body = (await client.get("/api/v1/events", params={"limit": 50}, headers=AUTH)).json()
    assert len(body["items"]) == 3 and body["next_cursor"] is None


@pytest.mark.anyio
@pytest.mark.parametrize("limit", [0, 201])
async def test_limit_out_of_range_is_422(client: AsyncClient, limit: int) -> None:
    r = await client.get("/api/v1/events", params={"limit": limit}, headers=AUTH)
    assert r.status_code == 422


@pytest.mark.anyio
@pytest.mark.parametrize(
    "cursor", ["not-base64!", "Zm9v", "MjAyNi0wMS0wNVQwODowMDowMCswMDowMHxub3QtYS11dWlk"]
)
async def test_bad_cursor_is_400(client: AsyncClient, cursor: str) -> None:
    r = await client.get("/api/v1/events", params={"cursor": cursor}, headers=AUTH)
    assert r.status_code == 400
    assert r.headers["content-type"] == "application/problem+json"


@pytest.mark.anyio
async def test_raw_is_not_exposed(client: AsyncClient) -> None:
    r = await client.get("/api/v1/events", headers=AUTH)
    assert "raw" not in r.json()["items"][0] and "do-not-leak" not in r.text
