from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.exc import IntegrityError

from app.agent.runner import AgentServices
from app.api.deps import BusinessDep, IdPath, SessionDep, require_owner
from app.channels.instagram import InstagramSendError
from app.crm import pipeline as board
from app.crm.insights import insights
from app.crm.takeover import TakeoverBlockedError, send_owner_message
from app.models import Conversation, Deal
from app.schemas import DealDetail, DealUpdate, InsightsOut, MessageOut, OwnerMessageIn, PipelineOut

router = APIRouter(prefix="/api", tags=["dashboard"], dependencies=[Depends(require_owner)])


@router.get("/pipeline")
async def get_pipeline(business: BusinessDep, session: SessionDep) -> PipelineOut:
    return await board.pipeline(session, business)


@router.get("/deals/{deal_id}")
async def get_deal(deal_id: IdPath, business: BusinessDep, session: SessionDep) -> DealDetail:
    return await _detail(session, business, deal_id)


@router.patch("/deals/{deal_id}")
async def update_deal(
    deal_id: IdPath, body: DealUpdate, business: BusinessDep, session: SessionDep
) -> DealDetail:
    deal = await session.get(Deal, deal_id)
    if deal is None or deal.business_id != business.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "deal not found")
    try:
        await board.move_deal(session, deal, body.stage, amount_minor=body.amount_minor)
        await session.commit()
    except board.DealMoveRefusedError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "this shopper already has another open deal for this product"
        ) from exc
    return await _detail(session, business, deal_id)


@router.post("/conversations/{conversation_id}/messages", status_code=status.HTTP_201_CREATED)
async def send_message(
    conversation_id: IdPath,
    body: OwnerMessageIn,
    request: Request,
    business: BusinessDep,
    session: SessionDep,
) -> MessageOut:
    """Reply as the owner. The agent pauses on this chat until it is resumed."""
    agent: AgentServices = request.app.state.agent
    conversation = await session.get(Conversation, conversation_id)
    if conversation is None or conversation.business_id != business.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "conversation not found")
    try:
        message = await send_owner_message(session, agent, conversation, body.text)
        await session.commit()
    except TakeoverBlockedError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except InstagramSendError as exc:  # rolled back: nothing claims the message was sent
        await session.rollback()
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"Instagram didn't accept the message: {exc}"
        ) from exc
    return MessageOut.model_validate(message)


@router.get("/insights")
async def get_insights(
    business: BusinessDep, session: SessionDep, days: Annotated[int, Query(ge=1, le=365)] = 30
) -> InsightsOut:
    return await insights(session, business, days)


async def _detail(session: SessionDep, business: BusinessDep, deal_id: int) -> DealDetail:
    detail = await board.deal_detail(session, business, deal_id)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "deal not found")
    return detail
