"""Small race-safe persistence helpers shared by the CRM services."""

from collections.abc import Mapping
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Base

_CONTACT_LOCK_NAMESPACE = 1


async def get_or_create[M: Base](
    session: AsyncSession,
    model: type[M],
    lookup: Mapping[str, Any],
    defaults: Mapping[str, Any] | None = None,
) -> tuple[M, bool]:
    """Return (row, created). Safe when two webhook deliveries race to create the same row:
    the loser's insert hits the unique constraint inside a savepoint and re-reads the winner's row."""
    query = select(model).filter_by(**lookup)
    found = await session.scalar(query)
    if found is not None:
        return found, False
    candidate = model(**lookup, **(defaults or {}))
    try:
        async with session.begin_nested():
            session.add(candidate)
    except IntegrityError:
        found = await session.scalar(query)
        if found is None:
            raise
        return found, False
    return candidate, True


async def lock_contact(session: AsyncSession, contact_id: int) -> None:
    """Serialize all CRM writes for one contact until the transaction ends (deal and conversation logic
    reads-then-writes, so two concurrent webhooks for the same person must not interleave)."""
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:namespace, :contact_id)"),
        {"namespace": _CONTACT_LOCK_NAMESPACE, "contact_id": contact_id},
    )


_AGENT_LOCK_NAMESPACE = 2


async def lock_agent_turn(session: AsyncSession, contact_id: int) -> None:
    """One agent turn per shopper at a time. Separate from the contact lock, so new webhooks for the shopper
    are stored while the (slow) model is thinking; the next turn answers them."""
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:namespace, :contact_id)"),
        {"namespace": _AGENT_LOCK_NAMESPACE, "contact_id": contact_id},
    )
