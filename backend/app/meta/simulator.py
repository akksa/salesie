"""Fake Meta traffic for demos and tests. Payloads match Meta's documented shapes and are signed with the
app secret, then go through receive_meta_webhook: the same function the real /webhooks/meta route calls."""

import hashlib
import json
import secrets
import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.meta.receiver import Processed, receive_meta_webhook
from app.meta.signature import sign


def simulated_user_id(username: str) -> str:
    """Stable id per username, so one fake shopper's comments and DMs land on one contact. Real Instagram
    ids are numeric, so the "sim_" prefix can never collide with a real person."""
    return "sim_" + hashlib.sha256(username.lower().encode()).hexdigest()[:16]


def comment_payload(account_id: str, media_id: str, username: str, text: str) -> dict[str, Any]:
    return {
        "object": "instagram",
        "entry": [
            {
                "id": account_id,
                "time": int(time.time()),
                "changes": [
                    {
                        "field": "comments",
                        "value": {
                            "from": {"id": simulated_user_id(username), "username": username},
                            "comment_id": f"179{secrets.randbelow(10**14):014d}",
                            "text": text,
                            "media": {"id": media_id, "media_product_type": "FEED"},
                        },
                    }
                ],
            }
        ],
    }


def direct_message_payload(account_id: str, username: str, text: str) -> dict[str, Any]:
    now_ms = int(time.time() * 1000)
    return {
        "object": "instagram",
        "entry": [
            {
                "id": account_id,
                "time": now_ms,
                "messaging": [
                    {
                        "sender": {"id": simulated_user_id(username)},
                        "recipient": {"id": account_id},
                        "timestamp": now_ms,
                        "message": {"mid": f"sim.{secrets.token_hex(16)}", "text": text},
                    }
                ],
            }
        ],
    }


async def deliver_simulated(
    sessionmaker: async_sessionmaker[AsyncSession], payload: dict[str, Any], app_secret: str
) -> Processed:
    body = json.dumps(payload).encode()
    return await receive_meta_webhook(sessionmaker, body, sign(body, app_secret), app_secret, simulated=True)
