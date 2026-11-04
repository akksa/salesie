from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Channel(StrEnum):
    INSTAGRAM = "instagram"
    WHATSAPP = "whatsapp"
    FACEBOOK = "facebook"
    MESSENGER = "messenger"


class DealStage(StrEnum):
    NEW = "new"
    ENGAGED = "engaged"
    QUALIFIED = "qualified"
    PAYMENT_SENT = "payment_sent"
    WON = "won"
    LOST = "lost"


OPEN_STAGES = (DealStage.NEW, DealStage.ENGAGED, DealStage.QUALIFIED, DealStage.PAYMENT_SENT)


class ProductStatus(StrEnum):
    ACTIVE = "active"
    DRAFT = "draft"


class EngagementKind(StrEnum):
    COMMENT = "comment"
    REACTION = "reaction"


class Direction(StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class Author(StrEnum):
    CONTACT = "contact"
    AGENT = "agent"
    OWNER = "owner"


class Actor(StrEnum):
    SYSTEM = "system"
    AGENT = "agent"
    OWNER = "owner"


class AgentTrigger(StrEnum):
    COMMENT = "comment"
    DM = "dm"


class AgentRunStatus(StrEnum):
    REPLIED = "replied"
    SKIPPED = "skipped"  # nothing to answer, or the model chose not to reply
    HANDED_OFF = "handed_off"  # paused for the owner
    BLOCKED = "blocked"  # Meta's messaging windows don't allow a reply
    FAILED = "failed"


class PaymentStatus(StrEnum):
    OPEN = "open"
    PAID = "paid"
    EXPIRED = "expired"  # replaced by a newer link, or the shopper chose something else


class WebhookStatus(StrEnum):
    RECEIVED = "received"
    PROCESSED = "processed"
    FAILED = "failed"


def _enum(cls: type[StrEnum]) -> Enum:
    """Store enum values as VARCHAR with a CHECK constraint (no native PG enum to migrate)."""
    return Enum(
        cls,
        native_enum=False,
        length=20,
        values_callable=lambda members: [m.value for m in members],
        validate_strings=True,
    )


def _created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Business(Base):
    __tablename__ = "businesses"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    ig_account_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    fb_page_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    wa_phone_number_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    # Shipping, returns, payment options... the agent may quote these, and nothing it isn't told.
    sales_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()


class Product(Base):
    __tablename__ = "products"
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    price_minor: Mapped[int | None] = mapped_column(Integer)
    image_url: Mapped[str | None] = mapped_column(String(2000))
    status: Mapped[ProductStatus] = mapped_column(_enum(ProductStatus), default=ProductStatus.ACTIVE)
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (UniqueConstraint("business_id", "channel", "external_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    channel: Mapped[Channel] = mapped_column(_enum(Channel))
    external_id: Mapped[str] = mapped_column(String(128))
    caption: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(2000))
    permalink: Mapped[str | None] = mapped_column(String(2000))
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = _created_at()


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    display_name: Mapped[str | None] = mapped_column(String(200))
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = _created_at()


class ContactIdentity(Base):
    """One person can be reachable on several channels; each handle maps back to one contact."""

    __tablename__ = "contact_identities"
    __table_args__ = (UniqueConstraint("business_id", "channel", "external_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"))
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"), index=True)
    channel: Mapped[Channel] = mapped_column(_enum(Channel))
    external_id: Mapped[str] = mapped_column(String(128))
    username: Mapped[str | None] = mapped_column(String(200))
    username_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Created by the dashboard simulator: replies to it are recorded, never sent to Meta.
    simulated: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class Engagement(Base):
    __tablename__ = "engagements"
    __table_args__ = (UniqueConstraint("business_id", "channel", "external_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"))
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"), index=True)
    post_id: Mapped[int | None] = mapped_column(ForeignKey("posts.id", ondelete="SET NULL"), index=True)
    channel: Mapped[Channel] = mapped_column(_enum(Channel))
    kind: Mapped[EngagementKind] = mapped_column(_enum(EngagementKind))
    external_id: Mapped[str] = mapped_column(String(128))
    text: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Instagram allows one private reply per comment, within 7 days of it.
    private_reply_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # When Salesie stored it (our clock; occurred_at is Meta's clock and only has whole seconds).
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# Pause reasons set by the owner (anything else was the agent handing a chat over).
PAUSED_BY_OWNER = "paused by the owner"
OWNER_TOOK_OVER = "you took over this chat"


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (UniqueConstraint("business_id", "contact_id", "channel"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"))
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"), index=True)
    channel: Mapped[Channel] = mapped_column(_enum(Channel))
    agent_paused: Mapped[bool] = mapped_column(Boolean, default=False)
    paused_reason: Mapped[str | None] = mapped_column(String(500))
    # Who paused the agent: the owner (handling it), or the agent itself (handed over: needs the owner).
    paused_by: Mapped[Actor | None] = mapped_column(_enum(Actor))
    last_inbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = _created_at()


class Message(Base):
    __tablename__ = "messages"
    # Meta message ids are unique per conversation, not globally: two connected businesses
    # messaging each other would otherwise see the same mid as inbound for one and echo for the other.
    __table_args__ = (UniqueConstraint("conversation_id", "external_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    direction: Mapped[Direction] = mapped_column(_enum(Direction))
    author: Mapped[Author] = mapped_column(_enum(Author))
    text: Mapped[str | None] = mapped_column(Text)
    external_id: Mapped[str | None] = mapped_column(String(256))
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    agent_run_id: Mapped[int | None] = mapped_column(ForeignKey("agent_runs.id", ondelete="SET NULL"))


class Deal(Base):
    __tablename__ = "deals"
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012
    # At most one open deal per contact per product, and one open product-less deal per contact.
    __table_args__ = (
        Index(
            "uq_deals_one_open_per_contact_product",
            "contact_id",
            text("coalesce(product_id, 0)"),
            unique=True,
            postgresql_where=text("stage IN ('new', 'engaged', 'qualified', 'payment_sent')"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"))
    source_post_id: Mapped[int | None] = mapped_column(ForeignKey("posts.id", ondelete="SET NULL"))
    channel: Mapped[Channel] = mapped_column(_enum(Channel))
    stage: Mapped[DealStage] = mapped_column(_enum(DealStage), default=DealStage.NEW)
    amount_minor: Mapped[int | None] = mapped_column(Integer)
    # What the agent learned while qualifying, e.g. {"size": "M", "ships_to": "Pune"}.
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DealStageChange(Base):
    __tablename__ = "deal_stage_changes"

    id: Mapped[int] = mapped_column(primary_key=True)
    deal_id: Mapped[int] = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"), index=True)
    from_stage: Mapped[DealStage | None] = mapped_column(_enum(DealStage))
    to_stage: Mapped[DealStage] = mapped_column(_enum(DealStage))
    actor: Mapped[Actor] = mapped_column(_enum(Actor))
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()


class WebhookEvent(Base):
    """Every webhook delivery is stored before processing, so failures can be inspected and replayed."""

    __tablename__ = "webhook_events"
    __table_args__ = (Index("ix_webhook_events_status", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    object_type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    # A resent identical body (Meta retry or a captured replay) is stored and processed once.
    body_sha256: Mapped[str | None] = mapped_column(String(64), unique=True)
    simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[WebhookStatus] = mapped_column(_enum(WebhookStatus), default=WebhookStatus.RECEIVED)
    error: Mapped[str | None] = mapped_column(Text)
    received_at: Mapped[datetime] = _created_at()
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentRun(Base):
    """One agent turn: what triggered it, every tool call with its result, and what was sent.
    Kept so the owner (and judges) can verify why the agent did what it did."""

    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"))
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    trigger: Mapped[AgentTrigger] = mapped_column(_enum(AgentTrigger))
    status: Mapped[AgentRunStatus] = mapped_column(_enum(AgentRunStatus))
    model: Mapped[str] = mapped_column(String(100))
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    reply_text: Mapped[str | None] = mapped_column(Text)
    # Newest message the model had in front of it: later messages still need an answer.
    last_seen_message_id: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PaymentLink(Base):
    __tablename__ = "payment_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"))
    deal_id: Mapped[int] = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"))
    quantity: Mapped[int] = mapped_column(Integer)
    amount_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    token: Mapped[str] = mapped_column(String(64), unique=True)
    provider: Mapped[str] = mapped_column(String(30))
    url: Mapped[str] = mapped_column(String(2000))
    status: Mapped[PaymentStatus] = mapped_column(_enum(PaymentStatus), default=PaymentStatus.OPEN)
    created_at: Mapped[datetime] = _created_at()
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
