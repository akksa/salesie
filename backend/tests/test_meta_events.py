"""Parsing edge cases that are awkward to reach through HTTP."""

from datetime import UTC, datetime

import pytest

from app.meta.events import InstagramComment, InstagramMessage, PayloadError, parse_meta_payload
from tests import meta_payloads as meta


def test_seconds_and_millisecond_timestamps_mean_the_same_instant() -> None:
    seconds = parse_meta_payload(
        meta.comment_via_changes(
            "1", comment_id="c", media_id="m", from_id="u", username="x", text="t", time=1_730_000_000
        )
    )
    millis = parse_meta_payload(
        meta.direct_message("1", mid="m", sender_id="u", text="t", timestamp_ms=1_730_000_000_000)
    )
    [comment] = seconds.events
    [message] = millis.events
    assert comment.occurred_at == message.occurred_at == datetime(2024, 10, 27, 3, 33, 20, tzinfo=UTC)


def test_unhandled_fields_and_objects_are_skipped_not_failed() -> None:
    payload = {
        "object": "instagram",
        "entry": [
            {
                "id": "1",
                "time": 1,
                "changes": [{"field": "mentions", "value": {"media_id": "m"}}],
                "messaging": [
                    {"sender": {"id": "u"}, "recipient": {"id": "1"}, "timestamp": 1, "read": {"mid": "x"}}
                ],
            }
        ],
    }
    parsed = parse_meta_payload(payload)
    assert parsed.events == ()
    assert len(parsed.skipped) == 2
    assert parse_meta_payload({"object": "whatsapp_business_account", "entry": []}).events == ()


def test_echo_contact_is_the_recipient() -> None:
    [message] = parse_meta_payload(meta.echo_message("1", mid="m", recipient_id="shopper", text="hi")).events
    assert isinstance(message, InstagramMessage)
    assert message.is_echo
    assert message.contact_external_id == "shopper"


def test_attachment_only_message_has_no_text() -> None:
    payload = meta.direct_message("1", mid="m", sender_id="u", text="x")
    del payload["entry"][0]["messaging"][0]["message"]["text"]
    payload["entry"][0]["messaging"][0]["message"]["attachments"] = [{"type": "image"}]
    [message] = parse_meta_payload(payload).events
    assert isinstance(message, InstagramMessage)
    assert message.text is None


def test_comment_reply_keeps_parent_id() -> None:
    payload = meta.comment_via_changes(
        "1", comment_id="c2", media_id="m", from_id="u", username="x", text="t"
    )
    payload["entry"][0]["changes"][0]["value"]["parent_id"] = "c1"
    [comment] = parse_meta_payload(payload).events
    assert isinstance(comment, InstagramComment)
    assert comment.parent_id == "c1"


@pytest.mark.parametrize(
    "payload",
    [[], {"object": "instagram"}, {"object": "instagram", "entry": "nope"}, {"entry": []}],
)
def test_broken_envelope_raises(payload: object) -> None:
    with pytest.raises(PayloadError):
        parse_meta_payload(payload)


def test_bad_items_are_reported_without_dropping_good_ones() -> None:
    good = meta.direct_message("1", mid="m.good", sender_id="u", text="hi")["entry"][0]
    payload = {
        "object": "instagram",
        "entry": [
            {"time": 1, "messaging": []},  # entry without id
            {"id": "1", "changes": [{"field": "comments", "value": {"text": "no ids"}}]},
            {"id": "1", "messaging": [{"sender": {}, "message": {"mid": "m"}}]},
            good,
        ],
    }
    parsed = parse_meta_payload(payload)
    assert [e.message_id for e in parsed.events if isinstance(e, InstagramMessage)] == ["m.good"]
    assert len(parsed.errors) == 3
    assert parsed.errors[0].startswith("entry[0]")


def test_standby_messages_are_parsed_and_flagged() -> None:
    payload = meta.direct_message("1", mid="m.sb", sender_id="u", text="hi")
    entry = payload["entry"][0]
    entry["standby"] = entry.pop("messaging")
    [message] = parse_meta_payload(payload).events
    assert isinstance(message, InstagramMessage)
    assert message.standby is True


def test_unknown_entry_keys_are_noted() -> None:
    payload = meta.direct_message("1", mid="m", sender_id="u", text="hi")
    payload["entry"][0]["mystery"] = []
    assert any("mystery" in note for note in parse_meta_payload(payload).skipped)


def test_float_and_out_of_range_timestamps() -> None:
    payload = meta.comment_via_changes("1", comment_id="c", media_id="m", from_id="u", username="x", text="t")
    payload["entry"][0]["time"] = 1_730_000_000.5
    [comment] = parse_meta_payload(payload).events
    assert comment.occurred_at.year == 2024
    payload["entry"][0]["time"] = 10**30
    parsed = parse_meta_payload(payload)
    assert parsed.events == ()
    assert "out of range" in parsed.errors[0]
