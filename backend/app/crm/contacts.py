import logging
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.crm.merge import absorb_contact
from app.crm.store import get_or_create
from app.models import Channel, Contact, ContactIdentity

logger = logging.getLogger(__name__)
_CHANNEL_LABELS = {
    Channel.INSTAGRAM: "Instagram",
    Channel.WHATSAPP: "WhatsApp",
    Channel.FACEBOOK: "Facebook",
    Channel.MESSENGER: "Messenger",
}


async def upsert_contact(
    session: AsyncSession, business_id: int, channel: Channel, external_id: str, *, simulated: bool = False
) -> tuple[Contact, ContactIdentity]:
    """Find the contact behind a channel handle, creating contact + identity on first sight.
    Usernames are recorded separately (remember_username) once the event is known not to be a redelivery."""
    lookup = select(ContactIdentity).where(
        ContactIdentity.business_id == business_id,
        ContactIdentity.channel == channel,
        ContactIdentity.external_id == external_id,
    )
    identity = await session.scalar(lookup)
    if identity is None:
        try:
            async with session.begin_nested():
                contact = Contact(business_id=business_id)
                session.add(contact)
                await session.flush()
                identity = ContactIdentity(
                    business_id=business_id,
                    contact_id=contact.id,
                    channel=channel,
                    external_id=external_id,
                    simulated=simulated,
                )
                session.add(identity)
            return contact, identity
        except IntegrityError:
            identity = await session.scalar(lookup)  # another delivery created it first
            if identity is None:
                raise
    if simulated and not identity.simulated:
        raise PermissionError("a simulated event may not act on a real contact")
    contact = await session.get(Contact, identity.contact_id)
    if contact is None:
        raise LookupError(f"identity {identity.id} points at missing contact {identity.contact_id}")
    return contact, identity


def remember_username(identity: ContactIdentity, username: str | None, seen_at: datetime) -> None:
    """People rename accounts; keep the newest handle, ignoring late or redelivered older events."""
    if not username or (identity.username_seen_at and seen_at < identity.username_seen_at):
        return
    identity.username = username
    identity.username_seen_at = seen_at


def record_activity(contact: Contact, at: datetime) -> None:
    if contact.last_activity_at is None or at > contact.last_activity_at:
        contact.last_activity_at = at


def display_name(contact: Contact, identities: Sequence[ContactIdentity]) -> str:
    if contact.display_name:
        return contact.display_name
    named = next((i for i in identities if i.username), None)
    if named is not None:
        return f"@{named.username}"
    if identities:
        first = identities[0]
        return f"{_CHANNEL_LABELS[first.channel]} user …{first.external_id[-4:]}"
    return f"Contact #{contact.id}"


async def link_identity(
    session: AsyncSession,
    *,
    business_id: int,
    contact_id: int,
    channel: Channel,
    external_id: str,
    simulated: bool,
) -> None:
    """Record another id Meta reported for this contact (the Messenger id it returns after a private reply
    to their Facebook comment), so their next message lands on the same contact. If that id already
    belongs to another contact, Meta has just told us they're the same person: the two are merged.

    Runs after a message has gone out, so it never fails the caller: a problem is logged and undone."""
    try:
        async with session.begin_nested():
            await _link(session, business_id, contact_id, channel, external_id, simulated)
    except Exception:
        logger.exception("couldn't link %s id to contact %s", channel.value, contact_id)


async def _link(
    session: AsyncSession,
    business_id: int,
    contact_id: int,
    channel: Channel,
    external_id: str,
    simulated: bool,
) -> None:
    identity, created = await get_or_create(
        session,
        ContactIdentity,
        {"business_id": business_id, "channel": channel, "external_id": external_id},
        {"contact_id": contact_id, "simulated": simulated},
    )
    if created or identity.contact_id == contact_id:
        return
    if identity.simulated != simulated:
        logger.warning(
            "%s id %s is on a simulated and a real contact: not merged", channel.value, external_id
        )
        return
    shared = await _channels(session, contact_id) & await _channels(session, identity.contact_id)
    if shared:  # e.g. two different Facebook commenters: two people, whatever the reported id says
        logger.warning(
            "contacts %s and %s both have %s ids: not merged", contact_id, identity.contact_id, shared
        )
        return
    logger.info("contact %s is contact %s on %s: merging", identity.contact_id, contact_id, channel.value)
    await absorb_contact(session, keep_id=contact_id, drop_id=identity.contact_id)


async def _channels(session: AsyncSession, contact_id: int) -> set[Channel]:
    rows = await session.scalars(
        select(ContactIdentity.channel).where(ContactIdentity.contact_id == contact_id)
    )
    return set(rows.all())
