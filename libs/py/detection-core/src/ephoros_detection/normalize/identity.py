"""Identity-provider session events (spec §6.1)."""

from typing import Any
from uuid import UUID

from ephoros_detection.events import Event
from ephoros_detection.normalize.common import timestamp


def to_event(event_id: UUID, raw: dict[str, Any]) -> Event:
    return Event.model_validate(
        {
            "event_id": event_id,
            "source": "identity",
            "category": "session",
            "action": raw["event_type"],
            "outcome": raw["outcome"],
            "observed_at": timestamp(raw["timestamp"]),
            "actor": {
                "principal_id": raw["principal"],
                "principal_type": raw["principal_type"],
                "session_id": raw["session_id"],
                "source_ip": raw.get("ip"),
                "user_agent": raw.get("user_agent"),
            },
            "resource": {"resource_uid": raw["session_id"], "kind": "Session"},
            "attributes": {"geo": raw.get("geo"), "federated_from": raw.get("federated_from")},
            "raw": raw,
        }
    )
