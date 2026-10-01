"""map positions and uplinks

Revision ID: 0005
Revises: 0004
"""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("devices", sa.Column("map_x", sa.Float(), nullable=True))
    op.add_column("devices", sa.Column("map_y", sa.Float(), nullable=True))
    op.create_table(
        "links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Uuid(), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_id", sa.Uuid(), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column("label", sa.String(64), nullable=True),
        sa.UniqueConstraint("source_id", "target_id", name="uq_links_source_target"),
    )


def downgrade() -> None:
    op.drop_table("links")
    op.drop_column("devices", "map_y")
    op.drop_column("devices", "map_x")
