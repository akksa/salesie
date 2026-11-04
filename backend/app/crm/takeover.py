"""The owner replies in a chat themselves. That pauses the agent on the chat until they resume it."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.runner import AgentServices
from app.channels.instagram import PRIVATE_REPLY_WINDOW, Blocked, fit_message, owner_route
from app.crm.contacts import record_activity
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
    """Instagram's rules don't allow a message to this person right now."""


async def send_owner_message(
    session: AsyncSession, services: AgentServices, conversation: Conversation, text: str
) -> Message:
    """Store the owner's message, pause the agent, then send. Sending is last: if Instagram refuses, the
    caller's transaction rolls back and nothing claims a message was sent."""
    await lock_contact(session, conversation.contact_id)
    await session.refresh(conversation)  # read the window after the lock: a DM may have just arrived
    identity = await session.scalar(
        select(ContactIdentity).where(
            ContactIdentity.contact_id == conversation.contact_id,
            ContactIdentity.channel == Channel.INSTAGRAM,
        )
    )
    business = await session.get(Business, conversation.business_id)
    contact = await session.get(Contact, conversation.contact_id)
    if identity is None or business is None or contact is None:
        raise LookupError(f"conversation {conversation.id} has no Instagram identity")
    now = datetime.now(UTC)
    comment = await _open_comment(session, conversation.contact_id, now)
    route = owner_route(
        now=now,
        contact_external_id=identity.external_id,
        last_inbound_at=conversation.last_inbound_at,
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
    message.external_id = await services.sender_for(identity).send_text(
        business.ig_account_id or "", route.recipient, message.text or "", tag=route.tag
    )
    return message


async def _open_comment(session: AsyncSession, contact_id: int, now: datetime) -> Engagement | None:
    """Their newest comment that can still get its one private reply."""
    return await session.scalar(
        select(Engagement)
        .where(
            Engagement.contact_id == contact_id,
            Engagement.private_reply_at.is_(None),
            Engagement.occurred_at >= now - PRIVATE_REPLY_WINDOW - timedelta(minutes=1),
        )
        .order_by(Engagement.id.desc())
        .limit(1)
    )
