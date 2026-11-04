"""Read models for the owner dashboard. A few batched queries per call, assembled in Python."""

from collections import defaultdict
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncSession

from app.crm.contacts import display_name
from app.models import Contact, ContactIdentity, Conversation, Deal, Engagement, Message, Product
from app.schemas import (
    ContactDetail,
    ContactListItem,
    ConversationDetail,
    ConversationListItem,
    DealOut,
    EngagementOut,
    IdentityOut,
    MessageOut,
)

LIST_LIMIT = 200


async def list_contacts(session: AsyncSession, business_id: int) -> list[ContactListItem]:
    """Most recent activity first; ordered in SQL so the newest leads survive the limit."""
    recency = func.coalesce(Contact.last_activity_at, Contact.created_at)
    contacts = list(
        await session.scalars(
            select(Contact)
            .where(Contact.business_id == business_id)
            .order_by(recency.desc(), Contact.id.desc())
            .limit(LIST_LIMIT)
        )
    )
    return await _contact_items(session, contacts)


async def get_contact(session: AsyncSession, business_id: int, contact_id: int) -> ContactDetail | None:
    contact = await session.get(Contact, contact_id)
    if contact is None or contact.business_id != business_id:
        return None
    [item] = await _contact_items(session, [contact])
    engagements = await session.scalars(
        select(Engagement).where(Engagement.contact_id == contact_id).order_by(Engagement.occurred_at.desc())
    )
    return ContactDetail(
        **item.model_dump(),
        engagements=[EngagementOut.model_validate(e) for e in engagements],
        deals=await list_deals(session, business_id, contact_id=contact_id),
        conversations=await list_conversations(session, business_id, contact_id=contact_id),
    )


async def list_deals(
    session: AsyncSession, business_id: int, *, contact_id: int | None = None
) -> list[DealOut]:
    query = (
        select(Deal, Product.name)
        .outerjoin(Product, Product.id == Deal.product_id)
        .where(Deal.business_id == business_id)
        .order_by(Deal.updated_at.desc(), Deal.id.desc())
        .limit(LIST_LIMIT)
    )
    if contact_id is not None:
        query = query.where(Deal.contact_id == contact_id)
    rows = (await session.execute(query)).all()
    names = await contact_names(session, {deal.contact_id for deal, _ in rows})
    return [deal_out(deal, product_name, names[deal.contact_id]) for deal, product_name in rows]


async def list_conversations(
    session: AsyncSession, business_id: int, *, contact_id: int | None = None
) -> list[ConversationListItem]:
    query = (
        select(Conversation)
        .where(Conversation.business_id == business_id)
        .order_by(Conversation.last_message_at.desc().nulls_last(), Conversation.id.desc())
        .limit(LIST_LIMIT)
    )
    if contact_id is not None:
        query = query.where(Conversation.contact_id == contact_id)
    conversations = list(await session.scalars(query))
    ids = [c.id for c in conversations]
    latest = await session.scalars(
        select(Message)
        .where(Message.conversation_id.in_(ids))
        .ext(distinct_on(Message.conversation_id))
        .order_by(Message.conversation_id, Message.sent_at.desc(), Message.id.desc())
    )
    last_by_conversation = {m.conversation_id: m for m in latest}
    names = await contact_names(session, {c.contact_id for c in conversations})
    return [_conversation_item(c, names[c.contact_id], last_by_conversation.get(c.id)) for c in conversations]


async def get_conversation(
    session: AsyncSession, business_id: int, conversation_id: int
) -> ConversationDetail | None:
    conversation = await session.get(Conversation, conversation_id)
    if conversation is None or conversation.business_id != business_id:
        return None
    messages = list(
        await session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.sent_at, Message.id)
        )
    )
    names = await contact_names(session, {conversation.contact_id})
    item = _conversation_item(
        conversation, names[conversation.contact_id], messages[-1] if messages else None
    )
    return ConversationDetail(**item.model_dump(), messages=[MessageOut.model_validate(m) for m in messages])


# --- helpers ------------------------------------------------------------------


async def _contact_items(session: AsyncSession, contacts: Sequence[Contact]) -> list[ContactListItem]:
    ids = [c.id for c in contacts]
    identities = await _identities(session, ids)
    latest_deals = await _latest_deals(session, ids)
    items = []
    for contact in contacts:
        name = display_name(contact, identities[contact.id])
        deal = latest_deals.get(contact.id)
        items.append(
            ContactListItem(
                id=contact.id,
                display_name=name,
                identities=[IdentityOut.model_validate(i) for i in identities[contact.id]],
                latest_deal=deal_out(deal[0], deal[1], name) if deal else None,
                last_activity_at=contact.last_activity_at,
                created_at=contact.created_at,
            )
        )
    return items


async def _identities(session: AsyncSession, contact_ids: Sequence[int]) -> dict[int, list[ContactIdentity]]:
    rows = await session.scalars(
        select(ContactIdentity)
        .where(ContactIdentity.contact_id.in_(contact_ids))
        .order_by(ContactIdentity.id)
    )
    grouped: dict[int, list[ContactIdentity]] = defaultdict(list)
    for identity in rows:
        grouped[identity.contact_id].append(identity)
    return grouped


async def contact_names(session: AsyncSession, contact_ids: set[int]) -> dict[int, str]:
    contacts = await session.scalars(select(Contact).where(Contact.id.in_(contact_ids)))
    identities = await _identities(session, list(contact_ids))
    return {c.id: display_name(c, identities[c.id]) for c in contacts}


async def _latest_deals(
    session: AsyncSession, contact_ids: Sequence[int]
) -> dict[int, tuple[Deal, str | None]]:
    rows = await session.execute(
        select(Deal, Product.name)
        .outerjoin(Product, Product.id == Deal.product_id)
        .where(Deal.contact_id.in_(contact_ids))
        .ext(distinct_on(Deal.contact_id))
        .order_by(Deal.contact_id, Deal.updated_at.desc(), Deal.id.desc())
    )
    return {deal.contact_id: (deal, product_name) for deal, product_name in rows}


def deal_out(deal: Deal, product_name: str | None, contact_name: str) -> DealOut:
    return DealOut(
        id=deal.id,
        contact_id=deal.contact_id,
        contact_name=contact_name,
        stage=deal.stage,
        channel=deal.channel,
        product_id=deal.product_id,
        product_name=product_name,
        source_post_id=deal.source_post_id,
        amount_minor=deal.amount_minor,
        details=deal.details,
        created_at=deal.created_at,
        updated_at=deal.updated_at,
    )


def _conversation_item(
    conversation: Conversation, contact_name: str, last: Message | None
) -> ConversationListItem:
    return ConversationListItem(
        id=conversation.id,
        contact_id=conversation.contact_id,
        contact_name=contact_name,
        channel=conversation.channel,
        agent_paused=conversation.agent_paused,
        paused_by=conversation.paused_by,
        paused_reason=conversation.paused_reason,
        last_inbound_at=conversation.last_inbound_at,
        last_message=MessageOut.model_validate(last) if last else None,
    )
