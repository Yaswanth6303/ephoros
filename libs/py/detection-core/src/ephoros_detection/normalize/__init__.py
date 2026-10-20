"""Source-specific mappers: raw record → normalized Event (spec §7 Normalize)."""

from collections.abc import Callable
from typing import Any
from uuid import UUID

from ephoros_detection.events import Event
from ephoros_detection.normalize import cloud, identity, k8s
from ephoros_detection.normalize.common import NormalizationError

_MAPPERS: dict[str, Callable[[UUID, dict[str, Any]], Event]] = {
    "cloud_audit": cloud.to_event,
    "k8s": k8s.to_event,
    "identity": identity.to_event,
}


def normalize(event_id: UUID, source: str, raw: Any) -> Event:
    """Map one raw record; any problem is a NormalizationError whose message is the DLQ reason."""
    mapper = _MAPPERS.get(source)
    if mapper is None:
        raise NormalizationError(f"unknown source {source!r}")
    if not isinstance(raw, dict):
        raise NormalizationError(f"{source}: record is {type(raw).__name__}, not an object")
    try:
        return mapper(event_id, raw)
    except NormalizationError:
        raise
    except (
        KeyError,
        TypeError,
        ValueError,
        IndexError,
        AttributeError,
    ) as exc:  # pydantic errors are ValueErrors
        raise NormalizationError(f"{source}: {type(exc).__name__}: {exc}") from exc


__all__ = ["NormalizationError", "normalize"]
