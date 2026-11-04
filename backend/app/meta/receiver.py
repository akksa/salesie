"""The single entry point for Meta webhook deliveries, real or simulated.

Order matters: verify signature -> store the raw event (committed) -> ingest each Meta event in its own
transaction. One bad event can't discard the valid ones in the same delivery, per-contact locks are held
only briefly (no cross-contact deadlocks), and failures are recorded on the stored event. Ingestion is
idempotent, so a failed delivery can be replayed with process_event.
"""

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agent.runner import ReplyRequest
from app.crm.ingest import UnknownAccountError, ingest_event
from app.meta.events import Comment, MetaEvent, PayloadError, parse_meta_payload
from app.meta.signature import is_valid_signature
from app.models import WebhookEvent, WebhookStatus
from app.sanitize import clean_json

logger = logging.getLogger(__name__)
_MAX_ERROR_LENGTH = 2000


class InvalidSignatureError(Exception):
    pass


class InvalidPayloadError(Exception):
    pass


@dataclass(frozen=True)
class StoredDelivery:
    event_id: int
    duplicate: bool


async def store_meta_webhook(
    sessionmaker: async_sessionmaker[AsyncSession],
    body: bytes,
    signature: str | None,
    app_secret: str,
    *,
    simulated: bool = False,
) -> StoredDelivery:
    """Verify and persist a delivery. Cheap, so the HTTP route can answer Meta right away."""
    if not is_valid_signature(body, signature, app_secret):
        raise InvalidSignatureError("signature does not match the app secret")
    payload = _decode(body)
    digest = hashlib.sha256(body).hexdigest()
    async with sessionmaker() as session:
        event_id = await session.scalar(
            insert(WebhookEvent)
            .values(
                object_type=str(payload.get("object", "unknown"))[:64],
                payload=payload,
                simulated=simulated,
                body_sha256=digest,
                status=WebhookStatus.RECEIVED,
            )
            .on_conflict_do_nothing(index_elements=["body_sha256"])
            .returning(WebhookEvent.id)
        )
        if event_id is None:
            existing = await session.scalar(select(WebhookEvent.id).where(WebhookEvent.body_sha256 == digest))
            if existing is None:
                raise LookupError("duplicate delivery vanished")
            return StoredDelivery(existing, duplicate=True)
        await session.commit()
        return StoredDelivery(event_id, duplicate=False)


@dataclass(frozen=True)
class Processed:
    event: WebhookEvent
    replies: tuple[ReplyRequest, ...] = ()  # new comments/DMs the sales agent should answer


async def process_stored(sessionmaker: async_sessionmaker[AsyncSession], event_id: int) -> Processed:
    async with sessionmaker() as session:
        return await process_event(session, event_id)


async def receive_meta_webhook(
    sessionmaker: async_sessionmaker[AsyncSession],
    body: bytes,
    signature: str | None,
    app_secret: str,
    *,
    simulated: bool = False,
) -> Processed:
    """Store and process inline (the simulator needs the outcome in its response)."""
    stored = await store_meta_webhook(sessionmaker, body, signature, app_secret, simulated=simulated)
    if stored.duplicate:
        async with sessionmaker() as session:
            event = await session.get(WebhookEvent, stored.event_id)
            if event is None:
                raise LookupError(f"webhook event {stored.event_id} not found")
            return Processed(event)
    return await process_stored(sessionmaker, stored.event_id)


async def process_event(session: AsyncSession, event_id: int) -> Processed:
    """Ingest (or re-ingest) a stored delivery and record the outcome on it."""
    event = await session.get(WebhookEvent, event_id)
    if event is None:
        raise LookupError(f"webhook event {event_id} not found")
    payload, simulated = event.payload, event.simulated
    try:
        parsed = parse_meta_payload(payload)
    except PayloadError as exc:
        return Processed(await _finish(session, event_id, attempted=1, errors=[str(exc)]))
    errors = list(parsed.errors)
    replies: list[ReplyRequest] = []
    for item in parsed.events:
        try:
            reply = await ingest_event(session, item, simulated=simulated)
            await session.commit()
            if reply is not None:
                replies.append(reply)
        except Exception as exc:  # recorded on the event below and logged with traceback
            await session.rollback()
            logger.exception("webhook event %s: failed to ingest %s", event_id, _describe(item))
            errors.append(f"{_describe(item)}: {_owner_visible_error(exc)}")
    if parsed.skipped:
        logger.info("webhook event %s skipped: %s", event_id, "; ".join(parsed.skipped))
    attempted = len(parsed.events) + len(parsed.errors)
    return Processed(await _finish(session, event_id, attempted=attempted, errors=errors), tuple(replies))


async def _finish(session: AsyncSession, event_id: int, *, attempted: int, errors: list[str]) -> WebhookEvent:
    event = await session.get(WebhookEvent, event_id, populate_existing=True)
    if event is None:
        raise LookupError(f"webhook event {event_id} disappeared while processing")
    event.status = WebhookStatus.FAILED if errors else WebhookStatus.PROCESSED
    event.error = (
        (f"{len(errors)} of {attempted} item(s) failed: " + "; ".join(errors))[:_MAX_ERROR_LENGTH]
        if errors
        else None
    )
    event.processed_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(event)
    return event


def _decode(body: bytes) -> dict[str, Any]:
    try:
        payload = clean_json(json.loads(body))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise InvalidPayloadError("body is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise InvalidPayloadError("body must be a JSON object")
    return payload


def _owner_visible_error(exc: Exception) -> str:
    """Domain errors explain themselves; anything unexpected (e.g. a database error that could quote
    SQL) is summarised, with the full traceback in the server log."""
    if isinstance(exc, UnknownAccountError | PayloadError):
        return f"{type(exc).__name__}: {exc}"
    return f"{type(exc).__name__} (details in server log)"


def _describe(item: MetaEvent) -> str:
    if isinstance(item, Comment):
        return f"comment {item.comment_id}"
    return f"message {item.message_id}"
