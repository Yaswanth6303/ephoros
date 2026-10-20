import json
from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

import pytest

from ephoros_api.domain.ports import StreamMessage
from ephoros_api.services.ingest import IngestService
from ephoros_detection.events import Event
from ephoros_detection.ids import uuid7

POD = {
    "requestReceivedTimestamp": "2026-01-05T08:00:00Z",
    "verb": "create",
    "user": {"username": "alice"},
    "sourceIPs": ["10.0.0.1"],
    "objectRef": {"resource": "pods", "namespace": "ci", "name": "p", "uid": "u1"},
    "responseStatus": {"code": 201},
}


def message(
    n: int, raw: object = POD, source: str = "k8s", event_id: str | None = None
) -> StreamMessage:
    fields = {"event_id": event_id or str(uuid7()), "source": source, "raw": json.dumps(raw)}
    return StreamMessage(id=f"1-{n}", fields=fields)


class FakeStore:
    def __init__(self, fail: bool = False) -> None:
        self.rows: dict[UUID, Event] = {}
        self.fail = fail

    async def add_many(self, events: Sequence[Event]) -> int:
        if self.fail:
            raise ConnectionError("database down")
        new = [e for e in events if e.event_id not in self.rows]
        self.rows |= {e.event_id: e for e in new}
        return len(new)

    async def page(self, *, limit: int, after: tuple[datetime, UUID] | None) -> list[Event]:
        raise NotImplementedError


class FakeBus:
    def __init__(self) -> None:
        self.acked: list[str] = []
        self.dlq: list[dict[str, str]] = []

    async def read(self, count: int, block_ms: int) -> list[StreamMessage]:
        return []

    async def claim_stale(self, min_idle_ms: int, count: int) -> list[StreamMessage]:
        return []

    async def ack(self, ids: Sequence[str]) -> None:
        self.acked += ids

    async def dead_letter(self, fields: dict[str, str]) -> None:
        self.dlq.append(fields)


@pytest.mark.anyio
async def test_valid_messages_are_stored_then_acked() -> None:
    store, bus = FakeStore(), FakeBus()
    result = await IngestService(store, bus).handle([message(1), message(2)])
    assert (result.stored, result.duplicates, result.dead_lettered) == (2, 0, 0)
    assert bus.acked == ["1-1", "1-2"]
    assert all(e.ingested_at is not None for e in store.rows.values())


@pytest.mark.anyio
async def test_invalid_records_go_to_dlq() -> None:
    store, bus = FakeStore(), FakeBus()
    bad = [
        StreamMessage("1-1", {"event_id": str(uuid7()), "source": "k8s", "raw": "{not json"}),
        message(2, source="mainframe"),
        StreamMessage("1-3", {"source": "k8s", "raw": json.dumps(POD)}),  # no event_id
        message(4, raw=POD | {"verb": "teleport"}),
        message(5, event_id="not-a-uuid"),
    ]
    result = await IngestService(store, bus).handle([*bad, message(6)])
    assert (result.stored, result.dead_lettered) == (1, 5)
    assert all(d["reason"] for d in bus.dlq)
    assert bus.acked == [f"1-{n}" for n in range(1, 7)]


@pytest.mark.anyio
async def test_nul_bytes_go_to_dlq() -> None:
    # Postgres cannot store \u0000 in JSONB/text: one such record must not block the stream forever
    bus = FakeBus()
    poisoned = POD | {"userAgent": "curl\u0000"}
    result = await IngestService(FakeStore(), bus).handle([message(1, raw=poisoned)])
    assert result.dead_lettered == 1 and "NUL" in bus.dlq[0]["reason"]


@pytest.mark.anyio
async def test_store_failure_leaves_messages_pending() -> None:
    bus = FakeBus()
    with pytest.raises(ConnectionError):
        await IngestService(FakeStore(fail=True), bus).handle(
            [message(1), message(2, source="bad")]
        )
    assert bus.acked == [] and bus.dlq == []


@pytest.mark.anyio
async def test_redelivered_message_is_stored_once() -> None:
    store, bus = FakeStore(), FakeBus()
    service = IngestService(store, bus)
    msg = message(1)
    first, second = await service.handle([msg]), await service.handle([msg])
    assert (first.stored, second.stored, second.duplicates) == (1, 0, 1)
    assert len(store.rows) == 1


@pytest.mark.anyio
@pytest.mark.parametrize(
    "raw_text",
    [
        pytest.param("[" * 5000, id="deep-nesting-recursion"),
        pytest.param(json.dumps(POD | {"userAgent": "\ud800"}), id="lone-surrogate"),
        pytest.param(json.dumps(POD | {"latency": float("nan")}), id="nan"),
        pytest.param(json.dumps(POD | {"latency": float("inf")}), id="infinity"),
    ],
)
async def test_unstorable_records_go_to_dlq_without_blocking_the_batch(raw_text: str) -> None:
    store, bus = FakeStore(), FakeBus()
    poison = StreamMessage("1-1", {"event_id": str(uuid7()), "source": "k8s", "raw": raw_text})
    result = await IngestService(store, bus).handle([poison, message(2)])
    assert (result.stored, result.dead_lettered) == (1, 1)
    assert bus.acked == ["1-1", "1-2"]


class RejectingStore(FakeStore):
    """Accepts everything except one event, like a row Postgres refuses permanently."""

    def __init__(self, bad: UUID) -> None:
        super().__init__()
        self.bad = bad

    async def add_many(self, events: Sequence[Event]) -> int:
        if any(e.event_id == self.bad for e in events):
            raise ValueError("invalid input for type jsonb")
        return await super().add_many(events)


@pytest.mark.anyio
async def test_a_row_the_store_rejects_is_isolated_and_dead_lettered() -> None:
    poison = message(1)
    store, bus = RejectingStore(UUID(poison.fields["event_id"])), FakeBus()
    result = await IngestService(store, bus).handle([poison, message(2), message(3)])
    assert (result.stored, result.dead_lettered) == (2, 1)
    assert "jsonb" in bus.dlq[0]["reason"]
    assert bus.acked == ["1-1", "1-2", "1-3"]
