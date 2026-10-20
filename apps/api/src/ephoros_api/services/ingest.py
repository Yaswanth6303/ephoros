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


def _check_storable(record: object) -> None:
    """Reject what Postgres would refuse forever (it would stall the batch): NaN/Infinity in JSONB,
    lone UTF-16 surrogates, NUL characters."""
    text = json.dumps(record, allow_nan=False, ensure_ascii=False)
    text.encode("utf-8")
    if "\\u0000" in text:  # json.dumps always escapes control characters
        raise NormalizationError("record contains NUL characters")


def _parse(fields: dict[str, str]) -> Event:
    try:
        event_id, source = UUID(fields["event_id"]), fields["source"]
        record = json.loads(fields["raw"])
        _check_storable(record)
        return normalize(event_id, source, record)
    except NormalizationError:
        raise
    except Exception as exc:  # e.g. RecursionError on deeply nested JSON: still just a bad record
        raise NormalizationError(f"{type(exc).__name__}: {exc}"[:500]) from exc


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
        stored, refused = await self._store(valid)
        rejected += refused
        for fields in rejected:
            await self.bus.dead_letter(fields)
        await self.bus.ack([m.id for m in messages])
        return IngestResult(stored, len(valid) - stored - len(refused), len(rejected))

    async def _store(self, events: list[Event]) -> tuple[int, list[dict[str, str]]]:
        """Store a batch; if it fails, retry row by row so one bad row cannot block the rest.
        Every row failing means the database is the problem: re-raise and keep the batch pending."""
        try:
            return await self.store.add_many(events), []
        except Exception:
            if len(events) <= 1:
                # shortcut: a lone permanently-bad row retries forever;
                # cap redeliveries via the XPENDING delivery count if this is ever seen
                raise
        stored, refused, last_error = 0, [], None
        for event in events:
            try:
                stored += await self.store.add_many([event])
            except Exception as exc:
                last_error = exc
                reason = f"store rejected: {type(exc).__name__}: {exc}"[:500]
                refused.append(
                    {
                        "event_id": str(event.event_id),
                        "source": event.source.value,
                        "raw": json.dumps(event.raw),
                        "reason": reason,
                    }
                )
        if last_error is not None and len(refused) == len(events):
            raise last_error
        return stored, refused

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
