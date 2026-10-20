from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

Severity = Literal["none", "low", "medium", "high", "critical"]
Source = Literal["cloud_audit", "k8s", "identity"]


@dataclass(frozen=True)
class Label:
    """Ground truth for one event; written to core.event_labels, never onto the stream."""

    scenario: str
    is_malicious: bool
    severity: Severity
    scenario_instance_id: str


@dataclass(frozen=True)
class SimRecord:
    event_id: UUID
    source: Source
    raw: dict[str, Any]
    observed_at: datetime
    label: Label
