from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from ephoros_api.adapters.db.events import SqlEventStore
from ephoros_detection.events import Event
from ephoros_detection.ids import uuid7

T0 = datetime(2026, 1, 5, 8, 0, tzinfo=UTC)


def make_event(minute: int) -> Event:
    at = T0 + timedelta(minutes=minute)
    return Event.model_validate(
        {
            "event_id": uuid7(int(at.timestamp() * 1000)),
            "source": "k8s",
            "category": "resource_lifecycle",
            "action": "create",
            "outcome": "success",
            "observed_at": at,
            "ingested_at": at + timedelta(seconds=1),
            "actor": {"principal_id": "alice", "principal_type": "user", "source_ip": "10.0.0.1"},
            "resource": {
                "resource_uid": f"pod-{minute}",
                "kind": "Pod",
                "name": f"p{minute}",
                "namespace": "ci",
                "labels": {"app": "build"},
                "owner_ref": {"kind": "Job", "name": "j", "uid": "u"},
            },
            "attributes": {"privileged": True, "command": "make test"},
            "raw": {"verb": "create", "nested": {"a": [1, 2]}},
        }
    )


@pytest.mark.anyio
async def test_add_many_is_idempotent(engine: AsyncEngine) -> None:
    store = SqlEventStore(engine)
    events = [make_event(i) for i in range(3)]
    assert await store.add_many(events) == 3
    assert await store.add_many(events) == 0
    async with engine.connect() as conn:
        assert (await conn.execute(text("select count(*) from core.events"))).scalar_one() == 3


@pytest.mark.anyio
async def test_page_is_keyset_ordered(engine: AsyncEngine) -> None:
    store = SqlEventStore(engine)
    events = [make_event(i) for i in (4, 0, 3, 1, 2)]
    await store.add_many(events)
    pages, after = [], None
    while page := await store.page(limit=2, after=after):
        pages.append([e.event_id for e in page])
        after = (page[-1].observed_at, page[-1].event_id)
    assert [len(p) for p in pages] == [2, 2, 1]
    expected = [e.event_id for e in sorted(events, key=lambda e: (e.observed_at, e.event_id))]
    assert [i for p in pages for i in p] == expected


@pytest.mark.anyio
async def test_event_round_trips(engine: AsyncEngine) -> None:
    store = SqlEventStore(engine)
    original = make_event(0)
    await store.add_many([original])
    assert (await store.page(limit=1, after=None)) == [original]


@pytest.mark.anyio
async def test_add_many_with_nothing_is_a_no_op(engine: AsyncEngine) -> None:
    assert await SqlEventStore(engine).add_many([]) == 0
