"""Ground truth goes straight to core.event_labels (spec §5.2), never onto the event stream."""

from collections.abc import Sequence

import asyncpg

from ephoros_sim.model import SimRecord

_INSERT = """
INSERT INTO core.event_labels
    (event_id, scenario, is_malicious, severity, scenario_instance_id, run_id)
VALUES ($1, $2, $3, $4, $5, $6)
ON CONFLICT (event_id) DO NOTHING
"""


async def write_labels(dsn: str, records: Sequence[SimRecord], run_id: str) -> int:
    rows = [
        (
            r.event_id,
            r.label.scenario,
            r.label.is_malicious,
            r.label.severity,
            r.label.scenario_instance_id,
            run_id,
        )
        for r in records
    ]
    conn = await asyncpg.connect(dsn)
    try:
        await conn.executemany(_INSERT, rows)
    finally:
        await conn.close()
    return len(rows)
