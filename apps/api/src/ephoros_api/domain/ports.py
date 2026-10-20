"""Ports: what services need from the outside world (adapters implement them)."""

from collections.abc import Sequence
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
