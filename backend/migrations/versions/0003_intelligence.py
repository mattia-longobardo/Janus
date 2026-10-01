"""device facts, services and scan settings

Revision ID: 0003
Revises: 0002
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("groups", sa.Column("scan_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("groups", sa.Column("scan_interval_hours", sa.Integer(), nullable=False, server_default="168"))
    op.add_column("devices", sa.Column("last_scan_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("devices", sa.Column("scan_requested_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "device_facts",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("mac", sa.String(17), nullable=False),
        sa.Column("field", sa.String(32), nullable=False),
        sa.Column("value", sa.String(255), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("mac", "field", "source", name="uq_device_facts_mac_field_source"),
    )
    op.create_index("ix_device_facts_mac", "device_facts", ["mac"])
    op.create_table(
        "services",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("mac", sa.String(17), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("proto", sa.String(4), nullable=False),
        sa.Column("state", sa.String(8), nullable=False),
        sa.Column("service", sa.String(64), nullable=True),
        sa.Column("version", sa.String(255), nullable=True),
        sa.Column("risk", sa.String(16), nullable=False),
        sa.Column("risk_reason", sa.String(128), nullable=True),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("mac", "port", "proto", name="uq_services_mac_port_proto"),
    )
    op.create_index("ix_services_mac", "services", ["mac"])
    rules = sa.table("notification_rules", sa.column("event_type", sa.String), sa.column("channel", sa.String),
                     sa.column("enabled", sa.Boolean))
    op.bulk_insert(rules, [
        {"event_type": "security.new_port", "channel": "email", "enabled": False},
        {"event_type": "security.new_port", "channel": "gotify", "enabled": True},
        {"event_type": "security.risky_service", "channel": "email", "enabled": True},
        {"event_type": "security.risky_service", "channel": "gotify", "enabled": True},
    ])


def downgrade() -> None:
    op.execute("DELETE FROM notification_rules WHERE event_type LIKE 'security.%'")
    op.drop_index("ix_services_mac", table_name="services")
    op.drop_table("services")
    op.drop_index("ix_device_facts_mac", table_name="device_facts")
    op.drop_table("device_facts")
    op.drop_column("devices", "scan_requested_at")
    op.drop_column("devices", "last_scan_at")
    op.drop_column("groups", "scan_interval_hours")
    op.drop_column("groups", "scan_enabled")
