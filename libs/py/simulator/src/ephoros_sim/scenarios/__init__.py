import random
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from ephoros_sim.model import Severity, Source
from ephoros_sim.world import World

MAX_DURATION_S = 3600  # every instance finishes within an hour of its start


@dataclass
class Instance:
    scenario: str
    is_malicious: bool
    severity: Severity
    records: list[tuple[datetime, Source, dict[str, Any]]] = field(default_factory=list)


class Clock:
    """Advances a scenario's timeline in seconds from t0 (millisecond precision)."""

    def __init__(self, t0: datetime) -> None:
        self.t0, self.s = t0, 0.0

    def after(self, rng: random.Random, lo: float, hi: float) -> datetime:
        self.s += rng.uniform(lo, hi)
        return self.at(self.s)

    def at(self, seconds: float) -> datetime:
        assert seconds < MAX_DURATION_S, "scenario longer than MAX_DURATION_S"
        ts = self.t0 + timedelta(seconds=seconds)
        return ts.replace(microsecond=ts.microsecond // 1000 * 1000)


# (world, rng, t0, ordinal of this scenario in the run); ordinals guarantee every variant appears
Scenario = Callable[[World, random.Random, datetime, int], Instance]
