"""Fill the demo shop with realistic activity: `uv run python -m app.demo` (after `app.seed --reset`).

Every shopper goes through the real pipeline (simulated, signed webhooks, the sales agent and the test
checkout), so the pipeline board, inbox and insights show genuine runs, not hand-written rows.
Needs SIMULATOR_ENABLED=true and AGENT_ENABLED=true.
"""

import asyncio
import re

import httpx

from app.config import get_settings
from app.main import create_app

# (shopper, opening move, follow-up DMs, pays?). Openings: ("comment", product name, text) or ("dm", text).
SCRIPT: list[tuple[str, tuple[str, ...], list[str], bool]] = [
    (
        "ana.styles",
        ("comment", "Linen wrap dress", "Price?"),
        ["Size M please", "Yes, send me the link!"],
        True,
    ),
    (
        "ben.makes",
        ("comment", "Hand-painted canvas tote", "Is this still available?"),
        ["I'll take it"],
        True,
    ),
    (
        "cleo.k",
        ("comment", "Silver leaf earrings", "price?"),
        ["Hmm, maybe later, I don't want it anymore"],
        False,
    ),
    ("dev.wears", ("comment", "Linen wrap dress", "how much?"), ["size L"], False),
    ("eli.home", ("dm", "My last order arrived damaged and I want a refund"), [], False),
    ("fay.loves", ("comment", "Linen wrap dress", "😍😍"), [], False),
    ("gus.gifts", ("comment", "Hand-painted canvas tote", "price?"), ["I'll take two"], False),
    ("hana.j", ("comment", "Silver leaf earrings", "Price please"), ["yes please, send the link"], True),
    ("ivy.reads", ("comment", "Linen wrap dress", "Do you ship to Austin?"), [], False),
    ("jon.k", ("comment", "Hand-painted canvas tote", "how much?"), ["What colours does it come in?"], False),
    ("kai.studio", ("comment", "Silver leaf earrings", "price?"), ["silver please"], False),
    ("lia.m", ("comment", "Linen wrap dress", "price"), ["size S", "yes, send the link"], False),
    ("mo.shop", ("dm", "Hi! Do you have totes?"), ["I'll take it"], True),
    (
        "nia.p",
        ("comment", "Hand-painted canvas tote", "price?"),
        ["Too pricey for me, not interested"],
        False,
    ),
]


async def play() -> list[str]:
    settings = get_settings()
    if not (settings.simulator_enabled and settings.agent_enabled):
        raise SystemExit("Set SIMULATOR_ENABLED=true and AGENT_ENABLED=true to generate demo activity")
    app = create_app(settings)
    auth = (settings.owner_username, settings.owner_password.get_secret_value())
    transport = httpx.ASGITransport(app=app)
    log: list[str] = []
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://demo", auth=auth) as owner:
            posts = {p["product_name"]: p["id"] for p in (await owner.get("/api/posts")).json()}
            for username, opening, follow_ups, pays in SCRIPT:
                replies = [await _open(owner, posts, username, opening)]
                for text in follow_ups:
                    replies.append(
                        await _say(owner, "/api/simulator/instagram/dm", {"username": username, "text": text})
                    )
                if pays and (link := _payment_path(replies[-1])):
                    async with httpx.AsyncClient(transport=transport, base_url="http://demo") as shopper:
                        await shopper.post(link)
                log.append(f"{username}: {replies[-1][:80]!r}{' (paid)' if pays else ''}")
    finally:
        await app.state.engine.dispose()
    return log


async def _open(
    owner: httpx.AsyncClient, posts: dict[str, int], username: str, opening: tuple[str, ...]
) -> str:
    if opening[0] == "comment":
        _, product, text = opening
        body = {"post_id": posts[product], "username": username, "text": text}
        return await _say(owner, "/api/simulator/instagram/comment", body)
    return await _say(owner, "/api/simulator/instagram/dm", {"username": username, "text": opening[1]})


async def _say(owner: httpx.AsyncClient, path: str, body: dict[str, object]) -> str:
    response = await owner.post(path, json=body)
    response.raise_for_status()
    runs = response.json()["agent_runs"]
    return (runs[-1]["reply_text"] or "") if runs else ""


def _payment_path(reply: str) -> str | None:
    match = re.search(r"/pay/[A-Za-z0-9_-]+", reply)
    return match.group(0) if match else None


if __name__ == "__main__":
    for line in asyncio.run(play()):
        print(line)
