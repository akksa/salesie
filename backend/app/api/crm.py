from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select

from app.agent.runner import respond_all
from app.api.deps import BusinessDep, IdPath, SessionDep, SettingsDep, require_owner
from app.crm import queries
from app.meta.receiver import process_event
from app.models import WebhookEvent, WebhookStatus
from app.schemas import (
    ContactDetail,
    ContactListItem,
    ConversationDetail,
    ConversationListItem,
    DealOut,
    WebhookEventOut,
)

router = APIRouter(prefix="/api", tags=["crm"], dependencies=[Depends(require_owner)])


@router.get("/app-config")
async def app_config(settings: SettingsDep) -> dict[str, bool]:
    return {"simulator_enabled": settings.simulator_enabled}


@router.get("/contacts")
async def list_contacts(business: BusinessDep, session: SessionDep) -> list[ContactListItem]:
    return await queries.list_contacts(session, business.id)


@router.get("/contacts/{contact_id}")
async def get_contact(contact_id: IdPath, business: BusinessDep, session: SessionDep) -> ContactDetail:
    contact = await queries.get_contact(session, business.id, contact_id)
    if contact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "contact not found")
    return contact


@router.get("/conversations")
async def list_conversations(business: BusinessDep, session: SessionDep) -> list[ConversationListItem]:
    return await queries.list_conversations(session, business.id)


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: IdPath, business: BusinessDep, session: SessionDep
) -> ConversationDetail:
    conversation = await queries.get_conversation(session, business.id, conversation_id)
    if conversation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "conversation not found")
    return conversation


@router.get("/deals")
async def list_deals(business: BusinessDep, session: SessionDep) -> list[DealOut]:
    return await queries.list_deals(session, business.id)


@router.get("/webhook-events")
async def list_webhook_events(
    session: SessionDep,
    status_filter: Annotated[WebhookStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[WebhookEventOut]:
    query = select(WebhookEvent).order_by(WebhookEvent.id.desc()).limit(limit)
    if status_filter is not None:
        query = query.where(WebhookEvent.status == status_filter)
    return [WebhookEventOut.model_validate(e) for e in await session.scalars(query)]


@router.post("/webhook-events/{event_id}/replay")
async def replay_webhook_event(event_id: IdPath, request: Request) -> WebhookEventOut:
    """Re-run a stored delivery (e.g. after connecting the right Instagram account). Safe to repeat:
    ingestion is idempotent, so events that already landed are not duplicated."""
    sessionmaker = request.app.state.sessionmaker
    async with sessionmaker() as session:
        try:
            processed = await process_event(session, event_id)
        except LookupError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "webhook event not found") from exc
        event = WebhookEventOut.model_validate(processed.event)
    await respond_all(sessionmaker, request.app.state.agent, processed.replies)
    return event
