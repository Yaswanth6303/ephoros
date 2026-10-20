"""events.raw → normalize → core.events, with a dead-letter stream (spec §7 Normalize, §16)."""

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from ephoros_api.domain.ports import EventBus, EventStore, StreamMessage
from ephoros_detection.events import Event
from ephoros_detection.normalize import NormalizationError, normalize

log = logging.getLogger(__name__)
RECLAIM_IDLE_MS = 60_000


@dataclass
class IngestResult:
    stored: int = 0
    duplicates: int = 0
    dead_lettered: int = 0


def _parse(fields: dict[str, str]) -> Event:
    try:
        event_id, source, raw = UUID(fields["event_id"]), fields["source"], fields["raw"]
    except (KeyError, ValueError) as exc:
        raise NormalizationError(f"bad envelope: {type(exc).__name__}: {exc}") from exc
    if (
        "\\u0000" in raw
    ):  # Postgres rejects NUL in text/JSONB; storing it would fail the batch forever
        raise NormalizationError("record contains NUL characters")
    try:
        record = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise NormalizationError(f"raw is not JSON: {exc}") from exc
    return normalize(event_id, source, record)


class IngestService:
    def __init__(
        self,
        store: EventStore,
        bus: EventBus,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.store, self.bus, self.now = store, bus, now

    async def handle(self, messages: list[StreamMessage]) -> IngestResult:
        valid: list[Event] = []
        rejected: list[dict[str, str]] = []
        for m in messages:
            try:
                valid.append(_parse(m.fields).model_copy(update={"ingested_at": self.now()}))
            except NormalizationError as exc:
                rejected.append(
                    {k: m.fields.get(k, "") for k in ("event_id", "source", "raw")}
                    | {"reason": str(exc)}
                )
        # store first: if it raises, nothing is dead-lettered or acked and the batch is retried
        stored = await self.store.add_many(valid)
        for fields in rejected:
            await self.bus.dead_letter(fields)
        await self.bus.ack([m.id for m in messages])
        return IngestResult(stored, len(valid) - stored, len(rejected))

    async def run(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            try:
                batch = await self.bus.claim_stale(RECLAIM_IDLE_MS, 100) or await self.bus.read(
                    100, 1000
                )
                if batch:
                    result = await self.handle(batch)
                    log.info("ingested batch: %s", result)
            except Exception:
                log.exception("ingest batch failed; its messages stay pending and will be retried")
                await asyncio.sleep(1)
