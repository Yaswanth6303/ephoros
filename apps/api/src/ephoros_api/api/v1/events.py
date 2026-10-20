import base64
import binascii
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import AwareDatetime, BaseModel

from ephoros_api.api.auth import Principal, current_user
from ephoros_api.domain.ports import EventStore
from ephoros_detection.events import Actor, Category, Event, Outcome, Resource, Source

router = APIRouter(prefix="/api/v1", tags=["events"])


class EventOut(BaseModel):
    """An Event without `raw`: evidence stays server-side until incident detail."""

    event_id: UUID
    source: Source
    category: Category
    action: str
    outcome: Outcome
    observed_at: AwareDatetime
    ingested_at: AwareDatetime | None
    actor: Actor
    resource: Resource
    attributes: dict[str, Any]


class EventPage(BaseModel):
    items: list[EventOut]
    next_cursor: str | None


def get_event_store(request: Request) -> EventStore:
    store: EventStore = request.app.state.event_store
    return store


def _encode(event: Event) -> str:
    key = f"{event.observed_at.isoformat()}|{event.event_id}"
    return base64.urlsafe_b64encode(key.encode()).decode()


def _decode(cursor: str) -> tuple[datetime, UUID]:
    try:
        observed_at, event_id = base64.urlsafe_b64decode(cursor.encode()).decode().split("|")
        key = (datetime.fromisoformat(observed_at), UUID(event_id))
    except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(400, "Invalid cursor") from exc
    if key[0].tzinfo is None:
        raise HTTPException(400, "Invalid cursor")
    return key


@router.get("/events")
async def list_events(
    _user: Annotated[Principal, Depends(current_user)],
    store: Annotated[EventStore, Depends(get_event_store)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: str | None = None,
) -> EventPage:
    events = await store.page(limit=limit, after=_decode(cursor) if cursor else None)
    return EventPage(
        items=[EventOut.model_validate(e.model_dump(exclude={"raw"})) for e in events],
        next_cursor=_encode(events[-1]) if len(events) == limit else None,
    )
