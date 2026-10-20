"""Seeded dataset generator: same (seed, start, hours) ⇒ identical records (spec §6.1)."""

import random
from collections import Counter
from datetime import datetime, timedelta

from ephoros_detection.ids import uuid7
from ephoros_sim.model import Label, SimRecord
from ephoros_sim.scenarios import (
    MAX_DURATION_S,
    Scenario,
    crypto_mining,
    exposure,
    identity_anomaly,
    legit_burst,
    routine,
)
from ephoros_sim.world import World

SCENARIOS: dict[str, Scenario] = {
    "crypto_mining": crypto_mining.instance,
    "public_exposure": exposure.instance,
    "identity_anomaly": identity_anomaly.instance,
    "legit_burst": legit_burst.instance,
    "routine_lifecycle": routine.instance,
}
# share of scenario instances per run (challenge proportions)
MIX = {
    "crypto_mining": (0.05, 0.08),
    "public_exposure": (0.03, 0.05),
    "identity_anomaly": (0.05, 0.08),
    "legit_burst": (0.40, 0.50),
    "routine_lifecycle": (0.30, 0.40),
}
EVENTS_PER_SOURCE = {"cloud_audit": (500, 1000), "k8s": (500, 1000), "identity": (200, 500)}


def generate(seed: int, start: datetime, hours: float = 6.0) -> list[SimRecord]:
    if hours * 3600 <= MAX_DURATION_S:
        raise ValueError("hours must exceed one scenario's maximum duration (1 h)")
    rng = random.Random(seed)
    world = World.build(rng)
    records: list[SimRecord] = []
    seen: Counter[str] = Counter()
    for n, name in enumerate(_plan(rng)):
        t0 = start + timedelta(seconds=rng.uniform(0, hours * 3600 - MAX_DURATION_S))
        inst = SCENARIOS[name](world, rng, t0, seen[name])
        seen[name] += 1
        label = Label(inst.scenario, inst.is_malicious, inst.severity, f"{name}-{n:03d}")
        for ts, source, raw in inst.records:
            records.append(
                SimRecord(uuid7(int(ts.timestamp() * 1000), rng), source, raw, ts, label)
            )
    records.sort(key=lambda r: (r.observed_at, r.event_id))
    _check_volumes(records)
    return records


def _plan(rng: random.Random) -> list[str]:
    """Instance counts inside the MIX ranges, drawn deterministically and shuffled."""
    while True:
        total = rng.randint(95, 110)
        counts = {
            name: round(total * rng.uniform(lo, hi))
            for name, (lo, hi) in MIX.items()
            if name != "routine_lifecycle"
        }
        counts["routine_lifecycle"] = total - sum(counts.values())
        if all(lo <= counts[name] / total <= hi for name, (lo, hi) in MIX.items()):
            plan = [name for name, n in counts.items() for _ in range(n)]
            rng.shuffle(plan)
            return plan


def _check_volumes(records: list[SimRecord]) -> None:
    counts: Counter[str] = Counter(r.source for r in records)
    bad = {s: counts[s] for s, (lo, hi) in EVENTS_PER_SOURCE.items() if not lo <= counts[s] <= hi}
    if bad:  # never ship a dataset outside the challenge's volumes silently
        raise ValueError(f"event volumes out of range: {bad} (expected {EVENTS_PER_SOURCE})")
