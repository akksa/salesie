"""Apply parsed Meta events to the CRM. Each handler is idempotent (Meta redelivers webhooks) and runs in
its own transaction, holding the contact's advisory lock for deal and conversation logic. A handler returns
a ReplyRequest when there is something new for the sales agent to answer."""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.runner import ReplyRequest
from app.crm import deals
from app.crm.contacts import record_activity, remember_username, upsert_contact
from app.crm.store import get_or_create, lock_contact
from app.meta.events import InstagramComment, InstagramMessage, MetaEvent
from app.models import (
    Actor,
    AgentTrigger,
    Author,
    Business,
    Channel,
    Conversation,
    DealStage,
    Direction,
    Engagement,
    EngagementKind,
    Message,
    Post,
)


class UnknownAccountError(LookupError):
    """The webhook is for an account no business in Salesie is connected to."""


async def ingest_event(
    session: AsyncSession, event: MetaEvent, *, simulated: bool = False
) -> ReplyRequest | None:
    match event:
        case InstagramComment():
            return await _ingest_instagram_comment(session, event, simulated)
        case InstagramMessage():
            return await _ingest_instagram_message(session, event, simulated)


async def _business_for_instagram(session: AsyncSession, account_id: str) -> Business:
    business = await session.scalar(select(Business).where(Business.ig_account_id == account_id))
    if business is None:
        raise UnknownAccountError(
            f"no business is connected to Instagram account {account_id} "
            "(set it as the business's Instagram account id if it is yours)"
        )
    return business


async def _ingest_instagram_comment(
    session: AsyncSession, event: InstagramComment, simulated: bool
) -> ReplyRequest | None:
    business = await _business_for_instagram(session, event.account_id)
    if event.from_id == event.account_id:
        return None  # the business replying under its own post is not a lead
    contact, identity = await upsert_contact(
        session, business.id, Channel.INSTAGRAM, event.from_id, simulated=simulated
    )
    await lock_contact(session, contact.id)
    post, _ = await get_or_create(
        session,
        Post,
        {"business_id": business.id, "channel": Channel.INSTAGRAM, "external_id": event.media_id},
    )
    inserted = await session.scalar(
        insert(Engagement)
        .values(
            business_id=business.id,
            contact_id=contact.id,
            post_id=post.id,
            channel=Channel.INSTAGRAM,
            kind=EngagementKind.COMMENT,
            external_id=event.comment_id,
            text=event.text,
            occurred_at=event.occurred_at,
        )
        .on_conflict_do_nothing(index_elements=["business_id", "channel", "external_id"])
        .returning(Engagement.id)
    )
    if inserted is None:
        return None  # duplicate delivery
    remember_username(identity, event.from_username, event.occurred_at)
    record_activity(contact, event.occurred_at)
    await deals.deal_for_comment(
        session, business_id=business.id, contact_id=contact.id, channel=Channel.INSTAGRAM, post=post
    )
    return ReplyRequest(business.id, contact.id, AgentTrigger.COMMENT, engagement_id=inserted)


async def _ingest_instagram_message(
    session: AsyncSession, event: InstagramMessage, simulated: bool
) -> ReplyRequest | None:
    business = await _business_for_instagram(session, event.account_id)
    contact, _ = await upsert_contact(
        session, business.id, Channel.INSTAGRAM, event.contact_external_id, simulated=simulated
    )
    await lock_contact(session, contact.id)
    conversation, _ = await get_or_create(
        session,
        Conversation,
        {"business_id": business.id, "contact_id": contact.id, "channel": Channel.INSTAGRAM},
    )
    inserted = await session.scalar(
        insert(Message)
        .values(
            conversation_id=conversation.id,
            direction=Direction.OUTBOUND if event.is_echo else Direction.INBOUND,
            author=Author.OWNER if event.is_echo else Author.CONTACT,
            text=event.text,
            external_id=event.message_id,
            sent_at=event.occurred_at,
        )
        .on_conflict_do_nothing(index_elements=["conversation_id", "external_id"])
        .returning(Message.id)
    )
    if inserted is None:
        return None  # duplicate delivery
    record_activity(contact, event.occurred_at)
    if conversation.last_message_at is None or event.occurred_at > conversation.last_message_at:
        conversation.last_message_at = event.occurred_at
    if event.is_echo:
        return None  # the business's own message: no lead progress
    if conversation.last_inbound_at is None or event.occurred_at > conversation.last_inbound_at:
        conversation.last_inbound_at = event.occurred_at
    await _progress_deal_on_inbound_message(session, business.id, contact.id)
    if event.standby:
        return None  # another app owns this thread (handover protocol): don't answer
    return ReplyRequest(business.id, contact.id, AgentTrigger.DM)


async def _progress_deal_on_inbound_message(session: AsyncSession, business_id: int, contact_id: int) -> None:
    deal = await deals.latest_open_deal(session, contact_id)
    if deal is not None:
        if deal.stage == DealStage.NEW:
            await deals.change_stage(
                session, deal, DealStage.ENGAGED, actor=Actor.SYSTEM, reason="the shopper replied in DMs"
            )
        return
    if await deals.recently_closed(session, contact_id):
        return
    await deals.open_deal(
        session,
        business_id=business_id,
        contact_id=contact_id,
        channel=Channel.INSTAGRAM,
        stage=DealStage.ENGAGED,
        reason="the shopper sent a DM",
    )
