"""The simulator drives the same pipeline as real Meta traffic, so judges can try it without Instagram."""

from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI

from tests.conftest import OWNER_AUTH, _build_app, create_post, create_product, make_settings


async def test_simulated_comment_creates_lead_through_webhook_pipeline(
    client: httpx.AsyncClient, business_id: int
) -> None:
    product = await create_product(client, name="Hand-painted tote")
    post = await create_post(client, product_id=product["id"])

    response = await client.post(
        "/api/simulator/instagram/comment",
        json={"post_id": post["id"], "username": "sam.buys", "text": "Is this still available?"},
    )
    assert response.status_code == 200, response.text
    event = response.json()
    assert event["status"] == "processed"
    assert event["simulated"] is True
    assert event["conversation_id"] is None  # a comment alone doesn't open a conversation

    [contact] = (await client.get("/api/contacts")).json()
    assert event["contact_id"] == contact["id"]
    assert contact["display_name"] == "@sam.buys"
    assert contact["latest_deal"]["product_name"] == "Hand-painted tote"
    assert contact["latest_deal"]["source_post_id"] == post["id"]


async def test_simulated_dm_from_same_username_joins_the_same_contact(
    client: httpx.AsyncClient, business_id: int
) -> None:
    post = await create_post(client)
    await client.post(
        "/api/simulator/instagram/comment",
        json={"post_id": post["id"], "username": "sam.buys", "text": "price?"},
    )
    response = await client.post(
        "/api/simulator/instagram/dm", json={"username": "sam.buys", "text": "Can I pay by card?"}
    )
    assert response.status_code == 200, response.text

    [contact] = (await client.get("/api/contacts")).json()
    assert contact["latest_deal"]["stage"] == "engaged"
    [conversation] = (await client.get("/api/conversations")).json()
    assert conversation["contact_id"] == contact["id"]


async def test_simulated_dm_reports_the_contact_and_conversation_it_created(
    client: httpx.AsyncClient, business_id: int
) -> None:
    response = await client.post("/api/simulator/instagram/dm", json={"username": "new.face", "text": "hi"})
    assert response.status_code == 200, response.text
    event = response.json()
    [conversation] = (await client.get("/api/conversations")).json()
    assert event["contact_id"] == conversation["contact_id"]
    assert event["conversation_id"] == conversation["id"]


async def test_simulator_rejects_post_from_unknown_id(client: httpx.AsyncClient, business_id: int) -> None:
    response = await client.post(
        "/api/simulator/instagram/comment", json={"post_id": 999, "username": "sam", "text": "hi"}
    )
    assert response.status_code == 404


async def test_simulator_needs_instagram_account_id(client: httpx.AsyncClient, business_id: int) -> None:
    await client.patch("/api/business", json={"ig_account_id": None})
    response = await client.post("/api/simulator/instagram/dm", json={"username": "sam", "text": "hi"})
    assert response.status_code == 409


@pytest.fixture
async def app_without_simulator() -> AsyncIterator[FastAPI]:
    async for built in _build_app(make_settings(simulator_enabled=False)):
        yield built


async def test_simulator_is_hidden_when_disabled(app_without_simulator: FastAPI) -> None:
    transport = httpx.ASGITransport(app=app_without_simulator)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", auth=OWNER_AUTH) as c:
        response = await c.post("/api/simulator/instagram/dm", json={"username": "sam", "text": "hi"})
        assert response.status_code == 404
        assert (await c.get("/api/app-config")).json() == {"simulator_enabled": False}


async def test_each_simulated_shopper_is_a_separate_contact_and_usernames_ignore_case(
    client: httpx.AsyncClient, business_id: int
) -> None:
    post = await create_post(client)
    sends = [
        ("comment", "ana.b", "price?"),
        ("comment", "ana.b", "and in blue?"),
        ("dm", "Ana.B", "hello"),
        ("dm", "ana.b", "still there?"),
        ("comment", "leo.k", "nice"),
    ]
    for kind, username, text in sends:
        body = {"username": username, "text": text} | ({"post_id": post["id"]} if kind == "comment" else {})
        response = await client.post(
            f"/api/simulator/instagram/{'comment' if kind == 'comment' else 'dm'}", json=body
        )
        assert response.json()["status"] == "processed", response.text

    contacts = {c["display_name"]: c for c in (await client.get("/api/contacts")).json()}
    assert set(contacts) == {"@ana.b", "@leo.k"}
    ana = (await client.get(f"/api/contacts/{contacts['@ana.b']['id']}")).json()
    assert len(ana["engagements"]) == 2
    thread = (await client.get(f"/api/conversations/{ana['conversations'][0]['id']}")).json()
    assert [m["text"] for m in thread["messages"]] == ["hello", "still there?"]


async def test_simulator_cannot_comment_on_another_businesss_post(
    app, client: httpx.AsyncClient, business_id: int
) -> None:
    from app.models import Business, Channel, Post

    async with app.state.sessionmaker() as session:
        other = Business(name="Other shop", ig_account_id="17841499999999999")
        session.add(other)
        await session.flush()
        foreign = Post(business_id=other.id, channel=Channel.INSTAGRAM, external_id="1899")
        session.add(foreign)
        await session.commit()
        foreign_id = foreign.id
    response = await client.post(
        "/api/simulator/instagram/comment", json={"post_id": foreign_id, "username": "x", "text": "y"}
    )
    assert response.status_code == 404
