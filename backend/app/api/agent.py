from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select

from app.agent.runner import AgentServices
from app.api.deps import BusinessDep, IdPath, SessionDep, require_owner
from app.crm import queries
from app.models import PAUSED_BY_OWNER, Actor, AgentRun, Conversation
from app.schemas import AgentRunOut, AgentStatusOut, ConversationListItem, ConversationUpdate

router = APIRouter(prefix="/api", tags=["agent"], dependencies=[Depends(require_owner)])


@router.get("/agent")
async def agent_status(request: Request) -> AgentStatusOut:
    agent: AgentServices = request.app.state.agent
    return AgentStatusOut(
        enabled=agent.enabled,
        model=agent.llm.model_name,
        is_mock=agent.llm.model_name.startswith("mock"),
        instagram_sending=agent.live_sender.mode if agent.live_sender else agent.recorder.mode,
        messenger_sending=agent.messenger_sender.mode if agent.messenger_sender else agent.recorder.mode,
        payments=agent.payments.name,
    )


@router.get("/conversations/{conversation_id}/agent-runs")
async def list_agent_runs(
    conversation_id: IdPath, business: BusinessDep, session: SessionDep
) -> list[AgentRunOut]:
    conversation = await _owned_conversation(session, business.id, conversation_id)
    runs = await session.scalars(
        select(AgentRun)
        .where(AgentRun.contact_id == conversation.contact_id)
        .order_by(AgentRun.id.desc())
        .limit(50)
    )
    return [AgentRunOut.model_validate(run) for run in runs]


@router.patch("/conversations/{conversation_id}")
async def update_conversation(
    conversation_id: IdPath, body: ConversationUpdate, business: BusinessDep, session: SessionDep
) -> ConversationListItem:
    """Pause the agent to take over a chat yourself, or resume it."""
    conversation = await _owned_conversation(session, business.id, conversation_id)
    if body.agent_paused is not None:
        conversation.agent_paused = body.agent_paused
        conversation.paused_by = Actor.OWNER if body.agent_paused else None
        conversation.paused_reason = PAUSED_BY_OWNER if body.agent_paused else None
    await session.commit()
    items = await queries.list_conversations(session, business.id, contact_id=conversation.contact_id)
    return next(item for item in items if item.id == conversation_id)


async def _owned_conversation(session: SessionDep, business_id: int, conversation_id: int) -> Conversation:
    conversation = await session.get(Conversation, conversation_id)
    if conversation is None or conversation.business_id != business_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "conversation not found")
    return conversation
