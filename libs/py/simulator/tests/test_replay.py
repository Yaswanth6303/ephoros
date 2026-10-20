import json
import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from redis.asyncio import Redis

from ephoros_sim.cli import main
from ephoros_sim.generate import SCENARIOS, generate
from ephoros_sim.replay import RAW_STREAM, envelope, publish, read_jsonl

START = datetime(2026, 1, 5, 8, 0, tzinfo=UTC)


def test_envelope_has_exactly_three_fields() -> None:
    record = generate(7, START)[0]
    env = envelope(record)
    assert set(env) == {"event_id", "source", "raw"}
    assert json.loads(env["raw"]) == record.raw


@pytest.mark.anyio
async def test_stream_carries_no_labels(redis: Redis) -> None:
    await publish(redis, generate(7, START))
    forbidden = [*SCENARIOS, "is_malicious", "scenario_instance_id", "severity"]
    for _id, fields in await redis.xrange(RAW_STREAM):
        assert set(fields) == {"event_id", "source", "raw"}
        assert not any(word in fields["raw"] for word in forbidden)


@pytest.mark.anyio
async def test_publish_preserves_order_and_count(redis: Redis) -> None:
    records = generate(7, START)
    assert await publish(redis, records) == len(records)
    published = [fields["event_id"] for _id, fields in await redis.xrange(RAW_STREAM)]
    assert published == [str(r.event_id) for r in records]


@pytest.mark.anyio
async def test_speed_paces_publication(redis: Redis) -> None:
    first = generate(7, START)[0]
    records = [
        replace(first, observed_at=first.observed_at + timedelta(seconds=s)) for s in (0, 1, 2)
    ]
    started = time.monotonic()
    await publish(redis, records, speed=10)
    assert time.monotonic() - started >= 0.18  # 2 s of event time at 10x


def test_cli_writes_a_dataset_that_reads_back(tmp_path: Path) -> None:
    out = tmp_path / "run.jsonl"
    assert (
        main(["generate", "--seed", "7", "--start", "2026-01-05T08:00:00Z", "--out", str(out)]) == 0
    )
    assert read_jsonl(out) == generate(7, START)
