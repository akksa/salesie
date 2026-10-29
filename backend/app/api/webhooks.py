import logging
import secrets
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agent.runner import AgentServices, respond_all
from app.api.deps import SettingsDep
from app.meta.receiver import InvalidPayloadError, InvalidSignatureError, process_stored, store_meta_webhook
from app.meta.signature import SIGNATURE_HEADER

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.get("/meta", response_class=PlainTextResponse)
async def verify_subscription(
    settings: SettingsDep,
    mode: Annotated[str, Query(alias="hub.mode")],
    token: Annotated[str, Query(alias="hub.verify_token")],
    challenge: Annotated[str, Query(alias="hub.challenge", max_length=200)],
) -> str:
    """Meta calls this once when you save the webhook URL in the app dashboard."""
    expected = settings.meta_verify_token.get_secret_value()
    if mode != "subscribe" or not secrets.compare_digest(token.encode(), expected.encode()):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "verification failed")
    return challenge


@router.post("/meta")
async def receive(request: Request, settings: SettingsDep, background: BackgroundTasks) -> dict[str, str]:
    """Store, answer Meta immediately, then ingest after the response (Meta retries slow webhooks).
    Body size is capped by BodySizeLimitMiddleware before this runs."""
    sessionmaker = request.app.state.sessionmaker
    try:
        stored = await store_meta_webhook(
            sessionmaker,
            await request.body(),
            request.headers.get(SIGNATURE_HEADER),
            settings.meta_app_secret.get_secret_value(),
        )
    except InvalidSignatureError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid signature") from exc
    except InvalidPayloadError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    if stored.duplicate:
        return {"status": "duplicate"}
    background.add_task(_process_after_response, sessionmaker, request.app.state.agent, stored.event_id)
    return {"status": "received"}


async def _process_after_response(
    sessionmaker: async_sessionmaker[AsyncSession], agent: AgentServices, event_id: int
) -> None:
    try:
        processed = await process_stored(sessionmaker, event_id)
        await respond_all(sessionmaker, agent, processed.replies)
    except Exception:  # the event stays "received"; it can be replayed from the dashboard
        logger.exception("webhook event %s could not be processed", event_id)
