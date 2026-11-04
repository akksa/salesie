"""Deal lifecycle. Every stage change is written to deal_stage_changes so the dashboard can show why.

Invariant (also enforced by a partial unique index): a contact has at most one open deal per product and
at most one open deal without a product. Callers must hold the contact lock (store.lock_contact).
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    OPEN_STAGES,
    Actor,
    Channel,
    Deal,
    DealStage,
    DealStageChange,
    Post,
    Product,
    ProductStatus,
)

# After a deal closes, a "thanks!" DM shouldn't open a new one. The agent (Phase 2) opens deals on intent.
CLOSED_DEAL_COOLDOWN = timedelta(days=14)


async def latest_open_deal(session: AsyncSession, contact_id: int) -> Deal | None:
    return await session.scalar(
        select(Deal)
        .where(Deal.contact_id == contact_id, Deal.stage.in_(OPEN_STAGES))
        .order_by(Deal.updated_at.desc(), Deal.id.desc())
        .limit(1)
    )


async def deal_for_comment(
    session: AsyncSession, *, business_id: int, contact_id: int, channel: Channel, post: Post
) -> Deal:
    """Reuse the open deal this comment belongs to, or open one. Preference: same product, then same
    post, then a deal that has no product yet (e.g. opened by a DM), which gets this post's product."""
    open_deals = list(
        await session.scalars(
            select(Deal)
            .where(Deal.contact_id == contact_id, Deal.stage.in_(OPEN_STAGES))
            .order_by(Deal.id.desc())
        )
    )
    product = await session.get(Product, post.product_id) if post.product_id is not None else None
    if product is not None and product.status != ProductStatus.ACTIVE:
        product = None  # a draft (unreleased) product is never revealed or sold
    match = (
        next((d for d in open_deals if product and d.product_id == product.id), None)
        or next((d for d in open_deals if d.source_post_id == post.id), None)
        or next((d for d in open_deals if d.product_id is None), None)
    )
    if match is None:
        return await open_deal(
            session,
            business_id=business_id,
            contact_id=contact_id,
            channel=channel,
            stage=DealStage.NEW,
            reason=f'commented on "{_snippet(post.caption)}"' if post.caption else "commented on a post",
            post=post,
            product=product,
        )
    if match.product_id is None and product is not None:
        match.product_id = product.id
        match.amount_minor = product.price_minor
    if match.source_post_id is None:
        match.source_post_id = post.id
    return match


async def recently_closed(session: AsyncSession, contact_id: int) -> bool:
    since = datetime.now(UTC) - CLOSED_DEAL_COOLDOWN
    closed = await session.scalar(
        select(Deal.id)
        .where(
            Deal.contact_id == contact_id,
            Deal.stage.in_((DealStage.WON, DealStage.LOST)),
            Deal.updated_at >= since,
        )
        .limit(1)
    )
    return closed is not None


async def open_deal(
    session: AsyncSession,
    *,
    business_id: int,
    contact_id: int,
    channel: Channel,
    stage: DealStage,
    reason: str,
    post: Post | None = None,
    product: Product | None = None,
) -> Deal:
    deal = Deal(
        business_id=business_id,
        contact_id=contact_id,
        product_id=product.id if product else None,
        source_post_id=post.id if post else None,
        channel=channel,
        stage=stage,
        amount_minor=product.price_minor if product else None,
    )
    session.add(deal)
    await session.flush()
    session.add(
        DealStageChange(deal_id=deal.id, from_stage=None, to_stage=stage, actor=Actor.SYSTEM, reason=reason)
    )
    return deal


async def change_stage(
    session: AsyncSession, deal: Deal, to_stage: DealStage, *, actor: Actor, reason: str | None
) -> None:
    if deal.stage == to_stage:
        return
    session.add(
        DealStageChange(deal_id=deal.id, from_stage=deal.stage, to_stage=to_stage, actor=actor, reason=reason)
    )
    deal.stage = to_stage
    await session.flush()


def _snippet(text: str, limit: int = 40) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"
