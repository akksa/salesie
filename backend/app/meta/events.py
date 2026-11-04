"""Turn raw Meta webhook payloads into typed events. Pure functions, no I/O.

Instagram (`object: "instagram"`) sends two comment envelopes depending on the app's login flow:
  - Facebook Login:  entry[].changes[] = [{field, value: {comment_id, ...}}]
  - Business Login:  entry[] carries field/value directly, value.id is the comment id
Facebook Pages (`object: "page"`) send comments as `feed` changes ({item: "comment", verb: "add",
comment_id, post_id, from: {id, name}, message, created_time}) and Messenger DMs in entry[].messaging[],
shaped like Instagram DMs. Timestamps arrive as seconds or milliseconds.

Meta batches several entries and items per delivery, so a malformed entry or item is reported in
ParsedPayload.errors instead of discarding the valid ones. Only a broken envelope raises PayloadError.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.models import Channel

_MILLISECONDS_THRESHOLD = 10**11  # 10-digit values are seconds, 13-digit values are milliseconds
# object type -> (channel of its comments, channel of its private messages)
_HANDLED_OBJECTS = {
    "instagram": (Channel.INSTAGRAM, Channel.INSTAGRAM),
    "page": (Channel.FACEBOOK, Channel.MESSENGER),
}


class PayloadError(ValueError):
    """The payload doesn't match any shape Meta documents."""


@dataclass(frozen=True)
class Comment:
    """A public comment on one of the business's posts (Instagram media or Facebook Page post)."""

    account_id: str  # the business's Instagram account id or Facebook Page id
    comment_id: str
    media_id: str  # Instagram media id or Facebook post id
    from_id: str
    from_username: str | None
    text: str | None
    parent_id: str | None
    occurred_at: datetime
    channel: Channel = Channel.INSTAGRAM
    from_name: str | None = None  # Facebook gives a display name instead of a username

    @property
    def is_thread_reply(self) -> bool:
        """A reply to another comment. Facebook sets parent_id to the post itself for top-level comments."""
        return self.parent_id is not None and self.parent_id != self.media_id


@dataclass(frozen=True)
class DirectMessage:
    """A private message: Instagram DM or Facebook Messenger."""

    account_id: str
    message_id: str
    sender_id: str
    recipient_id: str
    text: str | None
    is_echo: bool
    occurred_at: datetime
    standby: bool = False  # delivered while another app owns the thread (handover protocol)
    channel: Channel = Channel.INSTAGRAM

    @property
    def contact_external_id(self) -> str:
        """The shopper's id: the sender of inbound messages, the recipient of echoes."""
        return self.recipient_id if self.is_echo else self.sender_id


type MetaEvent = Comment | DirectMessage


@dataclass(frozen=True)
class ParsedPayload:
    object_type: str
    events: tuple[MetaEvent, ...]
    skipped: tuple[str, ...]
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class _EntryResult:
    events: tuple[MetaEvent, ...] = ()
    skipped: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


_ENTRY_KEYS = frozenset({"id", "time", "changes", "messaging", "standby", "field", "value"})


def parse_meta_payload(payload: object) -> ParsedPayload:
    body = _dict(payload, "payload")
    object_type = _str(body.get("object"), "object")
    entries = body.get("entry")
    if not isinstance(entries, list):
        raise PayloadError("entry must be a list")
    if object_type not in _HANDLED_OBJECTS:
        return ParsedPayload(object_type, (), (f"object {object_type!r} is not handled yet",))
    results = [_parse_entry_safely(object_type, index, entry) for index, entry in enumerate(entries)]
    return ParsedPayload(
        object_type,
        events=tuple(event for r in results for event in r.events),
        skipped=tuple(note for r in results for note in r.skipped),
        errors=tuple(error for r in results for error in r.errors),
    )


def _parse_entry_safely(object_type: str, index: int, entry: object) -> _EntryResult:
    try:
        return _parse_entry(object_type, index, _dict(entry, "entry"))
    except PayloadError as exc:
        return _EntryResult(errors=(f"entry[{index}]: {exc}",))


def _parse_entry(object_type: str, index: int, entry: dict[str, Any]) -> _EntryResult:
    comment_channel, message_channel = _HANDLED_OBJECTS[object_type]
    account_id = _str(entry.get("id"), "entry.id")
    changes = entry.get("changes")
    if changes is None and "field" in entry:
        changes = [{"field": entry["field"], "value": entry.get("value")}]
    events: list[MetaEvent] = []
    skipped: list[str] = []
    errors: list[str] = []
    for position, change in enumerate(_list(changes, "entry.changes")):
        where = f"entry[{index}].changes[{position}]"
        try:
            parsed = _parse_change(comment_channel, account_id, _dict(change, "change"), entry.get("time"))
            if isinstance(parsed, Comment):
                events.append(parsed)
            else:
                skipped.append(f"{where}: {parsed}")
        except PayloadError as exc:
            errors.append(f"{where}: {exc}")
    for key in ("messaging", "standby"):
        for position, item in enumerate(_list(entry.get(key), f"entry.{key}")):
            where = f"entry[{index}].{key}[{position}]"
            try:
                item = _dict(item, key)
                if "message" in item:
                    standby = key == "standby"
                    events.append(_parse_message(account_id, item, standby=standby, channel=message_channel))
                else:
                    skipped.append(f"{where}: keys {sorted(item)}")
            except PayloadError as exc:
                errors.append(f"{where}: {exc}")
    if unknown := sorted(set(entry) - _ENTRY_KEYS):
        skipped.append(f"entry[{index}]: unhandled keys {unknown}")
    return _EntryResult(tuple(events), tuple(skipped), tuple(errors))


def _parse_change(
    channel: Channel, account_id: str, change: dict[str, Any], entry_time: object
) -> Comment | str:
    """A Comment, or a note saying why the change was skipped."""
    field = change.get("field")
    if channel == Channel.INSTAGRAM and field == "comments":
        return _parse_instagram_comment(account_id, _dict(change.get("value"), "value"), entry_time)
    if channel == Channel.FACEBOOK and field == "feed":
        value = _dict(change.get("value"), "value")
        if value.get("item") == "comment" and value.get("verb") == "add":
            return _parse_page_comment(account_id, value, entry_time)
        return f"feed {value.get('item')!r}/{value.get('verb')!r}"
    return f"field {field!r}"


def _parse_instagram_comment(account_id: str, value: dict[str, Any], entry_time: object) -> Comment:
    sender = _dict(value.get("from"), "value.from")
    media = _dict(value.get("media"), "value.media")
    return Comment(
        account_id=account_id,
        comment_id=_str(value.get("comment_id") or value.get("id"), "value.comment_id"),
        media_id=_str(media.get("id"), "value.media.id"),
        from_id=_str(sender.get("id"), "value.from.id"),
        from_username=_optional_str(sender.get("username")),
        text=_optional_str(value.get("text")),
        parent_id=_optional_str(value.get("parent_id")),
        occurred_at=_timestamp(entry_time),  # Instagram comment values carry no time of their own
    )


def _parse_page_comment(page_id: str, value: dict[str, Any], entry_time: object) -> Comment:
    sender = _dict(value.get("from"), "value.from")
    return Comment(
        account_id=page_id,
        comment_id=_str(value.get("comment_id"), "value.comment_id"),
        media_id=_str(value.get("post_id"), "value.post_id"),
        from_id=_str(sender.get("id"), "value.from.id"),
        from_username=None,
        text=_optional_str(value.get("message")),
        parent_id=_optional_str(value.get("parent_id")),
        occurred_at=_timestamp(value.get("created_time") or entry_time),
        channel=Channel.FACEBOOK,
        from_name=_optional_str(sender.get("name")),
    )


def _parse_message(
    account_id: str, item: dict[str, Any], *, standby: bool, channel: Channel
) -> DirectMessage:
    message = _dict(item.get("message"), "messaging.message")
    return DirectMessage(
        account_id=account_id,
        message_id=_str(message.get("mid"), "message.mid"),
        sender_id=_str(_dict(item.get("sender"), "messaging.sender").get("id"), "sender.id"),
        recipient_id=_str(_dict(item.get("recipient"), "messaging.recipient").get("id"), "recipient.id"),
        text=_optional_str(message.get("text")),
        is_echo=message.get("is_echo") is True,
        occurred_at=_timestamp(item.get("timestamp")),
        standby=standby,
        channel=channel,
    )


def _timestamp(value: object) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise PayloadError(f"timestamp must be a number, got {type(value).__name__}")
    try:
        number = int(float(value))
    except (ValueError, OverflowError) as exc:
        raise PayloadError(f"timestamp {value!r} is not an integer") from exc
    seconds = number / 1000 if number >= _MILLISECONDS_THRESHOLD else number
    try:
        return datetime.fromtimestamp(seconds, UTC)
    except (OverflowError, OSError, ValueError) as exc:
        raise PayloadError(f"timestamp {value!r} is out of range") from exc


def _dict(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PayloadError(f"{name} must be an object")
    return value


def _list(value: object, name: str) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise PayloadError(f"{name} must be a list")
    return value


def _str(value: object, name: str) -> str:
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if not isinstance(value, str) or not value:
        raise PayloadError(f"{name} is missing")
    return value


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
