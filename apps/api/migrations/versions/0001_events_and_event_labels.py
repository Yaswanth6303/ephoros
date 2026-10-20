"""events and event labels

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "event_labels",
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("scenario", sa.Text(), nullable=False),
        sa.Column("is_malicious", sa.Boolean(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("scenario_instance_id", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("event_id"),
        schema="core",
    )
    op.create_table(
        "events",
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("principal_id", sa.Text(), nullable=False),
        sa.Column("principal_type", sa.Text(), nullable=False),
        sa.Column("session_id", sa.Text(), nullable=True),
        sa.Column("source_ip", sa.Text(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("resource_uid", sa.Text(), nullable=False),
        sa.Column("resource_kind", sa.Text(), nullable=False),
        sa.Column("resource_name", sa.Text(), nullable=True),
        sa.Column("namespace", sa.Text(), nullable=True),
        sa.Column("account", sa.Text(), nullable=True),
        sa.Column("region", sa.Text(), nullable=True),
        sa.Column("labels", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("owner_ref", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("attributes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("raw", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("event_id"),
        schema="core",
    )
    op.create_index(
        "events_keyset", "events", ["observed_at", "event_id"], unique=False, schema="core"
    )
    op.create_index(
        "events_observed_at_brin",
        "events",
        ["observed_at"],
        unique=False,
        schema="core",
        postgresql_using="brin",
    )
    op.create_index("events_principal_id", "events", ["principal_id"], unique=False, schema="core")
    op.create_index("events_resource_uid", "events", ["resource_uid"], unique=False, schema="core")


def downgrade() -> None:
    op.drop_index("events_resource_uid", table_name="events", schema="core")
    op.drop_index("events_principal_id", table_name="events", schema="core")
    op.drop_index(
        "events_observed_at_brin", table_name="events", schema="core", postgresql_using="brin"
    )
    op.drop_index("events_keyset", table_name="events", schema="core")
    op.drop_table("events", schema="core")
    op.drop_table("event_labels", schema="core")
