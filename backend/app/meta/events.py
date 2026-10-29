"""Turn raw Meta webhook payloads into typed events. Pure functions, no I/O.

Instagram sends two comment envelopes depending on the app's login flow:
  - Facebook Login:  entry[].changes[] = [{field, value: {comment_id, ...}}]
  - Business Login:  entry[] carries field/value directly, value.id is the comment id
Both are accepted. Timestamps arrive as seconds or milliseconds.

Meta batches several entries and items per delivery, so a malformed entry or item is reported in
ParsedPayload.errors instead of discarding the valid ones. Only a broken envelope raises PayloadError.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

_MILLISECONDS_THRESHOLD = 10**11  # 10-digit values are seconds, 13-digit values are milliseconds


class PayloadError(ValueError):
    """The payload doesn't match any shape Meta documents."""


@dataclass(frozen=True)
class InstagramComment:
    account_id: str
    comment_id: str
    media_id: str
    from_id: str
    from_username: str | None
    text: str | None
    parent_id: str | None
    occurred_at: datetime


@dataclass(frozen=True)
class InstagramMessage:
    account_id: str
    message_id: str
    sender_id: str
    recipient_id: str
    text: str | None
    is_echo: bool
    occurred_at: datetime
    standby: bool = False  # delivered while another app owns the thread (handover protocol)

    @property
    def contact_external_id(self) -> str:
        """The shopper's id: the sender of inbound messages, the recipient of echoes."""
        return self.recipient_id if self.is_echo else self.sender_id


type MetaEvent = InstagramComment | InstagramMessage


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
    if object_type != "instagram":
        return ParsedPayload(object_type, (), (f"object {object_type!r} is not handled yet",))
    results = [_parse_entry_safely(index, entry) for index, entry in enumerate(entries)]
    return ParsedPayload(
        object_type,
        events=tuple(event for r in results for event in r.events),
        skipped=tuple(note for r in results for note in r.skipped),
        errors=tuple(error for r in results for error in r.errors),
    )


def _parse_entry_safely(index: int, entry: object) -> _EntryResult:
    try:
        return _parse_instagram_entry(index, _dict(entry, "entry"))
    except PayloadError as exc:
        return _EntryResult(errors=(f"entry[{index}]: {exc}",))


def _parse_instagram_entry(index: int, entry: dict[str, Any]) -> _EntryResult:
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
            change = _dict(change, "change")
            if change.get("field") == "comments":
                value = _dict(change.get("value"), "value")
                events.append(_parse_comment(account_id, value, entry.get("time")))
            else:
                skipped.append(f"{where}: field {change.get('field')!r}")
        except PayloadError as exc:
            errors.append(f"{where}: {exc}")
    for key in ("messaging", "standby"):
        for position, item in enumerate(_list(entry.get(key), f"entry.{key}")):
            where = f"entry[{index}].{key}[{position}]"
            try:
                item = _dict(item, key)
                if "message" in item:
                    events.append(_parse_message(account_id, item, standby=key == "standby"))
                else:
                    skipped.append(f"{where}: keys {sorted(item)}")
            except PayloadError as exc:
                errors.append(f"{where}: {exc}")
    if unknown := sorted(set(entry) - _ENTRY_KEYS):
        skipped.append(f"entry[{index}]: unhandled keys {unknown}")
    return _EntryResult(tuple(events), tuple(skipped), tuple(errors))


def _parse_comment(account_id: str, value: dict[str, Any], entry_time: object) -> InstagramComment:
    sender = _dict(value.get("from"), "value.from")
    media = _dict(value.get("media"), "value.media")
    return InstagramComment(
        account_id=account_id,
        comment_id=_str(value.get("comment_id") or value.get("id"), "value.comment_id"),
        media_id=_str(media.get("id"), "value.media.id"),
        from_id=_str(sender.get("id"), "value.from.id"),
        from_username=_optional_str(sender.get("username")),
        text=_optional_str(value.get("text")),
        parent_id=_optional_str(value.get("parent_id")),
        occurred_at=_timestamp(entry_time),  # comment values carry no time of their own
    )


def _parse_message(account_id: str, item: dict[str, Any], *, standby: bool) -> InstagramMessage:
    message = _dict(item.get("message"), "messaging.message")
    return InstagramMessage(
        account_id=account_id,
        message_id=_str(message.get("mid"), "message.mid"),
        sender_id=_str(_dict(item.get("sender"), "messaging.sender").get("id"), "sender.id"),
        recipient_id=_str(_dict(item.get("recipient"), "messaging.recipient").get("id"), "recipient.id"),
        text=_optional_str(message.get("text")),
        is_echo=message.get("is_echo") is True,
        occurred_at=_timestamp(item.get("timestamp")),
        standby=standby,
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
