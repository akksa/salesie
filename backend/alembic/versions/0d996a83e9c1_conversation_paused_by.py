"""conversation paused_by

Revision ID: 0d996a83e9c1
Revises: 65f5c26056cd
Create Date: 2026-10-29 19:12:25.912394

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0d996a83e9c1"
down_revision: str | Sequence[str] | None = "65f5c26056cd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("paused_by", sa.String(length=20), nullable=True))
    op.execute(
        """
        UPDATE conversations SET paused_by = CASE
            WHEN paused_reason IN ('paused by the owner', 'you took over this chat') THEN 'owner'
            ELSE 'agent' END
        WHERE agent_paused
        """
    )


def downgrade() -> None:
    op.drop_column("conversations", "paused_by")
