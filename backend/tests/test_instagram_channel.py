import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.channels.messaging import (
    Blocked,
    GraphSender,
    Recipient,
    SendError,
    SentMessage,
    fit_message,
    reply_route,
)

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)


def sender_with(handler) -> GraphSender:
    return GraphSender(
        access_token="IGAA-test",
        graph_url="https://graph.instagram.com/v23.0",
        transport=httpx.MockTransport(handler),
    )


@pytest.mark.parametrize(
    ("recipient", "expected"),
    [(Recipient("user", "9100"), {"id": "9100"}), (Recipient("comment", "1790"), {"comment_id": "1790"})],
)
async def test_send_api_request(recipient: Recipient, expected: dict) -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"recipient_id": "9100", "message_id": "aWdfZAG1"})

    message_id = await sender_with(handler).send_text("17841400000000001", recipient, "Hi there")
    [request] = captured
    assert str(request.url) == "https://graph.instagram.com/v23.0/17841400000000001/messages"
    assert request.headers["authorization"] == "Bearer IGAA-test"
    assert json.loads(request.content) == {"recipient": expected, "message": {"text": "Hi there"}}
    assert message_id == SentMessage("aWdfZAG1", "9100")


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(400, json={"error": {"message": "(#10) Outside of allowed window", "code": 10}}),
        httpx.Response(200, json={"recipient_id": "9100"}),
    ],
)
async def test_send_api_failures_raise(response: httpx.Response) -> None:
    with pytest.raises(SendError):
        await sender_with(lambda request: response).send_text("1", Recipient("user", "9100"), "Hi")


def test_dm_within_24_hours_of_their_last_message() -> None:
    route = reply_route(
        now=NOW,
        contact_external_id="9100",
        last_inbound_at=NOW - timedelta(hours=23),
        comment_id="1790",
        comment_at=NOW,
        comment_already_replied=False,
    )
    assert route == Recipient("user", "9100")


def test_private_reply_when_they_only_commented() -> None:
    route = reply_route(
        now=NOW,
        contact_external_id="9100",
        last_inbound_at=None,
        comment_id="1790",
        comment_at=NOW - timedelta(days=6, hours=23),
        comment_already_replied=False,
    )
    assert route == Recipient("comment", "1790")


@pytest.mark.parametrize(
    ("last_inbound", "comment_at", "replied", "reason"),
    [
        (NOW - timedelta(hours=25), None, False, "24-hour"),
        (None, NOW - timedelta(days=7, minutes=1), False, "7-day"),
        (None, NOW - timedelta(hours=1), True, "already sent"),
    ],
)
def test_blocked_routes(last_inbound, comment_at, replied, reason) -> None:
    route = reply_route(
        now=NOW,
        contact_external_id="9100",
        last_inbound_at=last_inbound,
        comment_id="1790" if comment_at else None,
        comment_at=comment_at,
        comment_already_replied=replied,
    )
    assert isinstance(route, Blocked)
    assert reason in route.reason


def test_messages_are_trimmed_to_instagrams_limit() -> None:
    assert fit_message("  hi  ") == "hi"
    long = fit_message("x" * 1500)
    assert len(long.encode()) <= 1000 and long.endswith("…")
    emoji = fit_message("😍" * 400)  # 4 bytes each: limited by bytes, never split mid-character
    assert len(emoji.encode()) <= 1000 and emoji.endswith("…") and "\ufffd" not in emoji
