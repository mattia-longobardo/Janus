"""sentinel, maintenance windows and notifications

Revision ID: 0002
Revises: 0001
"""
from datetime import time

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

RULES = [
    ("device.new", True, True),
    ("device.approved", False, True),
    ("device.blocked", False, True),
    ("device.offline", False, True),
    ("ip.conflict", True, True),
    ("device.ip_mismatch", True, False),
    ("device.private_mac", False, True),
    ("infra.down", True, True),
    ("infra.up", True, True),
    ("notify.test", True, True),
]


def upgrade() -> None:
    op.alter_column("devices", "group_id", existing_type=sa.Integer(), nullable=True)
    op.add_column("devices", sa.Column("last_ip", sa.String(15), nullable=True))
    op.add_column("devices", sa.Column("dhcp_hostname", sa.String(255), nullable=True))
    op.create_table(
        "sightings",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("mac", sa.String(17), nullable=False),
        sa.Column("ip", sa.String(15), nullable=True),
        sa.Column("source", sa.String(8), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
    )
    op.create_index("ix_sightings_ts", "sightings", ["ts"])
    op.create_index("ix_sightings_mac", "sightings", ["mac"])
    windows = op.create_table(
        "maintenance_windows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("duration_min", sa.Integer(), nullable=False),
        sa.Column("days", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("mute_alerts", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("pause_isolation", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    rules = op.create_table(
        "notification_rules",
        sa.Column("event_type", sa.String(64), primary_key=True),
        sa.Column("channel", sa.String(16), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.bulk_insert(windows, [{
        "name": "Router & modem daily reboot", "start_time": time(5, 0), "duration_min": 15, "days": 127,
        "enabled": True, "mute_alerts": True, "pause_isolation": True,
    }])
    op.bulk_insert(rules, [
        {"event_type": event_type, "channel": channel, "enabled": enabled}
        for event_type, email, gotify in RULES
        for channel, enabled in (("email", email), ("gotify", gotify))
    ])


def downgrade() -> None:
    op.drop_table("notification_rules")
    op.drop_table("maintenance_windows")
    op.drop_index("ix_sightings_mac", table_name="sightings")
    op.drop_index("ix_sightings_ts", table_name="sightings")
    op.drop_table("sightings")
    op.drop_column("devices", "dhcp_hostname")
    op.drop_column("devices", "last_ip")
    op.alter_column("devices", "group_id", existing_type=sa.Integer(), nullable=False)
