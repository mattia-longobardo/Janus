"""initial schema

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

access = postgresql.ENUM("authorized", "lan_only", "pending", "blocked", name="access", create_type=False)


def upgrade() -> None:
    access.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False, unique=True),
        sa.Column("color", sa.String(9), nullable=False),
        sa.Column("icon", sa.String(32), nullable=False),
        sa.Column("range_start", sa.String(15), nullable=False),
        sa.Column("range_end", sa.String(15), nullable=False),
        sa.Column("default_access", access, nullable=False),
        sa.Column("offline_alert_hours", sa.Integer(), nullable=True),
    )
    op.create_table(
        "devices",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("mac", sa.String(17), nullable=True, unique=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("hostname", sa.String(63), nullable=False, unique=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id"), nullable=False),
        sa.Column("static_ip", sa.String(15), nullable=True, unique=True),
        sa.Column("access", access, nullable=False),
        sa.Column("vendor", sa.String(128), nullable=True),
        sa.Column("private_mac", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("online", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("mac", sa.String(17), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
    )
    op.create_index("ix_events_type", "events", ["type"])
    op.create_index("ix_events_mac", "events", ["mac"])
    op.create_table(
        "settings",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("value", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("settings")
    op.drop_index("ix_events_mac", table_name="events")
    op.drop_index("ix_events_type", table_name="events")
    op.drop_table("events")
    op.drop_table("devices")
    op.drop_table("groups")
    access.drop(op.get_bind(), checkfirst=True)
