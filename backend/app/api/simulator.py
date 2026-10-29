from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select

from app.agent.runner import respond_all
from app.api.deps import BusinessDep, SessionDep, SettingsDep, require_owner
from app.config import Settings
from app.meta import simulator
from app.models import Business, Channel, ContactIdentity, Conversation, Post
from app.schemas import (
    AgentRunOut,
    SimulatedCommentIn,
    SimulatedDirectMessageIn,
    SimulationResult,
    WebhookEventOut,
)


def require_simulator(settings: SettingsDep) -> None:
    if not settings.simulator_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not Found")


router = APIRouter(
    prefix="/api/simulator",
    tags=["simulator"],
    dependencies=[Depends(require_owner), Depends(require_simulator)],
)


@router.post("/instagram/comment")
async def simulate_comment(
    body: SimulatedCommentIn,
    request: Request,
    business: BusinessDep,
    session: SessionDep,
    settings: SettingsDep,
) -> SimulationResult:
    post = await session.get(Post, body.post_id)
    if post is None or post.business_id != business.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "post not found")
    payload = simulator.comment_payload(_account_id(business), post.external_id, body.username, body.text)
    return await _deliver(request, settings, session, business, payload, body.username)


@router.post("/instagram/dm")
async def simulate_direct_message(
    body: SimulatedDirectMessageIn,
    request: Request,
    business: BusinessDep,
    session: SessionDep,
    settings: SettingsDep,
) -> SimulationResult:
    payload = simulator.direct_message_payload(_account_id(business), body.username, body.text)
    return await _deliver(request, settings, session, business, payload, body.username)


def _account_id(business: Business) -> str:
    if not business.ig_account_id:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Set the business's Instagram account id before simulating traffic"
        )
    return business.ig_account_id


async def _deliver(
    request: Request,
    settings: Settings,
    session: SessionDep,
    business: Business,
    payload: dict[str, Any],
    username: str,
) -> SimulationResult:
    sessionmaker = request.app.state.sessionmaker
    processed = await simulator.deliver_simulated(
        sessionmaker, payload, settings.meta_app_secret.get_secret_value()
    )
    runs = await respond_all(sessionmaker, request.app.state.agent, processed.replies)  # inline: demo sees it
    contact_id = await session.scalar(
        select(ContactIdentity.contact_id).where(
            ContactIdentity.business_id == business.id,
            ContactIdentity.channel == Channel.INSTAGRAM,
            ContactIdentity.external_id == simulator.simulated_user_id(username),
        )
    )
    conversation_id = (
        await session.scalar(
            select(Conversation.id).where(
                Conversation.contact_id == contact_id, Conversation.channel == Channel.INSTAGRAM
            )
        )
        if contact_id is not None
        else None
    )
    return SimulationResult(
        **WebhookEventOut.model_validate(processed.event).model_dump(),
        contact_id=contact_id,
        conversation_id=conversation_id,
        agent_runs=[AgentRunOut.model_validate(run) for run in runs],
    )
