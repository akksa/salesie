"""agent run last seen message

Revision ID: 65f5c26056cd
Revises: 3f2faa8c48bd
Create Date: 2026-10-29 18:43:31.090653

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "65f5c26056cd"
down_revision: str | Sequence[str] | None = "3f2faa8c48bd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("agent_runs", sa.Column("last_seen_message_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("agent_runs", "last_seen_message_id")
