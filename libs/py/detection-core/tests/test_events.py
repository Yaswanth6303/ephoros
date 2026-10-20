from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from ephoros_detection.events import Event
from ephoros_detection.ids import uuid7


def event(**overrides: Any) -> Event:
    fields: dict[str, Any] = {
        "event_id": uuid7(),
        "source": "k8s",
        "category": "resource_lifecycle",
        "action": "create",
        "outcome": "success",
        "observed_at": datetime(2026, 1, 5, 8, 0, tzinfo=UTC),
        "actor": {
            "principal_id": "system:serviceaccount:ci:runner",
            "principal_type": "service_account",
        },
        "resource": {"resource_uid": "pod-1", "kind": "Pod", "name": "build-1", "namespace": "ci"},
        "attributes": {"privileged": False},
        "raw": {"verb": "create"},
    } | overrides
    return Event.model_validate(fields)


def test_valid_event_round_trips() -> None:
    original = event()
    assert Event.model_validate_json(original.model_dump_json()) == original


def test_unknown_action_is_rejected() -> None:
    with pytest.raises(ValidationError):
        event(action="teleport")


def test_naive_datetime_is_rejected() -> None:
    with pytest.raises(ValidationError):
        event(observed_at=datetime(2026, 1, 5, 8, 0))


def test_unknown_source_is_rejected() -> None:
    with pytest.raises(ValidationError):
        event(source="mainframe")
