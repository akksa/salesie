"""Regression tests for failure modes found in adversarial review of Phase 1 ingestion."""

import asyncio
from collections.abc import AsyncIterator

import httpx
from fastapi import FastAPI
from sqlalchemy import update

from app.models import Deal, DealStage
from tests import meta_payloads as meta
from tests.conftest import IG_ACCOUNT_ID, create_post, create_product, deliver

SHOPPER = "9100000000000042"
MEDIA_ID = "18000000000000001"


def _comment(
    comment_id: str, *, media_id: str = MEDIA_ID, username: str = "maya.shops", time: int = 1_730_000_000
):
    return meta.comment_via_changes(
        IG_ACCOUNT_ID,
        comment_id=comment_id,
        media_id=media_id,
        from_id=SHOPPER,
        username=username,
        text="hi",
        time=time,
    )


async def _contact(client: httpx.AsyncClient) -> dict:
    [contact] = (await client.get("/api/contacts")).json()
    return (await client.get(f"/api/contacts/{contact['id']}")).json()


async def _open_deals(client: httpx.AsyncClient) -> list[dict]:
    return [d for d in (await client.get("/api/deals")).json() if d["stage"] not in ("won", "lost")]


# --- one bad item must not sink the delivery ---------------------------------------


async def test_valid_events_survive_a_bad_sibling_in_the_same_delivery(
    client: httpx.AsyncClient, business_id: int
) -> None:
    good = meta.direct_message(IG_ACCOUNT_ID, mid="mid.good", sender_id=SHOPPER, text="hi")
    foreign = meta.direct_message("17849999999999999", mid="mid.foreign", sender_id=SHOPPER, text="hi")
    broken = {"id": IG_ACCOUNT_ID, "messaging": [{"sender": {"id": SHOPPER}, "message": {"text": "no mid"}}]}
    payload = {"object": "instagram", "entry": [*good["entry"], *foreign["entry"], broken]}
    assert (await deliver(client, payload)).status_code == 200

    contact = await _contact(client)
    [conversation] = contact["conversations"]
    assert conversation["last_message"]["text"] == "hi"
    [event] = (await client.get("/api/webhook-events")).json()
    assert event["status"] == "failed"
    assert event["error"].startswith("2 of 3 item(s) failed")


async def test_failed_delivery_can_be_replayed_after_fixing_the_account_id(
    client: httpx.AsyncClient, business_id: int
) -> None:
    payload = meta.direct_message("178414000000099", mid="mid.early", sender_id=SHOPPER, text="hello?")
    await deliver(client, payload)
    [event] = (await client.get("/api/webhook-events")).json()
    assert event["status"] == "failed"

    await client.patch("/api/business", json={"ig_account_id": "178414000000099"})
    replayed = (await client.post(f"/api/webhook-events/{event['id']}/replay")).json()
    assert replayed["status"] == "processed"
    assert replayed["error"] is None
    await client.post(f"/api/webhook-events/{event['id']}/replay")  # replaying twice is harmless
    contact = await _contact(client)
    [conversation] = contact["conversations"]
    thread = (await client.get(f"/api/conversations/{conversation['id']}")).json()
    assert len(thread["messages"]) == 1
    assert (await client.post("/api/webhook-events/999999/replay")).status_code == 404


async def test_opposite_order_batches_for_two_contacts_do_not_deadlock(
    client: httpx.AsyncClient, business_id: int
) -> None:
    def batch(round_: int, order: list[str]) -> dict:
        entries = [
            meta.direct_message(IG_ACCOUNT_ID, mid=f"mid.{round_}.{sender}", sender_id=sender, text="x")[
                "entry"
            ][0]
            for sender in order
        ]
        return {"object": "instagram", "entry": entries}

    a, b = "9100000000000001", "9100000000000002"
    for sender in (a, b):  # contacts exist before the race
        await deliver(
            client, meta.direct_message(IG_ACCOUNT_ID, mid=f"mid.seed.{sender}", sender_id=sender, text="x")
        )
    payloads = [batch(n, [a, b] if n % 2 else [b, a]) for n in range(20)]
    responses = await asyncio.gather(*(deliver(client, p) for p in payloads))
    assert all(r.status_code == 200 for r in responses)
    events = (await client.get("/api/webhook-events", params={"limit": 50})).json()
    assert {e["status"] for e in events} == {"processed"}


# --- text Postgres can't store ------------------------------------------------------


async def test_nul_and_lone_surrogate_text_is_cleaned_not_fatal(
    client: httpx.AsyncClient, business_id: int
) -> None:
    body = (
        b'{"object":"instagram","entry":[{"id":"'
        + IG_ACCOUNT_ID.encode()
        + (
            b'","time":1730000000000,"messaging":[{"sender":{"id":"' + SHOPPER.encode() + b'"},'
            b'"recipient":{"id":"1"},"timestamp":1730000000000,'
            b'"message":{"mid":"mid.nul","text":"hi\\u0000there \\ud83d"}}]}]}'
        )
    )
    from tests.conftest import meta_signature

    response = await client.post(
        "/webhooks/meta", content=body, headers={"X-Hub-Signature-256": meta_signature(body)}
    )
    assert response.status_code == 200, response.text
    [conversation] = (await client.get("/api/conversations")).json()
    assert conversation["last_message"]["text"] == "hithere ?"


async def test_owner_input_with_nul_is_cleaned(client: httpx.AsyncClient, business_id: int) -> None:
    product = await create_product(client, description="soft\u0000 linen", attributes={"k\u0000": "v\u0000"})
    assert product["description"] == "soft linen"
    assert product["attributes"] == {"k": "v"}


# --- one open deal per product ------------------------------------------------------


async def test_dm_then_comment_attaches_product_to_the_existing_deal(
    client: httpx.AsyncClient, business_id: int
) -> None:
    product = await create_product(client, price_minor=4900)
    await create_post(client, external_id=MEDIA_ID, product_id=product["id"])
    await deliver(client, meta.direct_message(IG_ACCOUNT_ID, mid="mid.1", sender_id=SHOPPER, text="hi"))
    await deliver(client, _comment("c1"))
    await deliver(client, meta.direct_message(IG_ACCOUNT_ID, mid="mid.2", sender_id=SHOPPER, text="price?"))

    [deal] = await _open_deals(client)
    assert deal["product_id"] == product["id"]
    assert deal["amount_minor"] == 4900
    assert deal["stage"] == "engaged"


async def test_linking_a_stub_post_later_does_not_duplicate_the_deal(
    client: httpx.AsyncClient, business_id: int
) -> None:
    await deliver(client, _comment("c1", media_id="18999999999999999"))
    [post] = (await client.get("/api/posts")).json()
    product = await create_product(client)
    await client.patch(f"/api/posts/{post['id']}", json={"product_id": product["id"]})
    await deliver(client, _comment("c2", media_id="18999999999999999"))

    [deal] = await _open_deals(client)
    assert deal["product_id"] == product["id"]
    assert deal["source_post_id"] == post["id"]


async def test_thanks_after_a_won_deal_does_not_open_a_new_deal(
    app: FastAPI, client: httpx.AsyncClient, business_id: int
) -> None:
    await deliver(
        client, meta.direct_message(IG_ACCOUNT_ID, mid="mid.1", sender_id=SHOPPER, text="I'll take it")
    )
    async with app.state.sessionmaker() as session:
        await session.execute(update(Deal).values(stage=DealStage.WON))
        await session.commit()
    await deliver(
        client, meta.direct_message(IG_ACCOUNT_ID, mid="mid.2", sender_id=SHOPPER, text="thanks, got it!")
    )

    deals = (await client.get("/api/deals")).json()
    assert [d["stage"] for d in deals] == ["won"]


# --- ordering, renames, limits -------------------------------------------------------


async def test_newest_contacts_are_listed_first_beyond_the_page_limit(
    client: httpx.AsyncClient, business_id: int
) -> None:
    base_ms = 1_730_000_000_000
    entries = [
        meta.direct_message(
            IG_ACCOUNT_ID,
            mid=f"mid.bulk.{n}",
            sender_id=f"92000000000{n:05d}",
            text="x",
            timestamp_ms=base_ms + n * 1000,
        )["entry"][0]
        for n in range(205)
    ]
    await deliver(client, {"object": "instagram", "entry": entries})

    contacts = (await client.get("/api/contacts")).json()
    assert len(contacts) == 200
    assert contacts[0]["identities"][0]["external_id"] == "9200000000000204"
    conversations = (await client.get("/api/conversations")).json()
    assert conversations[0]["last_message"]["sent_at"] > conversations[-1]["last_message"]["sent_at"]
    assert len(conversations) == 200


async def test_redelivered_old_comment_does_not_revert_a_rename(
    client: httpx.AsyncClient, business_id: int
) -> None:
    await deliver(client, _comment("c1", username="maya.shops", time=1_730_000_000))
    await deliver(client, _comment("c2", username="maya.studio", time=1_730_100_000))
    await deliver(client, _comment("c1", username="maya.shops", time=1_730_200_000))  # redelivered later
    await deliver(client, _comment("c0", username="maya.ancient", time=1_729_000_000))  # late, older event

    contact = await _contact(client)
    assert contact["display_name"] == "@maya.studio"


async def _chunks() -> AsyncIterator[bytes]:
    for _ in range(11):
        yield b"x" * 100_000


async def test_chunked_oversized_body_is_cut_off(client: httpx.AsyncClient) -> None:
    response = await client.post("/webhooks/meta", content=_chunks())
    assert response.status_code == 413


async def test_out_of_range_ids_and_amounts_are_validation_errors(
    client: httpx.AsyncClient, business_id: int
) -> None:
    huge = 2**40
    assert (await client.get(f"/api/contacts/{huge}")).status_code == 422
    assert (await client.get(f"/api/conversations/{huge}")).status_code == 422
    assert (await client.patch(f"/api/products/{huge}", json={"name": "x"})).status_code == 422
    assert (await client.post("/api/products", json={"name": "x", "price_minor": 2**31})).status_code == 422
    assert (await client.post("/api/posts", json={"external_id": "1", "product_id": 0})).status_code == 422
    assert (await client.post("/api/posts", json={"external_id": "1", "product_id": huge})).status_code == 422
    response = await client.post(
        "/api/simulator/instagram/comment", json={"post_id": huge, "username": "a", "text": "b"}
    )
    assert response.status_code == 422
