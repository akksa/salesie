"""harden ingestion: activity timestamps, per-conversation message ids, one open deal per product

Revision ID: e17f6a0390f7
Revises: 67b950c0d98f
Create Date: 2026-10-29 16:25:38.461781

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e17f6a0390f7"
down_revision: str | Sequence[str] | None = "67b950c0d98f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPEN_STAGES = "stage IN ('new', 'engaged', 'qualified', 'payment_sent')"


def upgrade() -> None:
    op.add_column("contacts", sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_contacts_last_activity_at", "contacts", ["last_activity_at"])
    op.add_column(
        "contact_identities", sa.Column("username_seen_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("conversations", sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_conversations_last_message_at", "conversations", ["last_message_at"])

    op.drop_constraint("messages_external_id_key", "messages", type_="unique")
    op.create_unique_constraint(
        "messages_conversation_id_external_id_key", "messages", ["conversation_id", "external_id"]
    )

    op.execute(
        """
        UPDATE conversations c SET last_message_at = m.latest
        FROM (SELECT conversation_id, max(sent_at) AS latest FROM messages GROUP BY conversation_id) m
        WHERE m.conversation_id = c.id
        """
    )
    op.execute(
        """
        UPDATE contacts c SET last_activity_at = a.latest
        FROM (
            SELECT contact_id, max(at) AS latest FROM (
                SELECT contact_id, occurred_at AS at FROM engagements
                UNION ALL
                SELECT cv.contact_id, m.sent_at FROM messages m
                JOIN conversations cv ON cv.id = m.conversation_id
            ) x GROUP BY contact_id
        ) a
        WHERE a.contact_id = c.id
        """
    )
    op.create_index(
        "uq_deals_one_open_per_contact_product",
        "deals",
        ["contact_id", sa.text("coalesce(product_id, 0)")],
        unique=True,
        postgresql_where=sa.text(OPEN_STAGES),
    )


def downgrade() -> None:
    op.drop_index("uq_deals_one_open_per_contact_product", table_name="deals")
    op.drop_constraint("messages_conversation_id_external_id_key", "messages", type_="unique")
    op.create_unique_constraint("messages_external_id_key", "messages", ["external_id"])
    op.drop_index("ix_conversations_last_message_at", table_name="conversations")
    op.drop_column("conversations", "last_message_at")
    op.drop_column("contact_identities", "username_seen_at")
    op.drop_index("ix_contacts_last_activity_at", table_name="contacts")
    op.drop_column("contacts", "last_activity_at")
