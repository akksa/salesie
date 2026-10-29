"""The real Meta webhook path: signed HTTP POST -> stored event -> CRM records visible in the owner API."""

import asyncio
import json

import httpx
import pytest

from tests import meta_payloads as meta
from tests.conftest import (
    IG_ACCOUNT_ID,
    VERIFY_TOKEN,
    create_post,
    create_product,
    deliver,
    meta_signature,
)

SHOPPER_ID = "9100000000000042"


def _redelivered(payload: dict, n: int) -> dict:
    """Meta resends the same event inside a new batch: same ids, different envelope time."""
    copy = json.loads(json.dumps(payload))
    copy["entry"][0]["time"] += n
    return copy


MEDIA_ID = "18000000000000001"


async def _contacts(client: httpx.AsyncClient) -> list[dict]:
    response = await client.get("/api/contacts")
    assert response.status_code == 200, response.text
    return response.json()


async def _events(client: httpx.AsyncClient) -> list[dict]:
    response = await client.get("/api/webhook-events")
    assert response.status_code == 200, response.text
    return response.json()


# --- handshake & signature ----------------------------------------------------


async def test_verification_handshake_echoes_challenge(anon_client: httpx.AsyncClient) -> None:
    params = {"hub.mode": "subscribe", "hub.verify_token": VERIFY_TOKEN, "hub.challenge": "1158201444"}
    response = await anon_client.get("/webhooks/meta", params=params)
    assert response.status_code == 200
    assert response.text == "1158201444"


@pytest.mark.parametrize(("mode", "token"), [("subscribe", "guess"), ("unsubscribe", VERIFY_TOKEN)])
async def test_verification_rejects_wrong_token_or_mode(
    anon_client: httpx.AsyncClient, mode: str, token: str
) -> None:
    params = {"hub.mode": mode, "hub.verify_token": token, "hub.challenge": "1"}
    response = await anon_client.get("/webhooks/meta", params=params)
    assert response.status_code == 403


@pytest.mark.parametrize(
    "header",
    [
        "sha256=" + "0" * 64,
        "sha1=0000000000000000000000000000000000000000",
        "",
        "sha256=",
    ],
)
async def test_forged_signature_is_rejected_and_not_stored(
    client: httpx.AsyncClient, business_id: int, header: str
) -> None:
    body = json.dumps(meta.direct_message(IG_ACCOUNT_ID, mid="m1", sender_id=SHOPPER_ID, text="hi")).encode()
    response = await client.post("/webhooks/meta", content=body, headers={"X-Hub-Signature-256": header})
    assert response.status_code == 401
    wrong_key = await deliver(client, json.loads(body), secret="not-the-app-secret")
    assert wrong_key.status_code == 401
    assert await _events(client) == []
    assert await _contacts(client) == []


async def test_missing_signature_is_rejected(client: httpx.AsyncClient) -> None:
    response = await client.post("/webhooks/meta", content=b"{}")
    assert response.status_code == 401


async def test_signed_non_json_body_is_rejected(client: httpx.AsyncClient) -> None:
    for body in (b"not json", b"[]", b'"just a string"'):
        response = await client.post(
            "/webhooks/meta", content=body, headers={"X-Hub-Signature-256": meta_signature(body)}
        )
        assert response.status_code == 400, body


# --- comments -> leads ----------------------------------------------------------


@pytest.mark.parametrize("build", [meta.comment_via_changes, meta.comment_via_entry_field])
async def test_comment_creates_contact_linked_to_post_and_product(
    client: httpx.AsyncClient, business_id: int, build
) -> None:
    product = await create_product(client, name="Linen summer dress", price_minor=4900)
    post = await create_post(client, external_id=MEDIA_ID, product_id=product["id"])

    payload = build(
        IG_ACCOUNT_ID,
        comment_id="17900000000000001",
        media_id=MEDIA_ID,
        from_id=SHOPPER_ID,
        username="maya.shops",
        text="How much is this? 😍",
    )
    response = await deliver(client, payload)
    assert response.status_code == 200, response.text

    [contact] = await _contacts(client)
    assert contact["display_name"] == "@maya.shops"
    assert contact["identities"] == [
        {"channel": "instagram", "external_id": SHOPPER_ID, "username": "maya.shops"}
    ]
    deal = contact["latest_deal"]
    assert deal["stage"] == "new"
    assert deal["product_id"] == product["id"]
    assert deal["product_name"] == "Linen summer dress"
    assert deal["source_post_id"] == post["id"]
    assert deal["amount_minor"] == 4900

    detail = (await client.get(f"/api/contacts/{contact['id']}")).json()
    [engagement] = detail["engagements"]
    assert engagement["text"] == "How much is this? 😍"
    assert engagement["post_id"] == post["id"]

    [event] = await _events(client)
    assert event["status"] == "processed"
    assert event["simulated"] is False


async def test_duplicate_delivery_is_idempotent(client: httpx.AsyncClient, business_id: int) -> None:
    payload = meta.comment_via_changes(
        IG_ACCOUNT_ID,
        comment_id="17900000000000002",
        media_id=MEDIA_ID,
        from_id=SHOPPER_ID,
        username="maya.shops",
        text="price?",
    )
    for n in range(3):
        assert (await deliver(client, _redelivered(payload, n))).status_code == 200

    [contact] = await _contacts(client)
    detail = (await client.get(f"/api/contacts/{contact['id']}")).json()
    assert len(detail["engagements"]) == 1
    assert len(detail["deals"]) == 1
    assert {e["status"] for e in await _events(client)} == {"processed"}  # dupes are no-ops, not errors


async def test_duplicate_inbound_dm_is_stored_once(client: httpx.AsyncClient, business_id: int) -> None:
    dm = meta.direct_message(IG_ACCOUNT_ID, mid="mid.$dup", sender_id=SHOPPER_ID, text="hello")
    for n in range(2):
        assert (await deliver(client, _redelivered(dm, n))).status_code == 200
    [conversation] = (await client.get("/api/conversations")).json()
    thread = (await client.get(f"/api/conversations/{conversation['id']}")).json()
    assert len(thread["messages"]) == 1
    assert {e["status"] for e in await _events(client)} == {"processed"}


async def test_comment_on_unregistered_media_creates_stub_post_and_lead(
    client: httpx.AsyncClient, business_id: int
) -> None:
    payload = meta.comment_via_changes(
        IG_ACCOUNT_ID,
        comment_id="17900000000000003",
        media_id="18999999999999999",
        from_id=SHOPPER_ID,
        username="maya.shops",
        text="is this available?",
    )
    assert (await deliver(client, payload)).status_code == 200

    [post] = (await client.get("/api/posts")).json()
    assert post["external_id"] == "18999999999999999"
    assert post["product_id"] is None
    assert post["engagement_count"] == 1
    [contact] = await _contacts(client)
    assert contact["latest_deal"]["product_id"] is None
    assert contact["latest_deal"]["source_post_id"] == post["id"]


async def test_business_replying_in_its_own_comments_is_not_a_lead(
    client: httpx.AsyncClient, business_id: int
) -> None:
    payload = meta.comment_via_changes(
        IG_ACCOUNT_ID,
        comment_id="17900000000000004",
        media_id=MEDIA_ID,
        from_id=IG_ACCOUNT_ID,
        username="bloomandthread",
        text="Thanks! Check your DMs",
    )
    assert (await deliver(client, payload)).status_code == 200
    assert await _contacts(client) == []


async def test_second_comment_on_same_product_does_not_open_second_deal(
    client: httpx.AsyncClient, business_id: int
) -> None:
    product = await create_product(client)
    await create_post(client, external_id=MEDIA_ID, product_id=product["id"])
    for n, text in enumerate(["price?", "also in blue?"]):
        payload = meta.comment_via_changes(
            IG_ACCOUNT_ID,
            comment_id=f"1790000000000010{n}",
            media_id=MEDIA_ID,
            from_id=SHOPPER_ID,
            username="maya.shops",
            text=text,
        )
        assert (await deliver(client, payload)).status_code == 200

    [contact] = await _contacts(client)
    detail = (await client.get(f"/api/contacts/{contact['id']}")).json()
    assert len(detail["engagements"]) == 2
    assert len(detail["deals"]) == 1


# --- direct messages -------------------------------------------------------------


async def test_dm_after_comment_reuses_contact_and_advances_deal(
    client: httpx.AsyncClient, business_id: int
) -> None:
    product = await create_product(client)
    await create_post(client, external_id=MEDIA_ID, product_id=product["id"])
    comment = meta.comment_via_changes(
        IG_ACCOUNT_ID,
        comment_id="17900000000000005",
        media_id=MEDIA_ID,
        from_id=SHOPPER_ID,
        username="maya.shops",
        text="price?",
    )
    dm = meta.direct_message(
        IG_ACCOUNT_ID, mid="mid.$abc1", sender_id=SHOPPER_ID, text="Do you ship to Austin?"
    )
    assert (await deliver(client, comment)).status_code == 200
    assert (await deliver(client, dm)).status_code == 200

    [contact] = await _contacts(client)
    assert contact["latest_deal"]["stage"] == "engaged"
    assert contact["latest_deal"]["product_id"] == product["id"]

    [conversation] = (await client.get("/api/conversations")).json()
    assert conversation["contact_id"] == contact["id"]
    assert conversation["last_message"]["text"] == "Do you ship to Austin?"
    assert conversation["last_inbound_at"] is not None
    thread = (await client.get(f"/api/conversations/{conversation['id']}")).json()
    assert [(m["direction"], m["author"]) for m in thread["messages"]] == [("inbound", "contact")]


async def test_dm_without_prior_comment_opens_engaged_deal(
    client: httpx.AsyncClient, business_id: int
) -> None:
    dm = meta.direct_message(IG_ACCOUNT_ID, mid="mid.$abc2", sender_id=SHOPPER_ID, text="hello!")
    assert (await deliver(client, dm)).status_code == 200

    [deal] = (await client.get("/api/deals")).json()
    assert deal["stage"] == "engaged"
    assert deal["product_id"] is None
    assert deal["contact_name"] == "Instagram user …0042"


async def test_echo_is_recorded_as_owner_message(client: httpx.AsyncClient, business_id: int) -> None:
    inbound = meta.direct_message(IG_ACCOUNT_ID, mid="mid.$in", sender_id=SHOPPER_ID, text="hi")
    echo = meta.echo_message(
        IG_ACCOUNT_ID, mid="mid.$out", recipient_id=SHOPPER_ID, text="Hi! How can I help?"
    )
    assert (await deliver(client, inbound)).status_code == 200
    assert (await deliver(client, echo)).status_code == 200
    assert (await deliver(client, _redelivered(echo, 1))).status_code == 200  # Meta may redeliver

    [contact] = await _contacts(client)
    assert len(contact["identities"]) == 1
    [conversation] = (await client.get("/api/conversations")).json()
    thread = (await client.get(f"/api/conversations/{conversation['id']}")).json()
    assert [(m["direction"], m["author"], m["text"]) for m in thread["messages"]] == [
        ("inbound", "contact", "hi"),
        ("outbound", "owner", "Hi! How can I help?"),
    ]


# --- failures are recorded, not swallowed --------------------------------------


async def test_event_for_unknown_account_is_acknowledged_and_marked_failed(
    client: httpx.AsyncClient, business_id: int
) -> None:
    payload = meta.direct_message("17849999999999999", mid="mid.$x", sender_id=SHOPPER_ID, text="hi")
    response = await deliver(client, payload)
    assert response.status_code == 200  # a retry from Meta would not fix this, so don't ask for one

    [event] = (await client.get("/api/webhook-events", params={"status": "failed"})).json()
    assert "17849999999999999" in event["error"]
    assert await _contacts(client) == []


# --- concurrency, limits, renames ----------------------------------------------


async def test_concurrent_deliveries_for_a_new_shopper_create_one_contact_and_deal(
    client: httpx.AsyncClient, business_id: int
) -> None:
    product = await create_product(client)
    await create_post(client, external_id=MEDIA_ID, product_id=product["id"])
    comments = [
        meta.comment_via_changes(
            IG_ACCOUNT_ID,
            comment_id=f"1790000000000020{n}",
            media_id=MEDIA_ID,
            from_id=SHOPPER_ID,
            username="maya.shops",
            text=f"comment {n}",
        )
        for n in range(6)
    ]
    dms = [
        meta.direct_message(IG_ACCOUNT_ID, mid=f"mid.$race{n}", sender_id=SHOPPER_ID, text=f"dm {n}")
        for n in range(4)
    ]
    responses = await asyncio.gather(*(deliver(client, p) for p in [*comments, *dms]))
    assert [r.status_code for r in responses] == [200] * 10

    [contact] = await _contacts(client)
    detail = (await client.get(f"/api/contacts/{contact['id']}")).json()
    assert len(detail["engagements"]) == 6
    assert len(detail["deals"]) == 1
    assert len(detail["conversations"]) == 1
    assert all(e["status"] == "processed" for e in await _events(client))


async def test_oversized_body_is_rejected(client: httpx.AsyncClient) -> None:
    response = await client.post("/webhooks/meta", content=b"x" * 1_000_001)
    assert response.status_code == 413


async def test_renamed_instagram_account_updates_the_contact_handle(
    client: httpx.AsyncClient, business_id: int
) -> None:
    for n, username in enumerate(["maya.shops", "maya.studio"]):
        payload = meta.comment_via_changes(
            IG_ACCOUNT_ID,
            comment_id=f"1790000000000030{n}",
            media_id=MEDIA_ID,
            from_id=SHOPPER_ID,
            username=username,
            text="hi",
        )
        assert (await deliver(client, payload)).status_code == 200

    [contact] = await _contacts(client)
    assert contact["display_name"] == "@maya.studio"


async def test_identical_body_is_stored_and_processed_once(
    client: httpx.AsyncClient, business_id: int
) -> None:
    payload = meta.direct_message(IG_ACCOUNT_ID, mid="mid.$same", sender_id=SHOPPER_ID, text="hi")
    first = await deliver(client, payload)
    second = await deliver(client, payload)
    assert first.json() == {"status": "received"}
    assert second.json() == {"status": "duplicate"}
    assert len(await _events(client)) == 1


async def test_echo_to_a_new_shopper_creates_no_lead(client: httpx.AsyncClient, business_id: int) -> None:
    echo = meta.echo_message(
        IG_ACCOUNT_ID, mid="mid.$first", recipient_id=SHOPPER_ID, text="Hi! Saw you liked our post"
    )
    assert (await deliver(client, echo)).status_code == 200
    assert (await client.get("/api/deals")).json() == []
    [conversation] = (await client.get("/api/conversations")).json()
    assert conversation["last_inbound_at"] is None


async def test_echo_after_a_comment_does_not_advance_the_deal(
    client: httpx.AsyncClient, business_id: int
) -> None:
    comment = meta.comment_via_changes(
        IG_ACCOUNT_ID,
        comment_id="1790000000000040",
        media_id=MEDIA_ID,
        from_id=SHOPPER_ID,
        username="maya",
        text="?",
    )
    echo = meta.echo_message(
        IG_ACCOUNT_ID, mid="mid.$reply", recipient_id=SHOPPER_ID, text="Sent you the price!"
    )
    await deliver(client, comment)
    await deliver(client, echo)
    [deal] = (await client.get("/api/deals")).json()
    assert deal["stage"] == "new"


async def test_stored_times_come_from_the_payload(client: httpx.AsyncClient, business_id: int) -> None:
    comment = meta.comment_via_changes(
        IG_ACCOUNT_ID,
        comment_id="1790000000000050",
        media_id=MEDIA_ID,
        from_id=SHOPPER_ID,
        username="maya",
        text="?",
        time=1_730_000_000,
    )
    dm = meta.direct_message(
        IG_ACCOUNT_ID, mid="mid.$t", sender_id=SHOPPER_ID, text="hi", timestamp_ms=1_730_000_100_250
    )
    await deliver(client, comment)
    await deliver(client, dm)
    [contact] = await _contacts(client)
    detail = (await client.get(f"/api/contacts/{contact['id']}")).json()
    assert detail["engagements"][0]["occurred_at"] == "2024-10-27T03:33:20Z"
    [conversation] = detail["conversations"]
    assert conversation["last_message"]["sent_at"] == "2024-10-27T03:35:00.250000Z"
    assert contact["last_activity_at"] == "2024-10-27T03:35:00.250000Z"
