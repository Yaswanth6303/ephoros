"""Schema `core` (spec §5.2). Actor/resource are flattened so they can be indexed."""

from sqlalchemy import Boolean, Column, DateTime, Index, MetaData, Table, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData(schema="core")

events = Table(
    "events",
    metadata,
    Column("event_id", Uuid, primary_key=True),
    Column("source", Text, nullable=False),
    Column("category", Text, nullable=False),
    Column("action", Text, nullable=False),
    Column("outcome", Text, nullable=False),
    Column("observed_at", DateTime(timezone=True), nullable=False),
    Column("ingested_at", DateTime(timezone=True)),
    Column("principal_id", Text, nullable=False),
    Column("principal_type", Text, nullable=False),
    Column("session_id", Text),
    Column("source_ip", Text),
    Column("user_agent", Text),
    Column("resource_uid", Text, nullable=False),
    Column("resource_kind", Text, nullable=False),
    Column("resource_name", Text),
    Column("namespace", Text),
    Column("account", Text),
    Column("region", Text),
    Column("labels", JSONB, nullable=False),
    Column("owner_ref", JSONB),
    Column("attributes", JSONB, nullable=False),
    Column("raw", JSONB, nullable=False),
    Index("events_observed_at_brin", "observed_at", postgresql_using="brin"),
    Index("events_principal_id", "principal_id"),
    Index("events_resource_uid", "resource_uid"),
    Index("events_keyset", "observed_at", "event_id"),
)

# simulator ground truth; read only by the evaluation harness. No FK: labels land before events.
event_labels = Table(
    "event_labels",
    metadata,
    Column("event_id", Uuid, primary_key=True),
    Column("scenario", Text, nullable=False),
    Column("is_malicious", Boolean, nullable=False),
    Column("severity", Text, nullable=False),
    Column("scenario_instance_id", Text, nullable=False),
    Column("run_id", Text, nullable=False),
)
