"""Request/response shapes for the owner API. This file is the contract the frontend builds against."""

from datetime import datetime
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.models import (
    Actor,
    AgentRunStatus,
    AgentTrigger,
    Author,
    Channel,
    DealStage,
    Direction,
    EngagementKind,
    PaymentStatus,
    ProductStatus,
    WebhookStatus,
)
from app.sanitize import clean_json

INT32_MAX = 2_147_483_647


def _http_url(value: str) -> str:
    if not value.startswith(("https://", "http://")):
        raise ValueError("must be an http(s) URL")
    return value


Url = Annotated[str, StringConstraints(max_length=2000), AfterValidator(_http_url)]
DbId = Annotated[int, Field(ge=1, le=INT32_MAX)]
Money = Annotated[int, Field(ge=0, le=INT32_MAX, description="Amount in minor units, e.g. cents")]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Currency = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
InstagramUsername = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9._]{1,30}$")]


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class In(BaseModel):
    """Request bodies: strip NULs and lone surrogates, which Postgres can't store."""

    @model_validator(mode="before")
    @classmethod
    def _clean(cls, data: Any) -> Any:
        return clean_json(data)


class Patch(In):
    """PATCH bodies: omitted fields are left alone, null clears a field. Fields listed in
    `_not_nullable` back NOT NULL columns, so an explicit null for them is a validation error."""

    _not_nullable: frozenset[str] = frozenset()

    @model_validator(mode="after")
    def _reject_null_for_required(self) -> "Patch":
        nulled = sorted(
            f for f in self._not_nullable if f in self.model_fields_set and getattr(self, f) is None
        )
        if nulled:
            raise ValueError(f"cannot be null: {', '.join(nulled)}")
        return self


# --- business ---------------------------------------------------------------


class BusinessOut(Out):
    id: int
    name: str
    currency: str
    ig_account_id: str | None
    fb_page_id: str | None
    wa_phone_number_id: str | None
    sales_notes: str | None


class BusinessUpdate(Patch):
    _not_nullable = frozenset({"name", "currency"})

    name: Name | None = None
    currency: Currency | None = None
    ig_account_id: str | None = Field(default=None, max_length=64)
    fb_page_id: str | None = Field(default=None, max_length=64)
    wa_phone_number_id: str | None = Field(default=None, max_length=64)
    sales_notes: str | None = Field(
        default=None,
        max_length=4000,
        description="Shipping, returns, payment options: what the agent may quote",
    )


# --- catalog ----------------------------------------------------------------


class ProductIn(In):
    name: Name
    description: str | None = Field(default=None, max_length=5000)
    attributes: dict[str, Any] = Field(default_factory=dict)
    price_minor: Money | None = None
    image_url: Url | None = None
    status: ProductStatus = ProductStatus.ACTIVE


class ProductUpdate(Patch):
    _not_nullable = frozenset({"name", "attributes", "status"})

    name: Name | None = None
    description: str | None = Field(default=None, max_length=5000)
    attributes: dict[str, Any] | None = None
    price_minor: Money | None = None
    image_url: Url | None = None
    status: ProductStatus | None = None


class ProductOut(Out):
    id: int
    name: str
    description: str | None
    attributes: dict[str, Any]
    price_minor: int | None
    image_url: str | None
    status: ProductStatus
    created_at: datetime


class PostIn(In):
    channel: Channel = Channel.INSTAGRAM
    external_id: str = Field(min_length=1, max_length=128, description="Media/post id on the platform")
    caption: str | None = Field(default=None, max_length=5000)
    image_url: Url | None = None
    permalink: Url | None = None
    product_id: DbId | None = None


class PostUpdate(Patch):
    caption: str | None = Field(default=None, max_length=5000)
    image_url: Url | None = None
    permalink: Url | None = None
    product_id: DbId | None = None


class PostOut(Out):
    id: int
    channel: Channel
    external_id: str
    caption: str | None
    image_url: str | None
    permalink: str | None
    product_id: int | None
    product_name: str | None
    engagement_count: int
    created_at: datetime


# --- CRM --------------------------------------------------------------------


class IdentityOut(Out):
    channel: Channel
    external_id: str
    username: str | None


class DealOut(BaseModel):
    id: int
    contact_id: int
    contact_name: str
    stage: DealStage
    channel: Channel
    product_id: int | None
    product_name: str | None
    source_post_id: int | None
    amount_minor: int | None
    details: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class EngagementOut(Out):
    id: int
    kind: EngagementKind
    channel: Channel
    text: str | None
    post_id: int | None
    occurred_at: datetime


class ContactListItem(BaseModel):
    id: int
    display_name: str
    identities: list[IdentityOut]
    latest_deal: DealOut | None
    last_activity_at: datetime | None
    created_at: datetime


class MessageOut(Out):
    id: int
    direction: Direction
    author: Author
    text: str | None
    sent_at: datetime
    agent_run_id: int | None


class ConversationListItem(BaseModel):
    id: int
    contact_id: int
    contact_name: str
    channel: Channel
    agent_paused: bool
    paused_by: Actor | None  # "owner": you're handling it; "agent": it handed the chat to you
    paused_reason: str | None
    last_inbound_at: datetime | None
    last_message: MessageOut | None


class ConversationDetail(ConversationListItem):
    messages: list[MessageOut]


class ContactDetail(ContactListItem):
    engagements: list[EngagementOut]
    deals: list[DealOut]
    conversations: list[ConversationListItem]


# --- webhooks & simulator ---------------------------------------------------


class WebhookEventOut(Out):
    id: int
    object_type: str
    simulated: bool
    status: WebhookStatus
    error: str | None
    received_at: datetime
    processed_at: datetime | None


class AgentRunOut(Out):
    id: int
    contact_id: int
    conversation_id: int | None
    trigger: AgentTrigger
    status: AgentRunStatus
    model: str
    steps: list[dict[str, Any]]
    reply_text: str | None
    error: str | None
    started_at: datetime
    finished_at: datetime


class AgentStatusOut(BaseModel):
    enabled: bool
    model: str
    is_mock: bool
    instagram_sending: str  # "live" (Send API) or "recorded" (kept in Salesie only)
    messenger_sending: str
    payments: str


class ConversationUpdate(Patch):
    _not_nullable = frozenset({"agent_paused"})

    agent_paused: bool | None = None


class SimulationResult(WebhookEventOut):
    """What a simulated delivery created, so the dashboard can link straight to it."""

    contact_id: int | None
    conversation_id: int | None
    agent_runs: list[AgentRunOut]


class SimulatedCommentIn(In):
    post_id: DbId
    username: InstagramUsername
    text: str = Field(min_length=1, max_length=2200)


class SimulatedDirectMessageIn(In):
    username: InstagramUsername
    text: str = Field(min_length=1, max_length=1000)


# --- phase 5: pipeline, deal detail, taking over a chat, insights -----------------------------------


def _fits_instagram(value: str) -> str:
    if len(value.encode("utf-8")) > 1000:
        raise ValueError(
            "too long for Instagram: at most 1000 bytes (emoji and accents count double or more)"
        )
    return value


class OwnerMessageIn(In):
    text: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1), AfterValidator(_fits_instagram)
    ]


class DealUpdate(Patch):
    """The owner moves a deal by hand (e.g. paid in cash, or lost). Any stage, in any direction."""

    _not_nullable = frozenset({"stage"})

    stage: DealStage | None = None
    amount_minor: Money | None = Field(default=None, description="Set the deal value, e.g. for a cash sale")


class StageChangeOut(Out):
    from_stage: DealStage | None
    to_stage: DealStage
    actor: Actor
    reason: str | None
    created_at: datetime


class PaymentLinkOut(Out):
    id: int
    status: PaymentStatus
    quantity: int
    amount_minor: int
    currency: str
    url: str
    created_at: datetime
    paid_at: datetime | None


class PostBrief(Out):
    id: int
    external_id: str
    caption: str | None
    image_url: str | None
    permalink: str | None


class PipelineCard(DealOut):
    conversation_id: int | None
    agent_paused: bool
    needs_owner: bool  # the agent handed this chat over (refund, complaint, a question it couldn't answer)
    source_post: PostBrief | None
    last_message: str | None
    last_message_author: Author | None
    last_activity_at: datetime | None


class PipelineColumn(BaseModel):
    stage: DealStage
    count: int
    amount_minor: int
    deals: list[PipelineCard]


class PipelineOut(BaseModel):
    currency: str
    columns: list[PipelineColumn]
    needs_owner: int  # chats the agent handed over that are waiting for the owner


class DealDetail(PipelineCard):
    stage_changes: list[StageChangeOut]
    payment_links: list[PaymentLinkOut]


class FunnelStep(BaseModel):
    stage: DealStage
    reached: int  # deals that got at least this far


class PostPerformance(BaseModel):
    post: PostBrief
    product_name: str | None
    leads: int
    deals: int
    won: int
    revenue_minor: int


class ChannelPerformance(BaseModel):
    channel: Channel
    deals: int
    won: int
    revenue_minor: int


class InsightsOut(BaseModel):
    currency: str
    days: int
    leads: int
    deals: int
    won: int
    revenue_minor: int
    conversion_rate: float | None  # won / deals opened in the period
    agent_replies: int
    median_agent_reply_seconds: float | None  # time the agent took to answer, from its run log
    handoffs: int
    funnel: list[FunnelStep]
    by_post: list[PostPerformance]
    by_channel: list[ChannelPerformance]
