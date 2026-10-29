"""Phase 2 end to end with the mock model: comment, private reply, DM, qualified, payment link, paid, won."""

import re
from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select

from app.models import Business, DealStageChange, Engagement
from tests import meta_payloads as meta
from tests.conftest import (
    IG_ACCOUNT_ID,
    OWNER_AUTH,
    _build_app,
    create_post,
    create_product,
    deliver,
    make_settings,
)

SHOP_NOTES = "We ship nationwide in 3-5 business days. Returns within 14 days."


@pytest.fixture
async def agent_app() -> AsyncIterator[FastAPI]:
    async for built in _build_app(make_settings(agent_enabled=True)):
        yield built


@pytest.fixture
async def shop(agent_app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with agent_app.state.sessionmaker() as session:
        session.add(
            Business(
                name="Bloom & Thread", currency="USD", ig_account_id=IG_ACCOUNT_ID, sales_notes=SHOP_NOTES
            )
        )
        await session.commit()
    transport = httpx.ASGITransport(app=agent_app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver", auth=OWNER_AUTH
    ) as client:
        yield client


async def _dress_post(client: httpx.AsyncClient) -> tuple[dict, dict]:
    dress = await create_product(
        client, name="Linen wrap dress", price_minor=6800, attributes={"color": "sage", "sizes": "XS-XL"}
    )
    post = await create_post(
        client, external_id="18000000000000101", product_id=dress["id"], caption="Back in sage!"
    )
    return dress, post


async def _say(client: httpx.AsyncClient, text: str, username: str = "maya.shops") -> dict:
    response = await client.post("/api/simulator/instagram/dm", json={"username": username, "text": text})
    assert response.status_code == 200, response.text
    return response.json()


async def _deal(client: httpx.AsyncClient) -> dict:
    [deal] = (await client.get("/api/deals")).json()
    return deal


async def test_comment_to_won(agent_app: FastAPI, shop: httpx.AsyncClient) -> None:
    dress, post = await _dress_post(shop)

    commented = await shop.post(
        "/api/simulator/instagram/comment",
        json={"post_id": post["id"], "username": "maya.shops", "text": "price?"},
    )
    [run] = commented.json()["agent_runs"]
    assert run["status"] == "replied"
    assert run["model"] == "mock-sales-brain"
    assert "$68.00" in run["reply_text"]
    assert [s["name"] for s in run["steps"] if s["type"] == "tool"] == ["get_product"]
    conversation_id = commented.json()["conversation_id"]
    assert conversation_id is not None  # the private reply opened the DM thread
    async with agent_app.state.sessionmaker() as session:
        engagement = await session.scalar(select(Engagement))
        assert engagement is not None and engagement.private_reply_at is not None

    sized = await _say(shop, "Size M please")
    assert sized["agent_runs"][0]["status"] == "replied"
    deal = await _deal(shop)
    assert (deal["stage"], deal["details"]) == ("qualified", {"size": "M"})

    linked = await _say(shop, "Yes, send me the link!")
    reply = linked["agent_runs"][0]["reply_text"]
    url = re.search(r"http://testserver/pay/[\w-]+", reply)
    assert url, reply
    deal = await _deal(shop)
    assert (deal["stage"], deal["amount_minor"], deal["product_id"]) == ("payment_sent", 6800, dress["id"])

    shopper_browser = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=agent_app), base_url="http://testserver"
    )
    pay_path = url.group(0).removeprefix("http://testserver")
    page = await shopper_browser.get(pay_path)  # no owner login: the link alone opens checkout
    assert page.status_code == 200
    assert "Linen wrap dress" in page.text and "$68.00" in page.text
    for _ in range(2):  # paying twice changes nothing the second time
        paid = await shopper_browser.post(pay_path)
        assert "Payment received" in paid.text

    assert (await _deal(shop))["stage"] == "won"
    thread = (await shop.get(f"/api/conversations/{conversation_id}")).json()
    texts = [m["text"] for m in thread["messages"] if m["direction"] == "outbound"]
    assert texts[-1].startswith("Payment received")
    assert sum(t.startswith("Payment received") for t in texts) == 1
    async with agent_app.state.sessionmaker() as session:
        changes = (await session.scalars(select(DealStageChange).order_by(DealStageChange.id))).all()
    assert [(c.to_stage.value, c.actor.value) for c in changes] == [
        ("new", "system"),
        ("engaged", "system"),
        ("qualified", "agent"),
        ("payment_sent", "agent"),
        ("won", "system"),
    ]


async def test_shipping_question_is_answered_from_shop_notes_only(shop: httpx.AsyncClient) -> None:
    _, post = await _dress_post(shop)
    await shop.post(
        "/api/simulator/instagram/comment",
        json={"post_id": post["id"], "username": "maya.shops", "text": "hi"},
    )
    asked = await _say(shop, "Do you ship to Austin?")
    assert "We ship nationwide in 3-5 business days." in asked["agent_runs"][0]["reply_text"]


async def test_refund_request_hands_off_and_the_agent_stays_paused_until_resumed(
    shop: httpx.AsyncClient,
) -> None:
    await _dress_post(shop)
    first = await _say(shop, "My order arrived damaged, I want a refund")
    [run] = first["agent_runs"]
    assert run["status"] == "handed_off"
    assert "owner" in run["reply_text"]
    conversation_id = first["conversation_id"]
    [conversation] = (await shop.get("/api/conversations")).json()
    assert conversation["agent_paused"] is True
    assert "refund" in conversation["paused_reason"]

    assert (await _say(shop, "hello?"))["agent_runs"] == []  # paused: the owner is handling it

    resumed = await shop.patch(f"/api/conversations/{conversation_id}", json={"agent_paused": False})
    assert resumed.json()["agent_paused"] is False
    assert resumed.json()["paused_reason"] is None
    assert (await _say(shop, "what do you sell?"))["agent_runs"][0]["status"] == "replied"


async def test_owner_reply_in_instagram_keeps_the_agent_quiet(shop: httpx.AsyncClient) -> None:
    shopper = "9100000000000042"
    dm = meta.direct_message(IG_ACCOUNT_ID, mid="mid.q", sender_id=shopper, text="is the dress in stock?")
    echo = meta.echo_message(
        IG_ACCOUNT_ID, mid="mid.owner", recipient_id=shopper, text="Yes! Sending details"
    )
    await deliver(shop, {"object": "instagram", "entry": [*dm["entry"], *echo["entry"]]})
    [conversation] = (await shop.get("/api/conversations")).json()
    runs = (await shop.get(f"/api/conversations/{conversation['id']}/agent-runs")).json()
    assert runs == []


async def test_agent_status_and_run_log(shop: httpx.AsyncClient) -> None:
    status = (await shop.get("/api/agent")).json()
    assert status == {
        "enabled": True,
        "model": "mock-sales-brain",
        "is_mock": True,
        "instagram_sending": "recorded",
        "payments": "test_checkout",
    }
    await _dress_post(shop)
    sent = await _say(shop, "what do you have?")
    runs = (await shop.get(f"/api/conversations/{sent['conversation_id']}/agent-runs")).json()
    assert [r["trigger"] for r in runs] == ["dm"]
    assert runs[0]["steps"][0]["tool_calls"][0]["name"] == "search_catalog"
    thread = (await shop.get(f"/api/conversations/{sent['conversation_id']}")).json()
    agent_message = next(m for m in thread["messages"] if m["author"] == "agent")
    assert agent_message["agent_run_id"] == runs[0]["id"]


# --- the mock's demo conversations (regressions from review) --------------------------------------


async def _comment(client: httpx.AsyncClient, post_id: int, text: str, username: str = "maya.shops") -> dict:
    response = await client.post(
        "/api/simulator/instagram/comment", json={"post_id": post_id, "username": username, "text": text}
    )
    assert response.status_code == 200, response.text
    return response.json()


def _reply(result: dict) -> str:
    [run] = result["agent_runs"]
    return run["reply_text"] or ""


@pytest.mark.parametrize(
    ("message", "expect_link"),
    [
        ("Ok, what colours does it come in?", False),
        ("Is it okay to machine wash?", False),
        ("I'll take a medium", True),
    ],
)
async def test_only_a_clear_yes_gets_a_checkout_link(
    shop: httpx.AsyncClient, message: str, expect_link: bool
) -> None:
    _, post = await _dress_post(shop)
    await _comment(shop, post["id"], "price?")
    reply = _reply(await _say(shop, message))
    assert ("/pay/" in reply) is expect_link, reply


async def test_ill_take_a_medium_records_the_size_and_sends_the_link(shop: httpx.AsyncClient) -> None:
    _, post = await _dress_post(shop)
    await _comment(shop, post["id"], "price?")
    await _say(shop, "I'll take a medium")
    deal = await _deal(shop)
    assert (deal["stage"], deal["details"]) == ("payment_sent", {"size": "M"})


async def test_declining_closes_the_deal(shop: httpx.AsyncClient) -> None:
    _, post = await _dress_post(shop)
    await _comment(shop, post["id"], "price?")
    reply = _reply(await _say(shop, "Hmm I don't want it anymore, sorry"))
    assert "/pay/" not in reply
    assert (await _deal(shop))["stage"] == "lost"


async def test_quantity_words_are_understood(shop: httpx.AsyncClient) -> None:
    _, post = await _dress_post(shop)
    await _comment(shop, post["id"], "price?")
    reply = _reply(await _say(shop, "I want two please"))
    assert "x2 ($136.00)" in reply


async def test_a_shopper_who_starts_in_dms_can_buy(shop: httpx.AsyncClient) -> None:
    await _dress_post(shop)
    await create_product(shop, name="Silver leaf earrings", price_minor=2400)
    first = _reply(await _say(shop, "Hi! Do you have linen dresses?"))
    assert "Linen wrap dress" in first
    assert not first.startswith("Hi Instagram")
    assert "Silver leaf earrings" in _reply(await _say(shop, "do you sell earrings?"))
    bought = _reply(await _say(shop, "The linen wrap dress please, I'll take it"))
    assert "/pay/" in bought and "Linen wrap dress" in bought
    assert _reply(await _say(shop, "Thank you so much!")).startswith("You're welcome")


async def test_a_comment_on_a_post_without_a_product_searches_the_catalog(shop: httpx.AsyncClient) -> None:
    await create_product(shop, name="Hand-painted canvas tote", price_minor=3200)
    studio = await create_post(shop, external_id="18000000000000199", caption="Studio tour!")
    assert "Hand-painted canvas tote" in _reply(await _comment(shop, studio["id"], "how much is the tote?"))


async def test_details_go_to_the_product_the_shopper_names(shop: httpx.AsyncClient) -> None:
    dress, dress_post = await _dress_post(shop)
    tote = await create_product(shop, name="Hand-painted canvas tote", price_minor=3200)
    tote_post = await create_post(shop, external_id="18000000000000102", product_id=tote["id"])
    await _comment(shop, dress_post["id"], "price?")
    second = await _comment(shop, tote_post["id"], "cute!")
    assert second["agent_runs"], "a second comment right after our reply must still be answered"
    await _say(shop, "Size M for the dress please")
    deals = {d["product_id"]: d for d in (await shop.get("/api/deals")).json()}
    assert (deals[dress["id"]]["stage"], deals[dress["id"]]["details"]) == ("qualified", {"size": "M"})
    assert deals[tote["id"]]["details"] == {}
