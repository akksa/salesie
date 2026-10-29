"""engagement received_at

Revision ID: 3f2faa8c48bd
Revises: a7b53a08e8c3
Create Date: 2026-10-29 18:23:55.030448

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3f2faa8c48bd"
down_revision: str | Sequence[str] | None = "a7b53a08e8c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "engagements",
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("engagements", "received_at")
