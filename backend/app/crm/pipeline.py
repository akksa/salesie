"""The owner's pipeline board and deal detail, and moving deals by hand."""

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncSession

from app.crm import deals
from app.crm.queries import contact_names, deal_out
from app.crm.store import lock_contact
from app.models import (
    Actor,
    Business,
    Contact,
    Conversation,
    Deal,
    DealStage,
    DealStageChange,
    Message,
    PaymentLink,
    PaymentStatus,
    Post,
    Product,
)
from app.payments.checkout import expire_open_links
from app.schemas import (
    DealDetail,
    PaymentLinkOut,
    PipelineCard,
    PipelineColumn,
    PipelineOut,
    PostBrief,
    StageChangeOut,
)

CARDS_PER_COLUMN = 100  # counts and totals always cover every deal; only the cards shown are capped


class DealMoveRefusedError(Exception):
    """The move would contradict what really happened (e.g. un-winning a deal the shopper paid for)."""


async def pipeline(session: AsyncSession, business: Business) -> PipelineOut:
    totals = {
        stage: (count, amount or 0)
        for stage, count, amount in await session.execute(
            select(Deal.stage, func.count(Deal.id), func.coalesce(func.sum(Deal.amount_minor), 0))
            .where(Deal.business_id == business.id)
            .group_by(Deal.stage)
        )
    }
    ranked = (
        select(
            Deal.id,
            func.row_number()
            .over(partition_by=Deal.stage, order_by=(Deal.updated_at.desc(), Deal.id.desc()))
            .label("position"),
        )
        .where(Deal.business_id == business.id)
        .subquery()
    )
    shown = (
        await session.scalars(
            select(Deal)
            .join(ranked, ranked.c.id == Deal.id)
            .where(ranked.c.position <= CARDS_PER_COLUMN)
            .order_by(Deal.updated_at.desc(), Deal.id.desc())
        )
    ).all()
    cards = await _cards(session, shown)
    columns = [
        PipelineColumn(
            stage=stage,
            count=totals.get(stage, (0, 0))[0],
            amount_minor=totals.get(stage, (0, 0))[1],
            deals=[c for c in cards if c.stage == stage],
        )
        for stage in DealStage
    ]
    needs_owner = await session.scalar(
        select(func.count(Conversation.id)).where(
            Conversation.business_id == business.id,
            Conversation.agent_paused.is_(True),
            Conversation.paused_by == Actor.AGENT,
        )
    )
    return PipelineOut(currency=business.currency, columns=columns, needs_owner=needs_owner or 0)


async def deal_detail(session: AsyncSession, business: Business, deal_id: int) -> DealDetail | None:
    deal = await session.get(Deal, deal_id, populate_existing=True)
    if deal is None or deal.business_id != business.id:
        return None
    [card] = await _cards(session, [deal])
    changes = await session.scalars(
        select(DealStageChange).where(DealStageChange.deal_id == deal.id).order_by(DealStageChange.id)
    )
    links = await session.scalars(
        select(PaymentLink).where(PaymentLink.deal_id == deal.id).order_by(PaymentLink.id)
    )
    return DealDetail(
        **card.model_dump(),
        stage_changes=[StageChangeOut.model_validate(c) for c in changes],
        payment_links=[PaymentLinkOut.model_validate(link) for link in links],
    )


async def move_deal(
    session: AsyncSession, deal: Deal, stage: DealStage | None, *, amount_minor: int | None
) -> None:
    """The owner overrides the pipeline (e.g. paid in cash, or lost). Works from the deal as it is after
    taking the contact lock, never from a copy read earlier."""
    await lock_contact(session, deal.contact_id)
    fresh = await session.get(Deal, deal.id, populate_existing=True, with_for_update=True)
    if fresh is None:
        raise LookupError(f"deal {deal.id} disappeared")
    paid = await session.scalar(
        select(PaymentLink.id)
        .where(PaymentLink.deal_id == fresh.id, PaymentLink.status == PaymentStatus.PAID)
        .limit(1)
    )
    if paid is not None and stage not in (None, DealStage.WON):
        raise DealMoveRefusedError("the shopper paid for this deal through its payment link, so it stays won")
    if amount_minor is not None:
        fresh.amount_minor = amount_minor
    if stage is not None:
        if stage != DealStage.PAYMENT_SENT:
            await expire_open_links(session, fresh.id)  # out of checkout: an old link can't be paid any more
        await deals.change_stage(session, fresh, stage, actor=Actor.OWNER, reason=None)
    await session.flush()


async def _cards(session: AsyncSession, board: Sequence[Deal]) -> list[PipelineCard]:
    contact_ids = {d.contact_id for d in board}
    names = await contact_names(session, contact_ids)
    products = await _by_id(session, Product, {d.product_id for d in board if d.product_id})
    posts = await _by_id(session, Post, {d.source_post_id for d in board if d.source_post_id})
    contacts = await _by_id(session, Contact, contact_ids)
    conversations: dict[int, Conversation] = {}
    for c in await session.scalars(  # a contact's most recent conversation, on whichever channel
        select(Conversation)
        .where(Conversation.contact_id.in_(contact_ids))
        .order_by(Conversation.last_message_at.asc().nulls_first(), Conversation.id)
    ):
        conversations[c.contact_id] = c
    latest = {
        m.conversation_id: m
        for m in await session.scalars(
            select(Message)
            .where(Message.conversation_id.in_([c.id for c in conversations.values()]))
            .ext(distinct_on(Message.conversation_id))
            .order_by(Message.conversation_id, Message.id.desc())
        )
    }
    cards = []
    for deal in board:
        product = products.get(deal.product_id) if deal.product_id else None
        post = posts.get(deal.source_post_id) if deal.source_post_id else None
        conversation = conversations.get(deal.contact_id)
        message = latest.get(conversation.id) if conversation else None
        paused = bool(conversation and conversation.agent_paused)
        contact = contacts.get(deal.contact_id)
        cards.append(
            PipelineCard(
                **deal_out(deal, product.name if product else None, names[deal.contact_id]).model_dump(),
                conversation_id=conversation.id if conversation else None,
                agent_paused=paused,
                needs_owner=paused and conversation is not None and conversation.paused_by == Actor.AGENT,
                source_post=PostBrief.model_validate(post) if post else None,
                last_message=(message.text or "(attachment)")[:140] if message else None,
                last_message_author=message.author if message else None,
                last_activity_at=contact.last_activity_at if contact else None,
            )
        )
    return cards


async def _by_id[M: (Product, Post, Contact)](
    session: AsyncSession, model: type[M], ids: set[int]
) -> dict[int, M]:
    if not ids:
        return {}
    return {row.id: row for row in await session.scalars(select(model).where(model.id.in_(ids)))}
