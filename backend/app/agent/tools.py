"""The sales agent's tools. Model output is untrusted input: every call is cleaned, validated and scoped to
the business, and prices always come from the catalog, never from the model or the shopper."""

import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.llm import ToolSpec
from app.crm import deals
from app.crm.store import lock_contact
from app.models import OPEN_STAGES, Actor, Business, Channel, Deal, DealStage, Product, ProductStatus
from app.payments.checkout import PaymentProvider, expire_open_links, format_money
from app.sanitize import clean_json

MAX_DETAILS = 20
MAX_DETAILS_CHARS = 2000
_STAGE_RANK = {DealStage.NEW: 0, DealStage.ENGAGED: 1, DealStage.QUALIFIED: 2, DealStage.PAYMENT_SENT: 3}
_WORD = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    "the a an and or for with you your have has does do did can could would will what which how much many "
    "this that these those is are was it its in on of to me my i we our any some please pls hi hello hey "
    "price cost available still want like get send yes ok okay".split()
)


@dataclass
class ToolContext:
    """Per-run state shared by the tools (mutable on purpose: it accumulates what the run did)."""

    session: AsyncSession
    business: Business
    contact_id: int
    channel: Channel
    payments: PaymentProvider
    handoff_reason: str | None = None
    payment_link_url: str | None = None
    _locked: bool = False

    async def lock(self) -> None:
        """Take the contact lock before the first write (not for the whole run: model calls are slow)."""
        if not self._locked:
            await lock_contact(self.session, self.contact_id)
            self._locked = True

    def forget_effects(self) -> None:
        """The run's writes were rolled back: nothing it created may be sent."""
        self.handoff_reason = None
        self.payment_link_url = None


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SearchCatalogArgs(_Args):
    query: str = Field(
        default="", max_length=200, description="What the shopper is looking for; empty lists all"
    )


class GetProductArgs(_Args):
    product_id: int = Field(ge=1)


class NoteDetailsArgs(_Args):
    details: dict[str, str] = Field(description='What you learned, e.g. {"size": "M", "ships_to": "Austin"}')
    product_id: int | None = Field(
        default=None, ge=1, description="Which product's deal; default: the latest"
    )

    @field_validator("details")
    @classmethod
    def bounded(cls, value: dict[str, str]) -> dict[str, str]:
        if not 1 <= len(value) <= 10:
            raise ValueError("give between 1 and 10 details")
        if any(len(k) > 40 or len(v) > 100 for k, v in value.items()):
            raise ValueError("keys must be at most 40 and values at most 100 characters")
        return value


class UpdateStageArgs(_Args):
    stage: Literal["engaged", "qualified", "lost"]
    reason: str = Field(max_length=300)
    product_id: int | None = Field(
        default=None, ge=1, description="Which product's deal; default: the latest"
    )


class PaymentLinkArgs(_Args):
    product_id: int = Field(ge=1)
    quantity: int = Field(default=1, ge=1, le=10)


class HandOffArgs(_Args):
    reason: str = Field(max_length=300)


async def _search_catalog(ctx: ToolContext, args: SearchCatalogArgs) -> dict[str, Any]:
    """Rank active products by how many of the shopper's words they contain (names count double)."""
    products = (
        await ctx.session.scalars(
            select(Product)
            .where(Product.business_id == ctx.business.id, Product.status == ProductStatus.ACTIVE)
            .order_by(Product.name)
            .limit(500)
        )
    ).all()
    words = {w for w in _WORD.findall(args.query.lower()) if len(w) > 2 and w not in _STOPWORDS}
    if words:
        scored = sorted(((_score(p, words), p) for p in products), key=lambda pair: -pair[0])
        products = [p for score, p in scored if score > 0]
    return {"products": [_product_json(p, ctx.business) for p in products[:8]]}


async def _get_product(ctx: ToolContext, args: GetProductArgs) -> dict[str, Any]:
    product = await _active_product(ctx, args.product_id)
    if product is None:
        return {"error": f"no product {args.product_id} in this shop"}
    return {"product": _product_json(product, ctx.business)}


async def _note_details(ctx: ToolContext, args: NoteDetailsArgs) -> dict[str, Any]:
    await ctx.lock()
    deal = await _target_deal(ctx, args.product_id)
    if isinstance(deal, str):
        return {"error": deal}
    merged = {**deal.details, **args.details}
    if len(merged) > MAX_DETAILS or len(json.dumps(merged)) > MAX_DETAILS_CHARS:
        return {"error": f"too many details saved (max {MAX_DETAILS} short entries); keep only what matters"}
    deal.details = merged
    return {"saved": args.details, "deal_product_id": deal.product_id}


async def _update_stage(ctx: ToolContext, args: UpdateStageArgs) -> dict[str, Any]:
    await ctx.lock()
    deal = await _target_deal(ctx, args.product_id)
    if isinstance(deal, str):
        return {"error": deal}
    target = DealStage(args.stage)
    if target != DealStage.LOST and _STAGE_RANK[target] <= _STAGE_RANK[deal.stage]:
        return {"error": f"deal is already {deal.stage.value}; stages only move forward"}
    if target == DealStage.LOST:
        await expire_open_links(ctx.session, deal.id)
    await deals.change_stage(ctx.session, deal, target, actor=Actor.AGENT, reason=args.reason)
    return {"stage": target.value, "deal_product_id": deal.product_id}


async def _create_payment_link(ctx: ToolContext, args: PaymentLinkArgs) -> dict[str, Any]:
    product = await _active_product(ctx, args.product_id)
    if product is None:
        return {"error": f"no product {args.product_id} in this shop"}
    if product.price_minor is None:
        return {"error": f"{product.name} has no price yet; hand off to the owner"}
    await ctx.lock()
    deal = await _deal_for_product(ctx, product)
    await _retire_other_checkouts(ctx, keep=deal, chosen=product)
    link = await ctx.payments.create_link(
        ctx.session, business=ctx.business, deal=deal, product=product, quantity=args.quantity
    )
    deal.amount_minor = link.amount_minor
    await deals.change_stage(
        ctx.session, deal, DealStage.PAYMENT_SENT, actor=Actor.AGENT, reason="sent a payment link"
    )
    ctx.payment_link_url = link.url
    amount = format_money(link.amount_minor, link.currency)
    return {"url": link.url, "product": product.name, "quantity": args.quantity, "total": amount}


async def _hand_off(ctx: ToolContext, args: HandOffArgs) -> dict[str, Any]:
    ctx.handoff_reason = args.reason
    return {
        "ok": True,
        "note": "The owner will take over. Tell the shopper briefly that a person will reply.",
    }


@dataclass(frozen=True)
class Tool:
    spec: ToolSpec
    args_model: type[_Args]
    run: Callable[[ToolContext, Any], Awaitable[dict[str, Any]]]


def _tool(name: str, description: str, args_model: type[_Args], run: Callable[..., Any]) -> Tool:
    return Tool(ToolSpec(name, description, args_model.model_json_schema()), args_model, run)


TOOLS = {
    tool.spec.name: tool
    for tool in [
        _tool("search_catalog", "Find products in this shop's catalog.", SearchCatalogArgs, _search_catalog),
        _tool(
            "get_product",
            "Get one product's price, attributes and description.",
            GetProductArgs,
            _get_product,
        ),
        _tool(
            "note_customer_details",
            "Save what you learned about the shopper's needs (size, colour, quantity, location...). "
            "Pass product_id when they have several open deals.",
            NoteDetailsArgs,
            _note_details,
        ),
        _tool(
            "update_deal_stage",
            "Mark a deal engaged, qualified (you know what they want) or lost (they declined). "
            "Pass product_id when they have several open deals.",
            UpdateStageArgs,
            _update_stage,
        ),
        _tool(
            "create_payment_link",
            "Create a checkout link for a product when the shopper wants to buy. Returns the URL to send. "
            "Any earlier unpaid link for this shopper stops working.",
            PaymentLinkArgs,
            _create_payment_link,
        ),
        _tool(
            "hand_off_to_owner",
            "Pause yourself and alert the owner: complaints, refunds, requests for a human, or questions "
            "the catalog and shop notes can't answer.",
            HandOffArgs,
            _hand_off,
        ),
    ]
}
TOOL_SPECS = [tool.spec for tool in TOOLS.values()]


async def run_tool(ctx: ToolContext, name: str, arguments: object) -> dict[str, Any]:
    tool = TOOLS.get(name)
    if tool is None:
        return {"error": f"unknown tool {name!r}; available: {sorted(TOOLS)}"}
    if not isinstance(arguments, dict):
        return {"error": "arguments must be a JSON object"}
    try:
        args = tool.args_model.model_validate(clean_json(arguments))
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(map(str, e['loc'])) or 'arguments'}: {e['msg']}" for e in exc.errors()
        )
        return {"error": f"invalid arguments: {problems}"}
    return await tool.run(ctx, args)


# --- helpers ------------------------------------------------------------------------------


async def _active_product(ctx: ToolContext, product_id: int) -> Product | None:
    if product_id > 2_147_483_647:
        return None
    product = await ctx.session.get(Product, product_id)
    if product is None or product.business_id != ctx.business.id or product.status != ProductStatus.ACTIVE:
        return None
    return product


async def _open_deals(ctx: ToolContext) -> list[Deal]:
    return list(
        (
            await ctx.session.scalars(
                select(Deal)
                .where(Deal.contact_id == ctx.contact_id, Deal.stage.in_(OPEN_STAGES))
                .order_by(Deal.updated_at.desc(), Deal.id.desc())
            )
        ).all()
    )


async def _target_deal(ctx: ToolContext, product_id: int | None) -> Deal | str:
    """The deal a details/stage call is about, or an error message for the model."""
    open_deals = await _open_deals(ctx)
    if not open_deals:
        return "this shopper has no open deal; create_payment_link opens one when they want to buy"
    if product_id is None:
        return open_deals[0]
    match = next((d for d in open_deals if d.product_id == product_id), None)
    return match or f"no open deal for product {product_id}; open deals are for products " + str(
        [d.product_id for d in open_deals]
    )


async def _deal_for_product(ctx: ToolContext, product: Product) -> Deal:
    """The open deal for this product, else a product-less one (which gets the product), else a new one."""
    open_deals = await _open_deals(ctx)
    match = next((d for d in open_deals if d.product_id == product.id), None) or next(
        (d for d in open_deals if d.product_id is None), None
    )
    if match is not None:
        match.product_id = product.id
        return match
    return await deals.open_deal(
        ctx.session,
        business_id=ctx.business.id,
        contact_id=ctx.contact_id,
        channel=ctx.channel,
        stage=DealStage.ENGAGED,
        reason=f"shopper chose {product.name}",
        product=product,
    )


async def _retire_other_checkouts(ctx: ToolContext, *, keep: Deal, chosen: Product) -> None:
    """One live checkout per shopper: a deal that already had a link for something else is closed."""
    for deal in await _open_deals(ctx):
        if deal.id != keep.id and deal.stage == DealStage.PAYMENT_SENT:
            await expire_open_links(ctx.session, deal.id)
            await deals.change_stage(
                ctx.session, deal, DealStage.LOST, actor=Actor.AGENT, reason=f"chose {chosen.name} instead"
            )


def _score(product: Product, words: set[str]) -> int:
    name = set(_WORD.findall(product.name.lower()))
    rest = set(_WORD.findall(f"{product.description or ''} {product.attributes}".lower()))
    return sum(
        2 if w in name or any(n.startswith(w) or w.startswith(n) for n in name) else 0 for w in words
    ) + sum(1 for w in words if w in rest)


def _product_json(product: Product, business: Business) -> dict[str, Any]:
    price = format_money(product.price_minor, business.currency) if product.price_minor is not None else None
    return {
        "id": product.id,
        "name": product.name,
        "price": price,
        "description": product.description,
        "attributes": product.attributes,
    }
