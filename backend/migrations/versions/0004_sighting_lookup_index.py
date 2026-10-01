"""index for per-device sighting lookups

Revision ID: 0004
Revises: 0003
"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_sightings_mac_source_ts", "sightings", ["mac", "source", "ts"])


def downgrade() -> None:
    op.drop_index("ix_sightings_mac_source_ts", table_name="sightings")
