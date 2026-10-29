"""Request/response shapes for the owner API. This file is the contract the frontend builds against."""

from datetime import datetime
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.models import (
    AgentRunStatus,
    AgentTrigger,
    Author,
    Channel,
    DealStage,
    Direction,
    EngagementKind,
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
