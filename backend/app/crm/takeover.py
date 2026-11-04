"""The owner replies in a chat themselves. That pauses the agent on the chat until they resume it."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.runner import AgentServices
from app.channels.messaging import (
    PRIVATE_REPLY_WINDOW,
    Blocked,
    account_id_for,
    fit_message,
    inbox_channel,
    owner_route,
)
from app.crm.contacts import link_identity, record_activity
from app.crm.store import lock_contact
from app.models import (
    OWNER_TOOK_OVER,
    Actor,
    Author,
    Business,
    Channel,
    Contact,
    ContactIdentity,
    Conversation,
    Direction,
    Engagement,
    Message,
)


class TakeoverBlockedError(Exception):
    """Meta's rules don't allow a message to this person right now."""


async def send_owner_message(
    session: AsyncSession, services: AgentServices, conversation: Conversation, text: str
) -> Message:
    """Store the owner's message, pause the agent, then send. Sending is last: if Meta refuses, the
    caller's transaction rolls back and nothing claims a message was sent."""
    await lock_contact(session, conversation.contact_id)
    await session.refresh(conversation)  # read the window after the lock: a DM may have just arrived
    identities = (
        await session.scalars(
            select(ContactIdentity)
            .where(ContactIdentity.contact_id == conversation.contact_id)
            .order_by(ContactIdentity.id)
        )
    ).all()
    identity = next((i for i in identities if i.channel == conversation.channel), None)
    simulated = any(i.simulated for i in identities)
    business = await session.get(Business, conversation.business_id)
    contact = await session.get(Contact, conversation.contact_id)
    if business is None or contact is None or not identities:
        raise LookupError(f"conversation {conversation.id} has no contact identity")
    now = datetime.now(UTC)
    comment = await _open_comment(session, conversation, now)
    route = owner_route(
        now=now,
        contact_external_id=identity.external_id if identity else "",
        last_inbound_at=conversation.last_inbound_at if identity else None,
        open_comment_id=comment.external_id if comment else None,
        open_comment_at=comment.occurred_at if comment else None,
    )
    if isinstance(route, Blocked):
        raise TakeoverBlockedError(route.reason)
    message = Message(
        conversation_id=conversation.id,
        direction=Direction.OUTBOUND,
        author=Author.OWNER,
        text=fit_message(text),  # already validated to fit; this only trims surrounding whitespace
        sent_at=now,
    )
    session.add(message)
    conversation.agent_paused = True
    conversation.paused_by = Actor.OWNER
    conversation.paused_reason = OWNER_TOOK_OVER
    conversation.last_message_at = now
    record_activity(contact, now)
    if route.recipient.kind == "comment" and comment is not None:
        comment.private_reply_at = now
    await session.flush()
    sender = services.sender_for(conversation.channel, simulated=simulated)
    account = account_id_for(business, conversation.channel) or ""
    sent = await sender.send_text(account, route.recipient, message.text or "", tag=route.tag)
    message.external_id = sent.message_id
    if (
        route.recipient.kind == "comment"
        and sent.recipient_id
        and comment
        and comment.channel != conversation.channel
    ):
        await link_identity(
            session,
            business_id=business.id,
            contact_id=contact.id,
            channel=conversation.channel,
            external_id=sent.recipient_id,
            simulated=simulated,
        )
    return message


async def _open_comment(
    session: AsyncSession, conversation: Conversation, now: datetime
) -> Engagement | None:
    """Their newest comment that can still get its one private reply into this conversation's channel."""
    channels = [c for c in Channel if inbox_channel(c) == conversation.channel]
    return await session.scalar(
        select(Engagement)
        .where(
            Engagement.contact_id == conversation.contact_id,
            Engagement.channel.in_(channels),
            Engagement.private_reply_at.is_(None),
            Engagement.occurred_at >= now - PRIVATE_REPLY_WINDOW - timedelta(minutes=1),
        )
        .order_by(Engagement.id.desc())
        .limit(1)
    )
