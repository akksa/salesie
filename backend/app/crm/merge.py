"""Fold two contacts that turn out to be one person into one.

Someone who messaged the Page and then commented arrives as two contacts: Facebook gives the comment a
different id, and only Meta's answer to our private reply reveals their Messenger id. Everything the
other contact has (ids, comments, deals, chats, agent runs) moves to the contact being answered, so the
pipeline shows one card and the agent sees one history.
"""

from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.crm.store import lock_contact
from app.models import (
    OPEN_STAGES,
    AgentRun,
    Contact,
    ContactIdentity,
    Conversation,
    Deal,
    DealStageChange,
    Engagement,
    Message,
    PaymentLink,
)

_RANK = {stage: rank for rank, stage in enumerate(OPEN_STAGES)}


async def absorb_contact(session: AsyncSession, *, keep_id: int, drop_id: int) -> None:
    """Move everything of contact `drop_id` to contact `keep_id` and delete it. The caller holds the lock
    of `keep_id`; ingestion only ever holds one contact lock, so taking the second can't deadlock."""
    await lock_contact(session, drop_id)
    keep = await session.get(Contact, keep_id)
    drop = await session.get(Contact, drop_id)
    if keep is None or drop is None or keep.business_id != drop.business_id or keep_id == drop_id:
        return
    await session.flush()  # the bulk statements below must see everything written so far
    await _merge_conversations(session, keep_id, drop_id)
    await _merge_deals(session, keep_id, drop_id)
    for model in (ContactIdentity, Engagement, AgentRun):
        await session.execute(update(model).where(model.contact_id == drop_id).values(contact_id=keep_id))
    keep.display_name = keep.display_name or drop.display_name
    keep.last_activity_at = _latest(keep.last_activity_at, drop.last_activity_at)
    await session.delete(drop)
    await session.flush()


async def _merge_conversations(session: AsyncSession, keep_id: int, drop_id: int) -> None:
    dropped = (await session.scalars(select(Conversation).where(Conversation.contact_id == drop_id))).all()
    for old in dropped:
        kept = await session.scalar(
            select(Conversation).where(
                Conversation.contact_id == keep_id, Conversation.channel == old.channel
            )
        )
        if kept is None:
            old.contact_id = keep_id
            continue
        # A message can be in both: our private reply here, and Meta's echo of it filed under the other one.
        ours = select(Message.external_id).where(
            Message.conversation_id == kept.id, Message.external_id.is_not(None)
        )
        await session.execute(
            delete(Message).where(Message.conversation_id == old.id, Message.external_id.in_(ours))
        )
        for model in (Message, AgentRun):
            await session.execute(
                update(model).where(model.conversation_id == old.id).values(conversation_id=kept.id)
            )
        kept.last_inbound_at = _latest(kept.last_inbound_at, old.last_inbound_at)
        kept.last_message_at = _latest(kept.last_message_at, old.last_message_at)
        if old.agent_paused and not kept.agent_paused:
            kept.agent_paused, kept.paused_by, kept.paused_reason = True, old.paused_by, old.paused_reason
        await session.delete(old)
    await session.flush()


async def _merge_deals(session: AsyncSession, keep_id: int, drop_id: int) -> None:
    """Open deals pair up like a new comment does with existing deals: same product first, then a deal
    without a product (it takes the other's product). Unpaired and closed deals just move over."""
    kept = await _open_deals(session, keep_id)
    for old in await _open_deals(session, drop_id):
        match = next((d for d in kept if d.product_id == old.product_id), None) or next(
            (d for d in kept if d.product_id is None or old.product_id is None), None
        )
        if match is None:
            continue
        _fold(match, old)
        for model in (DealStageChange, PaymentLink):
            await session.execute(update(model).where(model.deal_id == old.id).values(deal_id=match.id))
        await session.delete(old)
    await session.flush()
    await session.execute(update(Deal).where(Deal.contact_id == drop_id).values(contact_id=keep_id))


async def _open_deals(session: AsyncSession, contact_id: int) -> list[Deal]:
    rows = await session.scalars(
        select(Deal)
        .where(Deal.contact_id == contact_id, Deal.stage.in_(OPEN_STAGES))
        .order_by(Deal.id.desc())
    )
    return list(rows.all())


def _fold(into: Deal, other: Deal) -> None:
    if into.product_id is None and other.product_id is not None:
        into.product_id, into.amount_minor = other.product_id, other.amount_minor
    into.source_post_id = into.source_post_id or other.source_post_id
    into.details = {**(other.details or {}), **(into.details or {})}
    if _RANK[other.stage] > _RANK[into.stage]:
        into.stage = other.stage


def _latest(a: datetime | None, b: datetime | None) -> datetime | None:
    return max((t for t in (a, b) if t is not None), default=None)
