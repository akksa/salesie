"""Sending Instagram and Messenger messages, and Meta's rules for when a business may message someone.

Send API: POST {graph}/{ig_account_id}/messages, body {"recipient": {"id": IGSID} | {"comment_id": ...},
"message": {"text": ...}}, response {"recipient_id", "message_id"}.
Windows: a DM is allowed within 24 hours of the person's last message; a "private reply" to a comment is
allowed once, within 7 days of the comment (developers.facebook.com/docs/instagram-platform/private-replies).
A human (not the agent) may reply up to 7 days after the person's last message with the HUMAN_AGENT tag.
"""

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal, Protocol

import httpx

from app.models import Business, Channel
from app.sanitize import redact

DM_WINDOW = timedelta(hours=24)
HUMAN_AGENT_WINDOW = timedelta(days=7)
HUMAN_AGENT_TAG = "HUMAN_AGENT"
PRIVATE_REPLY_WINDOW = timedelta(days=7)
MAX_TEXT_LENGTH = 1000  # Instagram's limit (Messenger allows more), counted in bytes: never more than chars


@dataclass(frozen=True)
class Recipient:
    kind: Literal["user", "comment"]
    id: str

    def as_json(self) -> dict[str, str]:
        return {"id": self.id} if self.kind == "user" else {"comment_id": self.id}


@dataclass(frozen=True)
class Blocked:
    reason: str


class SendError(Exception):
    pass


@dataclass(frozen=True)
class SentMessage:
    message_id: str
    # The person's id on this platform, as Meta reports it. For a Facebook private reply this is their
    # Messenger id (PSID), which can differ from the id on their comment: it lets Salesie link the two.
    recipient_id: str | None = None


class MessageSender(Protocol):
    @property
    def mode(self) -> Literal["live", "recorded"]: ...

    async def send_text(
        self, account_id: str, recipient: Recipient, text: str, tag: str | None = None
    ) -> SentMessage:
        """Send and return Meta's ids. `tag` marks e.g. a human agent reply outside 24 hours."""
        ...


class RecordingSender:
    """Sends nothing to Meta: the reply exists only in Salesie (simulated shoppers, or no Meta app yet)."""

    mode: Literal["recorded"] = "recorded"

    async def send_text(
        self, account_id: str, recipient: Recipient, text: str, tag: str | None = None
    ) -> SentMessage:
        return SentMessage(f"rec.{secrets.token_hex(12)}")


class GraphSender:
    """Meta's Send API, for Instagram (graph.instagram.com, account token) or Messenger (graph.facebook.com,
    Page access token). The token goes in a header, never the URL, so it can't end up in request logs."""

    mode: Literal["live"] = "live"

    def __init__(
        self,
        *,
        access_token: str,
        graph_url: str,
        platform: Literal["instagram", "messenger"] = "instagram",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._token = access_token
        self._platform = platform
        self._label = "Instagram" if platform == "instagram" else "Messenger"
        self._http = httpx.AsyncClient(
            base_url=graph_url.rstrip("/"),
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15.0,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def send_text(
        self, account_id: str, recipient: Recipient, text: str, tag: str | None = None
    ) -> SentMessage:
        body: dict[str, object] = {"recipient": recipient.as_json(), "message": {"text": text}}
        if tag:
            body |= {"messaging_type": "MESSAGE_TAG", "tag": tag}
        elif self._platform == "messenger":
            body["messaging_type"] = "RESPONSE"  # required by the Messenger Send API
        try:
            response = await self._http.post(f"/{account_id}/messages", json=body)
        except httpx.HTTPError as exc:
            raise SendError(f"{self._label} Send API unreachable: {type(exc).__name__}") from exc
        if response.status_code >= 400:
            detail = redact(_meta_error(response), [self._token])
            raise SendError(f"{self._label} Send API {response.status_code}: {detail}")
        data = response.json()
        message_id = data.get("message_id")
        if not isinstance(message_id, str) or not message_id:
            raise SendError(f"{self._label} Send API returned no message_id")
        recipient_id = data.get("recipient_id")
        return SentMessage(
            message_id, recipient_id if isinstance(recipient_id, str) and recipient_id else None
        )


def reply_route(
    *,
    now: datetime,
    contact_external_id: str,
    last_inbound_at: datetime | None,
    comment_id: str | None,
    comment_at: datetime | None,
    comment_already_replied: bool,
) -> Recipient | Blocked:
    """How (and whether) the business may reach this person right now."""
    if last_inbound_at is not None and now - last_inbound_at <= DM_WINDOW:
        return Recipient("user", contact_external_id)
    if comment_id is None or comment_at is None:
        return Blocked("outside Meta's 24-hour messaging window")
    if comment_already_replied:
        return Blocked("the one private reply allowed for this comment was already sent")
    if now - comment_at > PRIVATE_REPLY_WINDOW:
        return Blocked("the 7-day private reply window for this comment has passed")
    return Recipient("comment", comment_id)


@dataclass(frozen=True)
class OwnerRoute:
    recipient: Recipient
    tag: str | None


# Meta's clock and ours can differ: tag human replies a little before the 24 hours are strictly up.
_TAG_MARGIN = timedelta(minutes=10)


def owner_route(
    *,
    now: datetime,
    contact_external_id: str,
    last_inbound_at: datetime | None,
    open_comment_id: str | None = None,
    open_comment_at: datetime | None = None,
) -> OwnerRoute | Blocked:
    """When the owner (a person) may message someone: 24 hours after their last DM normally, 7 days with the
    HUMAN_AGENT tag; someone who only commented can get one private reply within 7 days of the comment."""
    if last_inbound_at is not None and now - last_inbound_at <= HUMAN_AGENT_WINDOW:
        tag = None if now - last_inbound_at <= DM_WINDOW - _TAG_MARGIN else HUMAN_AGENT_TAG
        return OwnerRoute(Recipient("user", contact_external_id), tag)
    if (
        open_comment_id is not None
        and open_comment_at is not None
        and now - open_comment_at <= PRIVATE_REPLY_WINDOW
    ):
        return OwnerRoute(Recipient("comment", open_comment_id), None)
    if last_inbound_at is None:
        return Blocked(
            "this shopper hasn't messaged you, and Meta only allows replies to people who wrote first"
        )
    return Blocked("Meta only lets you reply within 7 days of the shopper's last message")


def utf8_length(text: str) -> int:
    return len(text.encode("utf-8"))


def fit_message(text: str, limit: int = MAX_TEXT_LENGTH) -> str:
    """Trim to Meta's limit, counted in UTF-8 bytes to be safe with emoji and non-Latin scripts."""
    text = text.strip()
    if utf8_length(text) <= limit:
        return text
    budget = max(limit - utf8_length("…"), 0)
    trimmed = text.encode("utf-8")[:budget].decode("utf-8", errors="ignore").rstrip()
    return trimmed + "…" if limit >= utf8_length("…") else ""


def _meta_error(response: httpx.Response) -> str:
    try:
        return str(response.json()["error"]["message"])[:300]
    except (ValueError, KeyError, TypeError):
        return response.text[:300]


# --- which channel and account a conversation uses ----------------------------------------------------

_INBOX = {
    Channel.INSTAGRAM: Channel.INSTAGRAM,
    Channel.FACEBOOK: Channel.MESSENGER,  # replies to Facebook comments go to Messenger
    Channel.MESSENGER: Channel.MESSENGER,
}


def inbox_channel(channel: Channel) -> Channel:
    """Where a conversation with someone who engaged on `channel` happens."""
    return _INBOX.get(channel, channel)


def account_id_for(business: Business, channel: Channel) -> str | None:
    """The business's own id on a channel: what Meta puts in entry.id, and where we send from."""
    if channel == Channel.INSTAGRAM:
        return business.ig_account_id
    if channel in (Channel.FACEBOOK, Channel.MESSENGER):
        return business.fb_page_id
    return None


def platform_name(channel: Channel) -> str:
    return "Instagram" if channel == Channel.INSTAGRAM else "Facebook"
