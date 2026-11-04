"""One agent turn: decide whether Meta allows a reply, let the model use its tools, send the reply, and record
every step in agent_runs.

Ordering guarantees:
- One turn per shopper at a time (agent lock); webhooks for the shopper keep flowing meanwhile.
- Tool writes happen in a savepoint, undone if the model fails or never settles on a reply.
- Every database write is flushed before the message is sent, and sending is the last step, so a database
  error can never leave a shopper holding a message (or payment link) that Salesie has no record of.
"""

import json
import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agent.gate import AgentGate
from app.agent.llm import ChatMessage, LLMClient, LLMError
from app.agent.prompt import AgentContext, build_messages
from app.agent.tools import TOOL_SPECS, ToolContext, run_tool
from app.channels.messaging import (
    Blocked,
    MessageSender,
    Recipient,
    SendError,
    account_id_for,
    fit_message,
    inbox_channel,
    platform_name,
    reply_route,
    utf8_length,
)
from app.crm.contacts import display_name, link_identity, record_activity
from app.crm.store import get_or_create, lock_agent_turn
from app.models import (
    OPEN_STAGES,
    Actor,
    AgentRun,
    AgentRunStatus,
    AgentTrigger,
    Author,
    Business,
    Channel,
    Contact,
    ContactIdentity,
    Conversation,
    Deal,
    Direction,
    Engagement,
    Message,
    Post,
    Product,
)
from app.payments.checkout import PaymentProvider
from app.sanitize import clean_json, clean_text

logger = logging.getLogger(__name__)
MAX_STEPS = 6
HOLDING_MESSAGE = "Thanks for your message! The owner will get back to you here shortly."
MAX_FOLLOW_UPS = 2  # extra turns for messages that arrive while the model is thinking
# Anything a shopper's app would turn into a link: scheme://..., www...., a domain with a path
# (evil.example/pay), or a bare domain with a common or two-letter country TLD. Labels may be any script
# (look-alike Cyrillic domains), and apps also accept the fullwidth and ideographic dots as dots.
# Instagram handles like "fay.loves" are left alone.
_COMMON_TLDS = (
    "com|net|org|io|co|app|shop|store|online|site|xyz|info|biz|me|ly|link|click|top|live|pay|money|"
    "ai|dev|vip|win|bid|icu|zip|mov|club|fun|life|world|today|email|support|help|page|tech|space|"
    "[a-z]{2}"
)
_DOT = "[.\uff0e\u3002\uff61]"
_LABEL = r"[^\W_](?:[\w-]*[^\W_])?"
_LINKISH = re.compile(
    rf"(?i)\b(?:[a-z][a-z0-9+.-]*://|www{_DOT})\S+"
    rf"|\b(?:{_LABEL}{_DOT})+[^\W\d_]{{2,}}/\S*"
    rf"|(?<![@\w.\uff0e\u3002\uff61])(?:{_LABEL}{_DOT})+(?:{_COMMON_TLDS})(?![.\uff0e\u3002\uff61\w])"
)
# Markdown the model may still write, which Instagram and Messenger would show as typed. Only ** bold and
# headings: single * and __ appear in ordinary text and handles ("5*", "@__maya__").
_BOLD = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", re.DOTALL)
_HEADING = re.compile(r"(?m)^[ \t]*#{1,6}[ \t]+")
_COVERED = (AgentRunStatus.REPLIED, AgentRunStatus.HANDED_OFF, AgentRunStatus.SKIPPED)


class _SupersededError(Exception):
    """The chat was paused (the owner took over) during the turn: undo it all and send nothing."""


@dataclass(frozen=True)
class AgentServices:
    llm: LLMClient
    recorder: MessageSender
    payments: PaymentProvider
    gate: AgentGate
    live_sender: MessageSender | None = None  # Instagram
    enabled: bool = True
    messenger_sender: MessageSender | None = None  # Facebook Messenger

    def sender_for(self, channel: Channel, *, simulated: bool) -> MessageSender:
        """Simulated shoppers are never messaged through Meta; neither is a channel with no token."""
        live = self.messenger_sender if channel == Channel.MESSENGER else self.live_sender
        return self.recorder if simulated or live is None else live


@dataclass(frozen=True)
class ReplyRequest:
    business_id: int
    contact_id: int
    trigger: AgentTrigger
    engagement_id: int | None = None
    channel: Channel = Channel.INSTAGRAM  # where the comment or message came in


@dataclass(frozen=True)
class _Shopper:
    business: Business
    contact: Contact
    inbox: Channel  # where the conversation happens (Messenger for Facebook commenters)
    identity: ContactIdentity | None  # their id in the inbox channel, once we know it
    identities: tuple[ContactIdentity, ...]
    simulated: bool
    conversation: Conversation | None
    engagement: Engagement | None

    @property
    def engagement_channel(self) -> Channel:
        """Where they found the business: the comment's channel, else their inbox's platform."""
        if self.engagement is not None:
            return self.engagement.channel
        return Channel.FACEBOOK if self.inbox == Channel.MESSENGER else self.inbox


@dataclass(frozen=True)
class _Outcome:
    status: AgentRunStatus
    text: str
    steps: list[dict[str, Any]]
    error: str | None = None


async def respond_all(
    sessionmaker: async_sessionmaker[AsyncSession], services: AgentServices, requests: Sequence[ReplyRequest]
) -> list[AgentRun]:
    """Answer a batch. One run per shopper for DMs: a run answers every message still unanswered."""
    runs: list[AgentRun] = []
    seen_dm: set[int] = set()
    for request in requests:
        if request.trigger == AgentTrigger.DM:
            if request.contact_id in seen_dm:
                continue
            seen_dm.add(request.contact_id)
        runs.extend(await respond(sessionmaker, services, request))
    return runs


async def respond(
    sessionmaker: async_sessionmaker[AsyncSession], services: AgentServices, request: ReplyRequest
) -> list[AgentRun]:
    """Reply to a shopper if there is something to answer and Meta allows it. Messages that arrive while the
    model is thinking get a follow-up turn. Returns the recorded runs (none if there was nothing to do)."""
    if not services.enabled:
        return []
    runs: list[AgentRun] = []
    async with services.gate.turn(request.contact_id):  # wait here, before taking a DB connection
        current = request
        for _ in range(1 + MAX_FOLLOW_UPS):
            run = await _turn(sessionmaker, services, current)
            if run is None:
                break
            runs.append(run)
            if run.status != AgentRunStatus.REPLIED:
                break
            current = ReplyRequest(
                request.business_id,
                request.contact_id,
                AgentTrigger.DM,
                channel=inbox_channel(request.channel),
            )
    return runs


async def _turn(
    sessionmaker: async_sessionmaker[AsyncSession], services: AgentServices, request: ReplyRequest
) -> AgentRun | None:
    started = datetime.now(UTC)
    try:
        async with sessionmaker() as session, session.begin():
            return await _respond(session, services, request, started)
    except _SupersededError:  # everything the turn did was rolled back; nothing was sent
        async with sessionmaker() as session, session.begin():
            error = "the owner took over while the agent was thinking; nothing was sent"
            run = _run(request, services.llm, AgentRunStatus.SKIPPED, started, error=error)
            session.add(run)
        return run
    except Exception as exc:  # recorded as a failed run below; full traceback in the log
        logger.exception("agent run for contact %s failed", request.contact_id)
        error = str(exc) if isinstance(exc, SendError) else f"{type(exc).__name__} (details in server log)"
        async with sessionmaker() as session, session.begin():
            run = _run(request, services.llm, AgentRunStatus.FAILED, started, error=error)
            session.add(run)
        return run


async def _respond(
    session: AsyncSession, services: AgentServices, request: ReplyRequest, started: datetime
) -> AgentRun | None:
    await lock_agent_turn(session, request.contact_id)  # same guarantee across processes
    shopper = await _load(session, request)
    if shopper is None or (shopper.conversation and shopper.conversation.agent_paused):
        return None
    if not await _has_something_to_answer(session, request, shopper):
        return None
    conversation, engagement = shopper.conversation, shopper.engagement
    route = reply_route(
        now=datetime.now(UTC),
        contact_external_id=shopper.identity.external_id if shopper.identity else "",
        last_inbound_at=conversation.last_inbound_at if conversation else None,
        comment_id=engagement.external_id if engagement else None,
        comment_at=engagement.occurred_at if engagement else None,
        comment_already_replied=bool(engagement and engagement.private_reply_at),
    )
    if isinstance(route, Blocked):
        run = _run(
            request, services.llm, AgentRunStatus.BLOCKED, started, error=route.reason, shopper=shopper
        )
        session.add(run)
        return run
    if not services.gate.spend(shopper.contact.id):
        return await _over_budget(session, services, request, shopper, started)
    tools = ToolContext(session, shopper.business, shopper.contact.id, shopper.inbox, services.payments)
    context = await _context(session, shopper, route)
    outcome = await _attempt(services.llm, build_messages(context, date.today()), tools)
    seen = max((m.id for m in context.history), default=None)
    return await _deliver(session, services, request, shopper, route, tools, outcome, started, seen)


async def _over_budget(
    session: AsyncSession,
    services: AgentServices,
    request: ReplyRequest,
    shopper: _Shopper,
    started: datetime,
) -> AgentRun:
    conversation, _ = await get_or_create(
        session,
        Conversation,
        {"business_id": shopper.business.id, "contact_id": shopper.contact.id, "channel": shopper.inbox},
    )
    conversation.agent_paused = True
    conversation.paused_by = Actor.AGENT
    conversation.paused_reason = "unusually many messages today: please check this chat"
    run = _run(
        request,
        services.llm,
        AgentRunStatus.HANDED_OFF,
        started,
        shopper=shopper,
        error="daily turn budget used",
    )
    run.conversation_id = conversation.id
    session.add(run)
    return run


async def _attempt(llm: LLMClient, messages: list[ChatMessage], tools: ToolContext) -> _Outcome:
    """Run the model loop in a savepoint; its writes are undone if the model errors or never settles.
    A temporary model error leaves the message unanswered (the next message retries); anything else hands
    the chat to the owner with a holding message, so the shopper isn't ignored."""
    steps: list[dict[str, Any]] = []
    try:
        async with tools.session.begin_nested() as attempt:
            text = await _converse(llm, messages, tools, steps)
            if text is None:
                await attempt.rollback()
    except LLMError as exc:
        tools.forget_effects()
        if exc.retryable:
            return _Outcome(AgentRunStatus.FAILED, "", steps, error=str(exc))
        tools.handoff_reason = "the agent couldn't reply (model error; see its runs)"
        return _Outcome(AgentRunStatus.FAILED, HOLDING_MESSAGE, steps, error=str(exc))
    if text is None:
        tools.forget_effects()
        tools.handoff_reason = f"the agent did not finish within {MAX_STEPS} steps"
        return _Outcome(AgentRunStatus.HANDED_OFF, HOLDING_MESSAGE, steps)
    status = AgentRunStatus.HANDED_OFF if tools.handoff_reason else AgentRunStatus.REPLIED
    return _Outcome(status, text, steps)


async def _converse(
    llm: LLMClient, messages: list[ChatMessage], tools: ToolContext, steps: list[dict[str, Any]]
) -> str | None:
    """Let the model call tools until it answers. Returns its reply, or None if it never finished."""
    history = list(messages)
    said = ""  # text the model wrote alongside tool calls, used if its final turn is empty
    for _ in range(MAX_STEPS):
        turn = await llm.complete(history, TOOL_SPECS)
        calls = [{"id": c.id, "name": c.name, "arguments": c.arguments} for c in turn.tool_calls]
        steps.append({"type": "model", "text": turn.text, "tool_calls": calls, "usage": turn.usage})
        if turn.text and turn.text.strip():
            said = turn.text
        if not turn.tool_calls:
            return said
        history.append(ChatMessage("assistant", turn.text, tool_calls=turn.tool_calls))
        for call in turn.tool_calls:
            result = await run_tool(tools, call.name, call.arguments)
            steps.append({"type": "tool", "name": call.name, "arguments": call.arguments, "result": result})
            history.append(ChatMessage("tool", json.dumps(result, default=str), tool_call_id=call.id))
    return None


async def _deliver(
    session: AsyncSession,
    services: AgentServices,
    request: ReplyRequest,
    shopper: _Shopper,
    route: Recipient,
    tools: ToolContext,
    outcome: _Outcome,
    started: datetime,
    seen: int | None,
) -> AgentRun:
    reply = final_text(outcome.text, tools.payment_link_url)
    if not reply and tools.handoff_reason:
        reply = HOLDING_MESSAGE
    if not reply:
        status = AgentRunStatus.FAILED if outcome.error else AgentRunStatus.SKIPPED
        run = _run(
            request, services.llm, status, started, steps=outcome.steps, shopper=shopper, error=outcome.error
        )
        run.last_seen_message_id = seen
        session.add(run)
        return run
    await tools.lock()  # final writes under the contact lock, like ingestion and the owner
    conversation, _ = await get_or_create(
        session,
        Conversation,
        {"business_id": shopper.business.id, "contact_id": shopper.contact.id, "channel": shopper.inbox},
    )
    await session.refresh(conversation)  # the owner may have taken over while the model was thinking
    if conversation.agent_paused:
        raise _SupersededError
    run = _run(
        request, services.llm, outcome.status, started, steps=outcome.steps, reply=reply, error=outcome.error
    )
    run.conversation_id = conversation.id
    run.last_seen_message_id = seen
    session.add(run)
    await session.flush()
    now = datetime.now(UTC)
    message = Message(
        conversation_id=conversation.id,
        direction=Direction.OUTBOUND,
        author=Author.AGENT,
        text=reply,
        sent_at=now,
        agent_run_id=run.id,
    )
    session.add(message)
    conversation.last_message_at = now
    record_activity(shopper.contact, now)
    if route.kind == "comment" and shopper.engagement is not None:
        shopper.engagement.private_reply_at = now
    if tools.handoff_reason:
        conversation.agent_paused = True
        conversation.paused_by = Actor.AGENT
        conversation.paused_reason = clean_text(tools.handoff_reason)[:500]
    await session.flush()  # any database error surfaces here, before the shopper receives anything
    sender = services.sender_for(shopper.inbox, simulated=shopper.simulated)
    account = account_id_for(shopper.business, shopper.inbox) or ""
    sent = await sender.send_text(account, route, reply)
    message.external_id = sent.message_id
    if route.kind == "comment" and sent.recipient_id and shopper.inbox != shopper.engagement_channel:
        await link_identity(
            session,
            business_id=shopper.business.id,
            contact_id=shopper.contact.id,
            channel=shopper.inbox,
            external_id=sent.recipient_id,
            simulated=shopper.simulated,
        )
    run.finished_at = datetime.now(UTC)  # reply time includes the send
    return run


def final_text(text: str, payment_link: str | None) -> str:
    """What may leave Salesie: plain text, and no links or web addresses except our own payment link, which
    arrives whole."""
    plain = _HEADING.sub("", _BOLD.sub(r"\1", text))
    cleaned = _LINKISH.sub(
        lambda m: m.group(0) if payment_link and m.group(0).startswith(payment_link) else "", plain
    )
    cleaned = re.sub(r"[ \t]{2,}", " ", clean_text(cleaned)).strip()
    if payment_link and payment_link not in cleaned:
        room = 1000 - utf8_length(payment_link) - 1
        cleaned = f"{fit_message(cleaned, limit=room)}\n{payment_link}".strip()
    return fit_message(cleaned)


async def notify_shopper(
    session: AsyncSession, services: AgentServices, contact_id: int, text: str, *, real_shopper_note: str = ""
) -> Message | None:
    """Send a templated message (e.g. a payment receipt) in the shopper's latest conversation, if Meta's
    24-hour window is open."""
    conversation = await session.scalar(
        select(Conversation)
        .where(Conversation.contact_id == contact_id)
        .order_by(Conversation.last_message_at.desc().nulls_last(), Conversation.id.desc())
        .limit(1)
    )
    business = await session.get(Business, conversation.business_id) if conversation else None
    identities = await _identities(session, contact_id)
    identity = next((i for i in identities if conversation and i.channel == conversation.channel), None)
    if conversation is None or identity is None or business is None:
        logger.info("no conversation to notify contact %s in", contact_id)
        return None
    route = reply_route(
        now=datetime.now(UTC),
        contact_external_id=identity.external_id,
        last_inbound_at=conversation.last_inbound_at,
        comment_id=None,
        comment_at=None,
        comment_already_replied=False,
    )
    if isinstance(route, Blocked):
        logger.info("not notifying contact %s: %s", contact_id, route.reason)
        return None
    now = datetime.now(UTC)
    message = Message(
        conversation_id=conversation.id,
        direction=Direction.OUTBOUND,
        author=Author.AGENT,
        text=fit_message(text if identity.simulated else f"{text}{real_shopper_note}"),
        sent_at=now,
    )
    session.add(message)
    conversation.last_message_at = now
    await session.flush()
    sender = services.sender_for(conversation.channel, simulated=identity.simulated)
    sent = await sender.send_text(
        account_id_for(business, conversation.channel) or "", route, message.text or ""
    )
    message.external_id = sent.message_id
    return message


# --- loading context ----------------------------------------------------------------------


async def _load(session: AsyncSession, request: ReplyRequest) -> _Shopper | None:
    business = await session.get(Business, request.business_id)
    contact = await session.get(Contact, request.contact_id)
    identities = await _identities(session, request.contact_id)
    if business is None or contact is None or not identities:
        return None
    inbox = inbox_channel(request.channel)
    conversation = await session.scalar(
        select(Conversation).where(Conversation.contact_id == contact.id, Conversation.channel == inbox)
    )
    engagement = await session.get(Engagement, request.engagement_id) if request.engagement_id else None
    return _Shopper(
        business=business,
        contact=contact,
        inbox=inbox,
        identity=next((i for i in identities if i.channel == inbox), None),
        identities=identities,
        simulated=any(i.simulated for i in identities),
        conversation=conversation,
        engagement=engagement,
    )


async def _identities(session: AsyncSession, contact_id: int) -> tuple[ContactIdentity, ...]:
    rows = await session.scalars(
        select(ContactIdentity).where(ContactIdentity.contact_id == contact_id).order_by(ContactIdentity.id)
    )
    return tuple(rows.all())


async def _has_something_to_answer(session: AsyncSession, request: ReplyRequest, shopper: _Shopper) -> bool:
    """Our replies are compared on our own clock and insertion order; Meta's clock can differ by seconds."""
    conversation = shopper.conversation
    if request.trigger == AgentTrigger.COMMENT:
        engagement = shopper.engagement
        if engagement is None or engagement.private_reply_at is not None:
            return False
        if conversation is None:
            return True
        replied_since = await session.scalar(
            select(Message.id)
            .where(
                Message.conversation_id == conversation.id,
                Message.author == Author.AGENT,
                Message.sent_at >= engagement.received_at,
            )
            .limit(1)
        )
        return replied_since is None
    if conversation is None:
        return False
    newest_inbound = await session.scalar(
        select(Message)
        .where(Message.conversation_id == conversation.id, Message.direction == Direction.INBOUND)
        .order_by(Message.id.desc())
        .limit(1)
    )
    if newest_inbound is None:
        return False
    owner_answered = await session.scalar(
        select(Message.id)
        .where(Message.conversation_id == conversation.id, Message.author == Author.OWNER)
        # the owner replied in Instagram (an echo, on Meta's clock), even if Meta delivered it first
        .where((Message.id > newest_inbound.id) | (Message.sent_at >= newest_inbound.sent_at))
        .limit(1)
    )
    if owner_answered is not None:
        return False
    covered = await _last_seen(session, shopper.contact.id)
    return covered is None or newest_inbound.id > covered  # something arrived after the model last looked


async def _last_seen(session: AsyncSession, contact_id: int) -> int | None:
    """Newest message id any answering turn had in front of it."""
    return await session.scalar(
        select(func.max(AgentRun.last_seen_message_id)).where(
            AgentRun.contact_id == contact_id, AgentRun.status.in_(_COVERED)
        )
    )


async def _context(session: AsyncSession, shopper: _Shopper, route: Recipient) -> AgentContext:
    open_deals = (
        await session.scalars(
            select(Deal)
            .where(Deal.contact_id == shopper.contact.id, Deal.stage.in_(OPEN_STAGES))
            .order_by(Deal.updated_at.desc(), Deal.id.desc())
            .limit(5)
        )
    ).all()
    with_products = tuple(
        [
            (deal, await session.get(Product, deal.product_id) if deal.product_id else None)
            for deal in open_deals
        ]
    )
    latest = open_deals[0] if open_deals else None
    post_id = (latest.source_post_id if latest else None) or (
        shopper.engagement.post_id if shopper.engagement else None
    )
    post = await session.get(Post, post_id) if post_id else None
    history: tuple[Message, ...] = ()
    if shopper.conversation is not None:
        recent = await session.scalars(
            select(Message)
            .where(Message.conversation_id == shopper.conversation.id)
            .order_by(Message.id.desc())  # insertion order: immune to clock differences
            .limit(20)
        )
        covered = await _last_seen(session, shopper.contact.id)
        # Messages no earlier turn saw go last, even if they were stored before that turn's reply.
        history = tuple(
            sorted(
                recent.all(),
                key=lambda m: (
                    m.direction == Direction.INBOUND and covered is not None and m.id > covered,
                    m.id,
                ),
            )
        )
    comments = await session.scalars(
        select(Engagement.text)
        .where(Engagement.contact_id == shopper.contact.id, Engagement.text.is_not(None))
        .where(Engagement.id != (shopper.engagement.id if shopper.engagement else 0))
        .order_by(Engagement.id.desc())
        .limit(3)
    )
    return AgentContext(
        business=shopper.business,
        contact_name=display_name(shopper.contact, list(shopper.identities)),
        platform=platform_name(shopper.engagement_channel),
        reply_channel=_reply_channel_label(shopper.inbox, route),
        open_deals=with_products,
        source_post=post,
        recent_comments=tuple(c for c in comments if c),
        history=history,
        new_comment=shopper.engagement.text if shopper.engagement else None,
    )


def _reply_channel_label(inbox: Channel, route: Recipient) -> str:
    if route.kind == "comment":
        return "a private reply to their comment" + (
            " (it arrives in Messenger)" if inbox == Channel.MESSENGER else ""
        )
    return "a Messenger message" if inbox == Channel.MESSENGER else "an Instagram DM"


def _run(
    request: ReplyRequest,
    llm: LLMClient,
    status: AgentRunStatus,
    started: datetime,
    *,
    steps: list[dict[str, Any]] | None = None,
    shopper: _Shopper | None = None,
    reply: str | None = None,
    error: str | None = None,
) -> AgentRun:
    return AgentRun(
        business_id=request.business_id,
        contact_id=request.contact_id,
        conversation_id=shopper.conversation.id if shopper and shopper.conversation else None,
        trigger=request.trigger,
        status=status,
        model=llm.model_name,
        steps=clean_json(steps or []),
        reply_text=reply,
        error=clean_text(error)[:2000] if error else None,
        started_at=started,
        finished_at=datetime.now(UTC),
    )
