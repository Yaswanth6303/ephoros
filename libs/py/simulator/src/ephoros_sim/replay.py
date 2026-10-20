"""Publish datasets onto events.raw (spec §6.1). Envelopes never carry labels."""

import asyncio
import json
from collections.abc import Sequence
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from uuid import UUID

from redis.asyncio import Redis

from ephoros_sim.model import Label, SimRecord

RAW_STREAM = "events.raw"  # consumed by ephoros_api's worker; the simulator must not import the API
BATCH = 500


def envelope(record: SimRecord) -> dict[str, str]:
    return {
        "event_id": str(record.event_id),
        "source": record.source,
        "raw": json.dumps(record.raw, separators=(",", ":")),
    }


async def publish(redis: Redis, records: Sequence[SimRecord], speed: float = 0.0) -> int:
    """speed 0: as fast as possible (pipelined); speed s > 0: s× real time between events."""
    if speed <= 0:
        for start in range(0, len(records), BATCH):
            async with redis.pipeline(transaction=False) as pipe:
                for record in records[start : start + BATCH]:
                    pipe.xadd(RAW_STREAM, envelope(record))  # type: ignore[arg-type]
                await pipe.execute()
        return len(records)
    previous: datetime | None = None
    for record in records:
        if previous is not None:
            await asyncio.sleep((record.observed_at - previous).total_seconds() / speed)
        await redis.xadd(RAW_STREAM, envelope(record))  # type: ignore[arg-type]
        previous = record.observed_at
    return len(records)


def write_jsonl(path: Path, records: Sequence[SimRecord]) -> None:
    with path.open("w") as f:
        for r in records:
            row = asdict(r) | {
                "event_id": str(r.event_id),
                "observed_at": r.observed_at.isoformat(),
            }
            f.write(json.dumps(row, sort_keys=True) + "\n")


def read_jsonl(path: Path) -> list[SimRecord]:
    records = []
    for line in path.read_text().splitlines():
        row = json.loads(line)
        records.append(
            SimRecord(
                event_id=UUID(row["event_id"]),
                source=row["source"],
                raw=row["raw"],
                observed_at=datetime.fromisoformat(row["observed_at"]),
                label=Label(**row["label"]),
            )
        )
    return records
