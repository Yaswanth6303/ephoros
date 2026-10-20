"""The normalized event every source is mapped into before detection (spec §5.1, OCSF-inspired)."""

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, field_validator


class Source(StrEnum):
    CLOUD_AUDIT = "cloud_audit"
    K8S = "k8s"
    IDENTITY = "identity"


class Category(StrEnum):
    API_ACTIVITY = "api_activity"
    RESOURCE_LIFECYCLE = "resource_lifecycle"
    SESSION = "session"
    RBAC = "rbac"


class Outcome(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"


class PrincipalType(StrEnum):
    USER = "user"
    SERVICE_ACCOUNT = "service_account"
    ROLE = "role"
    FEDERATED = "federated"


ACTIONS = frozenset(
    {
        "create", "delete", "update", "get", "list", "exec", "scale", "port_forward",
        "assume_role", "login", "logout", "token_issued", "mfa",
        "modify_sg", "bind_role", "run_instances", "terminate_instances", "create_access_key",
    }
)  # fmt: skip


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Actor(_Model):
    principal_id: str
    principal_type: PrincipalType
    session_id: str | None = None
    source_ip: str | None = None
    user_agent: str | None = None


class Resource(_Model):
    resource_uid: str
    kind: str
    name: str | None = None
    namespace: str | None = None
    account: str | None = None
    region: str | None = None
    labels: dict[str, str] = {}
    owner_ref: dict[str, str] | None = None


class Event(_Model):
    event_id: UUID
    source: Source
    category: Category
    action: str
    outcome: Outcome
    observed_at: AwareDatetime
    ingested_at: AwareDatetime | None = None
    actor: Actor
    resource: Resource
    attributes: dict[str, Any] = {}
    raw: dict[str, Any]

    @field_validator("action")
    @classmethod
    def _known_action(cls, action: str) -> str:
        if action not in ACTIONS:
            raise ValueError(f"unknown action {action!r}")
        return action
