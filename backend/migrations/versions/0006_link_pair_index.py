"""one link per device pair regardless of direction

Revision ID: 0006
Revises: 0005
"""
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE UNIQUE INDEX uq_links_pair ON links (LEAST(source_id, target_id), GREATEST(source_id, target_id))")


def downgrade() -> None:
    op.execute("DROP INDEX uq_links_pair")
