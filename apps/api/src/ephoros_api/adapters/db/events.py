from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Row, literal, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine

from ephoros_api.adapters.db.tables import events as t
from ephoros_detection.events import Event


def _row(e: Event) -> dict[str, Any]:
    a, r = e.actor, e.resource
    return {
        "event_id": e.event_id,
        "source": e.source.value,
        "category": e.category.value,
        "action": e.action,
        "outcome": e.outcome.value,
        "observed_at": e.observed_at,
        "ingested_at": e.ingested_at,
        "principal_id": a.principal_id,
        "principal_type": a.principal_type.value,
        "session_id": a.session_id,
        "source_ip": a.source_ip,
        "user_agent": a.user_agent,
        "resource_uid": r.resource_uid,
        "resource_kind": r.kind,
        "resource_name": r.name,
        "namespace": r.namespace,
        "account": r.account,
        "region": r.region,
        "labels": r.labels,
        "owner_ref": r.owner_ref,
        "attributes": e.attributes,
        "raw": e.raw,
    }


def _event(row: Row[Any]) -> Event:
    m = row._mapping
    return Event.model_validate(
        {
            "event_id": m["event_id"],
            "source": m["source"],
            "category": m["category"],
            "action": m["action"],
            "outcome": m["outcome"],
            "observed_at": m["observed_at"],
            "ingested_at": m["ingested_at"],
            "actor": {
                k: m[k]
                for k in ("principal_id", "principal_type", "session_id", "source_ip", "user_agent")
            },
            "resource": {
                "resource_uid": m["resource_uid"],
                "kind": m["resource_kind"],
                "name": m["resource_name"],
                "namespace": m["namespace"],
                "account": m["account"],
                "region": m["region"],
                "labels": m["labels"],
                "owner_ref": m["owner_ref"],
            },
            "attributes": m["attributes"],
            "raw": m["raw"],
        }
    )


class SqlEventStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine

    async def add_many(self, events: Sequence[Event]) -> int:
        if not events:
            return 0
        stmt = (
            insert(t)
            .values([_row(e) for e in events])
            .on_conflict_do_nothing(index_elements=["event_id"])
        )
        async with self.engine.begin() as conn:
            return (await conn.execute(stmt)).rowcount

    async def page(self, *, limit: int, after: tuple[datetime, UUID] | None) -> list[Event]:
        query = select(t).order_by(t.c.observed_at, t.c.event_id).limit(limit)
        if after:
            query = query.where(
                tuple_(t.c.observed_at, t.c.event_id) > tuple_(literal(after[0]), literal(after[1]))
            )
        async with self.engine.connect() as conn:
            return [_event(row) for row in await conn.execute(query)]
