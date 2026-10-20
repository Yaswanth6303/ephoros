import random

from ephoros_detection.ids import uuid7


def test_uuid7_is_version_7_and_time_ordered() -> None:
    ids = [uuid7(ms) for ms in (3, 1, 2)]
    assert all(i.version == 7 for i in ids)
    assert [i.int >> 80 for i in sorted(ids)] == [1, 2, 3]  # top 48 bits are the timestamp


def test_uuid7_is_reproducible_with_a_seeded_rng() -> None:
    assert uuid7(1_700_000_000_000, random.Random(7)) == uuid7(1_700_000_000_000, random.Random(7))
    assert uuid7(1_700_000_000_000, random.Random(7)) != uuid7(1_700_000_000_000, random.Random(8))
