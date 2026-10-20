"""Ports: what services need from the outside world (adapters implement them)."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from ephoros_detection.events import Event


class EventStore(Protocol):
    async def add_many(self, events: Sequence[Event]) -> int:
        """Insert events, skipping ids already stored; returns how many rows were inserted."""
        ...

    async def page(self, *, limit: int, after: tuple[datetime, UUID] | None) -> list[Event]:
        """Events ordered by (observed_at, event_id), strictly after the given key."""
        ...


@dataclass(frozen=True)
class StreamMessage:
    id: str
    fields: dict[str, str]


class EventBus(Protocol):
    """events.raw consumed through a consumer group; unacked messages stay pending."""

    async def read(self, count: int, block_ms: int) -> list[StreamMessage]: ...

    async def claim_stale(self, min_idle_ms: int, count: int) -> list[StreamMessage]: ...

    async def ack(self, ids: Sequence[str]) -> None: ...

    async def dead_letter(self, fields: dict[str, str]) -> None: ...
