"""dedupe webhook deliveries

Revision ID: 19c46048c7b0
Revises: e17f6a0390f7
Create Date: 2026-10-29 16:45:08.601609

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "19c46048c7b0"
down_revision: str | Sequence[str] | None = "e17f6a0390f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("webhook_events", sa.Column("body_sha256", sa.String(length=64), nullable=True))
    op.create_unique_constraint("webhook_events_body_sha256_key", "webhook_events", ["body_sha256"])


def downgrade() -> None:
    op.drop_constraint("webhook_events_body_sha256_key", "webhook_events", type_="unique")
    op.drop_column("webhook_events", "body_sha256")
