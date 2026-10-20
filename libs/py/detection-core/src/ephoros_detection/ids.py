"""UUIDv7 (RFC 9562): time-sortable ids. Python 3.13 has no uuid.uuid7, and the simulator needs ids
that a seeded random generator makes reproducible."""

import random
import secrets
import time
import uuid


def uuid7(ms: int | None = None, rng: random.Random | None = None) -> uuid.UUID:
    ms = time.time_ns() // 1_000_000 if ms is None else ms
    rand = rng.getrandbits(74) if rng else secrets.randbits(74)
    value = (ms & (2**48 - 1)) << 80  # 48-bit unix ms
    value |= 0x7 << 76  # version 7
    value |= (rand >> 62) << 64  # 12 random bits (rand_a)
    value |= 0b10 << 62  # RFC 4122 variant
    value |= rand & (2**62 - 1)  # 62 random bits (rand_b)
    return uuid.UUID(int=value)
