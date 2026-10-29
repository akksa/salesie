"""What the owner API returns: ordering, filters, and isolation from other businesses."""

import httpx
from fastapi import FastAPI

from app.models import Business, Channel, Post, Product
from tests import meta_payloads as meta
from tests.conftest import IG_ACCOUNT_ID, create_post, create_product, deliver

OTHER_ACCOUNT = "17841499999999999"


async def test_threads_are_oldest_first_and_previews_show_the_newest(
    client: httpx.AsyncClient, business_id: int
) -> None:
    for n, ms in enumerate([1_730_000_300_000, 1_730_000_100_000, 1_730_000_200_000]):
        dm = meta.direct_message(
            IG_ACCOUNT_ID, mid=f"mid.{n}", sender_id="91", text=f"t{ms}", timestamp_ms=ms
        )
        await deliver(client, dm)
    [conversation] = (await client.get("/api/conversations")).json()
    assert conversation["last_message"]["text"] == "t1730000300000"
    thread = (await client.get(f"/api/conversations/{conversation['id']}")).json()
    assert [m["text"] for m in thread["messages"]] == ["t1730000100000", "t1730000200000", "t1730000300000"]


async def test_engagements_are_newest_first(client: httpx.AsyncClient, business_id: int) -> None:
    for n, time in enumerate([1_730_000_000, 1_730_000_900, 1_730_000_500]):
        comment = meta.comment_via_changes(
            IG_ACCOUNT_ID,
            comment_id=f"c{n}",
            media_id="m",
            from_id="91",
            username="u",
            text=str(time),
            time=time,
        )
        await deliver(client, comment)
    [contact] = (await client.get("/api/contacts")).json()
    detail = (await client.get(f"/api/contacts/{contact['id']}")).json()
    assert [e["text"] for e in detail["engagements"]] == ["1730000900", "1730000500", "1730000000"]


async def test_webhook_events_are_newest_first_and_filterable(
    client: httpx.AsyncClient, business_id: int
) -> None:
    await deliver(client, meta.direct_message(IG_ACCOUNT_ID, mid="ok1", sender_id="91", text="a"))
    await deliver(client, meta.direct_message(OTHER_ACCOUNT, mid="bad", sender_id="91", text="b"))
    await deliver(client, meta.direct_message(IG_ACCOUNT_ID, mid="ok2", sender_id="91", text="c"))
    events = (await client.get("/api/webhook-events")).json()
    assert [e["status"] for e in events] == ["processed", "failed", "processed"]
    assert events[0]["id"] > events[1]["id"] > events[2]["id"]
    failed = (await client.get("/api/webhook-events", params={"status": "failed"})).json()
    assert [e["id"] for e in failed] == [events[1]["id"]]
    assert (await client.get("/api/webhook-events", params={"limit": 1})).json()[0]["id"] == events[0]["id"]


async def test_another_businesss_data_never_shows_up(
    app: FastAPI, client: httpx.AsyncClient, business_id: int
) -> None:
    async with app.state.sessionmaker() as session:
        other = Business(name="Other shop", currency="EUR", ig_account_id=OTHER_ACCOUNT)
        session.add(other)
        await session.flush()
        product = Product(business_id=other.id, name="Their product")
        session.add(product)
        await session.flush()
        session.add(
            Post(business_id=other.id, channel=Channel.INSTAGRAM, external_id="1899", product_id=product.id)
        )
        await session.commit()
        foreign_product_id = product.id
    await deliver(client, meta.direct_message(OTHER_ACCOUNT, mid="theirs", sender_id="91", text="for them"))
    their_comment = meta.comment_via_changes(
        OTHER_ACCOUNT, comment_id="cx", media_id="1899", from_id="91", username="u", text="x"
    )
    await deliver(client, their_comment)

    mine = await create_product(client, name="Mine")
    await create_post(client, external_id="1700", product_id=mine["id"])
    assert [p["name"] for p in (await client.get("/api/products")).json()] == ["Mine"]
    assert [p["external_id"] for p in (await client.get("/api/posts")).json()] == ["1700"]
    assert (await client.get("/api/contacts")).json() == []
    assert (await client.get("/api/conversations")).json() == []
    assert (await client.get("/api/deals")).json() == []
    assert (await client.patch(f"/api/products/{foreign_product_id}", json={"name": "x"})).status_code == 404
    assert (
        await client.post("/api/posts", json={"external_id": "1701", "product_id": foreign_product_id})
    ).status_code == 404
