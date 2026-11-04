"""Webhook bodies shaped like Meta's documented examples.

Sources: developers.facebook.com/documentation/instagram-platform/webhooks/examples and
developers.facebook.com/docs/graph-api/webhooks/reference/instagram. Deliberately written
independently of app/meta/simulator.py so the tests don't just check the simulator against itself.
"""

from typing import Any


def comment_via_changes(
    account_id: str,
    *,
    comment_id: str,
    media_id: str,
    from_id: str,
    username: str,
    text: str,
    time: int = 1_730_000_000,
) -> dict[str, Any]:
    """Facebook Login / unified flow: entry[].changes[] with value.comment_id."""
    return {
        "object": "instagram",
        "entry": [
            {
                "id": account_id,
                "time": time,
                "changes": [
                    {
                        "field": "comments",
                        "value": {
                            "from": {"id": from_id, "username": username},
                            "comment_id": comment_id,
                            "text": text,
                            "media": {"id": media_id, "media_product_type": "FEED"},
                        },
                    }
                ],
            }
        ],
    }


def comment_via_entry_field(
    account_id: str,
    *,
    comment_id: str,
    media_id: str,
    from_id: str,
    username: str,
    text: str,
    time: int = 1_730_000_000,
) -> dict[str, Any]:
    """Business Login for Instagram: field/value directly on the entry, value.id."""
    return {
        "object": "instagram",
        "entry": [
            {
                "id": account_id,
                "time": time,
                "field": "comments",
                "value": {
                    "id": comment_id,
                    "from": {"id": from_id, "username": username},
                    "text": text,
                    "media": {"id": media_id, "media_product_type": "FEED"},
                },
            }
        ],
    }


def direct_message(
    account_id: str, *, mid: str, sender_id: str, text: str, timestamp_ms: int = 1_730_000_100_123
) -> dict[str, Any]:
    return {
        "object": "instagram",
        "entry": [
            {
                "id": account_id,
                "time": timestamp_ms,
                "messaging": [
                    {
                        "sender": {"id": sender_id},
                        "recipient": {"id": account_id},
                        "timestamp": timestamp_ms,
                        "message": {"mid": mid, "text": text},
                    }
                ],
            }
        ],
    }


def echo_message(
    account_id: str, *, mid: str, recipient_id: str, text: str, timestamp_ms: int = 1_730_000_200_456
) -> dict[str, Any]:
    """What Meta sends when the business itself sends a DM (e.g. from the Instagram app)."""
    return {
        "object": "instagram",
        "entry": [
            {
                "id": account_id,
                "time": timestamp_ms,
                "messaging": [
                    {
                        "sender": {"id": account_id},
                        "recipient": {"id": recipient_id},
                        "timestamp": timestamp_ms,
                        "message": {"mid": mid, "text": text, "is_echo": True},
                    }
                ],
            }
        ],
    }


# --- Facebook Page (object "page") ----------------------------------------------------------------
# Sources: developers.facebook.com/documentation/pages-api/webhooks-for-pages (feed) and
# developers.facebook.com/documentation/business-messaging/messenger-platform/webhooks/webhook-events/messages


def page_comment(
    page_id: str,
    *,
    comment_id: str,
    post_id: str,
    from_id: str,
    name: str,
    text: str,
    created_time: int = 1_730_000_000,
    parent_id: str | None = None,
) -> dict[str, Any]:
    """Facebook sets parent_id to the post for top-level comments, and to the comment for replies."""
    return {
        "object": "page",
        "entry": [
            {
                "id": page_id,
                "time": created_time + 2,
                "changes": [
                    {
                        "field": "feed",
                        "value": {
                            "from": {"id": from_id, "name": name},
                            "post": {"status_type": "added_photos", "is_published": True},
                            "message": text,
                            "post_id": post_id,
                            "comment_id": comment_id,
                            "created_time": created_time,
                            "item": "comment",
                            "parent_id": parent_id or post_id,
                            "verb": "add",
                        },
                    }
                ],
            }
        ],
    }


def messenger_message(
    page_id: str, *, mid: str, psid: str, text: str, timestamp_ms: int = 1_730_000_100_123, echo: bool = False
) -> dict[str, Any]:
    sender, recipient = (page_id, psid) if echo else (psid, page_id)
    message: dict[str, Any] = {"mid": mid, "text": text} | ({"is_echo": True} if echo else {})
    return {
        "object": "page",
        "entry": [
            {
                "id": page_id,
                "time": timestamp_ms,
                "messaging": [
                    {
                        "sender": {"id": sender},
                        "recipient": {"id": recipient},
                        "timestamp": timestamp_ms,
                        "message": message,
                    }
                ],
            }
        ],
    }
