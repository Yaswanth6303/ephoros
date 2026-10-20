"""ephoros-sim: generate labelled datasets and replay them onto events.raw."""

import argparse
import asyncio
import os
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from redis.asyncio import Redis

from ephoros_sim.generate import generate
from ephoros_sim.labels import write_labels
from ephoros_sim.model import SimRecord
from ephoros_sim.replay import publish, read_jsonl, write_jsonl


def _aware(value: str) -> datetime:
    start = datetime.fromisoformat(value)
    if start.tzinfo is None:
        raise argparse.ArgumentTypeError("--start needs a timezone (e.g. a trailing Z)")
    return start.astimezone(UTC)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ephoros-sim")
    commands = parser.add_subparsers(dest="command", required=True)
    gen = commands.add_parser("generate", help="generate a seeded dataset")
    gen.add_argument("--seed", type=int, default=7)
    gen.add_argument(
        "--start", type=_aware, help="ISO start with a timezone, e.g. 2026-01-05T08:00:00Z"
    )
    gen.add_argument("--hours", type=float, default=6.0)
    gen.add_argument("--out", type=Path, help="write records (with labels) as JSON lines")
    gen.add_argument(
        "--replay", action="store_true", help="write labels to DATABASE_URL, publish to REDIS_URL"
    )
    gen.add_argument(
        "--speed", type=float, default=0.0, help="0 = as fast as possible, 1 = real time"
    )
    rep = commands.add_parser("replay", help="replay a dataset written with --out")
    rep.add_argument("file", type=Path)
    rep.add_argument("--speed", type=float, default=0.0)
    return parser


async def _replay(records: Sequence[SimRecord], run_id: str, speed: float) -> None:
    await write_labels(
        os.environ["DATABASE_URL"], records, run_id
    )  # labels first: never unlabelled events
    redis = Redis.from_url(os.environ["REDIS_URL"])
    try:
        await publish(redis, records, speed)
    finally:
        await redis.aclose()


def _summary(records: Sequence[SimRecord]) -> str:
    sources = Counter(r.source for r in records)
    scenarios = Counter(r.label.scenario for r in records)
    return f"{len(records)} events · by source {dict(sources)} · by scenario {dict(scenarios)}"


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "generate":
        start = (args.start or datetime.now(UTC)).replace(microsecond=0)
        records = generate(args.seed, start, args.hours)
        run_id = f"seed{args.seed}-{start:%Y%m%dT%H%M%SZ}"
        if args.out:
            write_jsonl(args.out, records)
    else:
        records = read_jsonl(args.file)
        run_id = args.file.stem
    print(_summary(records))
    if args.command == "replay" or args.replay:
        asyncio.run(_replay(records, run_id, args.speed))
        print(f"replayed run {run_id}")
    return 0
