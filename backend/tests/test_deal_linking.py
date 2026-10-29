"""Which deal a comment or DM lands on, in setups with several posts, products and shoppers."""

import asyncio
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select, update

from app.crm import deals as deals_module
from app.models import Deal, DealStage, DealStageChange
from tests import meta_payloads as meta
from tests.conftest import IG_ACCOUNT_ID, create_post, create_product, deliver

MAYA = "9100000000000042"
SAM = "9100000000000077"


def _comment(comment_id: str, media_id: str, *, shopper: str = MAYA, time: int = 1_730_000_000) -> dict:
    return meta.comment_via_changes(
        IG_ACCOUNT_ID,
        comment_id=comment_id,
        media_id=media_id,
        from_id=shopper,
        username=f"u{shopper[-4:]}",
        text="price?",
        time=time,
    )


def _dm(mid: str, *, shopper: str = MAYA, ms: int = 1_730_000_500_000) -> dict:
    return meta.direct_message(IG_ACCOUNT_ID, mid=mid, sender_id=shopper, text="hi", timestamp_ms=ms)


async def _deals(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    return (await client.get("/api/deals")).json()


async def _catalog(client: httpx.AsyncClient) -> dict[str, Any]:
    dress = await create_product(client, name="Dress", price_minor=6800)
    tote = await create_product(client, name="Tote", price_minor=3200)
    return {
        "dress": dress,
        "tote": tote,
        "dress_post": await create_post(client, external_id="18000000000000101", product_id=dress["id"]),
        "dress_reel": await create_post(client, external_id="18000000000000102", product_id=dress["id"]),
        "tote_post": await create_post(client, external_id="18000000000000103", product_id=tote["id"]),
    }


async def test_comment_links_the_exact_post_and_product(client: httpx.AsyncClient, business_id: int) -> None:
    cat = await _catalog(client)
    await deliver(client, _comment("c1", "18000000000000103"))
    [deal] = await _deals(client)
    assert deal["product_id"] == cat["tote"]["id"] != cat["tote_post"]["id"]
    assert deal["source_post_id"] == cat["tote_post"]["id"]
    assert deal["amount_minor"] == 3200


async def test_two_posts_of_one_product_share_one_deal(client: httpx.AsyncClient, business_id: int) -> None:
    cat = await _catalog(client)
    await deliver(client, _comment("c1", "18000000000000101"))
    await deliver(client, _comment("c2", "18000000000000102"))
    [deal] = await _deals(client)
    assert deal["product_id"] == cat["dress"]["id"]
    assert deal["source_post_id"] == cat["dress_post"]["id"]  # first touch is kept


async def test_two_products_open_two_deals_and_a_dm_advances_the_latest(
    client: httpx.AsyncClient, business_id: int
) -> None:
    cat = await _catalog(client)
    await deliver(client, _comment("c1", "18000000000000101"))
    await deliver(client, _comment("c2", "18000000000000103"))
    await deliver(client, _dm("mid.1"))
    by_product = {d["product_id"]: d for d in await _deals(client)}
    assert by_product[cat["dress"]["id"]]["stage"] == "new"
    assert by_product[cat["tote"]["id"]]["stage"] == "engaged"
    [contact] = (await client.get("/api/contacts")).json()
    assert contact["latest_deal"]["product_id"] == cat["tote"]["id"]
    deals = await _deals(client)
    assert deals[0]["product_id"] == cat["tote"]["id"]  # most recently updated first


async def test_two_shoppers_on_one_post_get_their_own_deals(
    client: httpx.AsyncClient, business_id: int
) -> None:
    await _catalog(client)
    await deliver(client, _comment("c1", "18000000000000101", shopper=MAYA))
    await deliver(client, _comment("c2", "18000000000000101", shopper=SAM))
    await deliver(client, _dm("mid.sam", shopper=SAM))
    stages = {d["contact_name"]: d["stage"] for d in await _deals(client)}
    assert stages == {"@u0042": "new", "@u0077": "engaged"}


async def test_dm_first_then_comment_fills_in_post_and_product(
    client: httpx.AsyncClient, business_id: int
) -> None:
    cat = await _catalog(client)
    await deliver(client, _dm("mid.1"))
    await deliver(client, _comment("c1", "18000000000000103"))
    [deal] = await _deals(client)
    assert (deal["product_id"], deal["source_post_id"]) == (cat["tote"]["id"], cat["tote_post"]["id"])
    assert deal["stage"] == "engaged"


@pytest.mark.parametrize("stage", [DealStage.QUALIFIED, DealStage.PAYMENT_SENT])
async def test_dm_never_moves_a_deal_backwards(
    app: FastAPI, client: httpx.AsyncClient, business_id: int, stage: DealStage
) -> None:
    await deliver(client, _dm("mid.1"))
    async with app.state.sessionmaker() as session:
        await session.execute(update(Deal).values(stage=stage))
        await session.commit()
    await deliver(client, _dm("mid.2", ms=1_730_000_600_000))
    [deal] = await _deals(client)
    assert deal["stage"] == stage.value


async def test_a_recently_lost_deal_also_suppresses_new_dm_deals(
    app: FastAPI, client: httpx.AsyncClient, business_id: int
) -> None:
    await deliver(client, _dm("mid.1"))
    async with app.state.sessionmaker() as session:
        await session.execute(update(Deal).values(stage=DealStage.LOST))
        await session.commit()
    await deliver(client, _dm("mid.2", ms=1_730_000_600_000))
    assert [d["stage"] for d in await _deals(client)] == ["lost"]


async def test_every_stage_change_is_recorded(
    app: FastAPI, client: httpx.AsyncClient, business_id: int
) -> None:
    await _catalog(client)
    await deliver(client, _comment("c1", "18000000000000101"))
    await deliver(client, _dm("mid.1"))
    async with app.state.sessionmaker() as session:
        rows = (await session.execute(select(DealStageChange).order_by(DealStageChange.id))).scalars().all()
    assert [(r.from_stage, r.to_stage, r.actor.value) for r in rows] == [
        (None, DealStage.NEW, "system"),
        (DealStage.NEW, DealStage.ENGAGED, "system"),
    ]


async def test_concurrent_comments_from_a_known_shopper_open_one_deal_per_product(
    client: httpx.AsyncClient, business_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The contact already exists, so only the per-contact lock prevents duplicate deals.
    open_deal is slowed down to widen the check-then-insert window."""
    cat = await _catalog(client)
    await deliver(client, _comment("c.seed", "18000000000000101"))  # known shopper with a dress deal
    original = deals_module.open_deal

    async def slow_open_deal(*args: Any, **kwargs: Any) -> Deal:
        await asyncio.sleep(0.05)
        return await original(*args, **kwargs)

    monkeypatch.setattr(deals_module, "open_deal", slow_open_deal)
    comments = [_comment(f"c{n}", "18000000000000103") for n in range(12)]  # all race for the tote
    await asyncio.gather(*(deliver(client, c) for c in comments))

    events = (await client.get("/api/webhook-events", params={"limit": 50})).json()
    assert {e["status"] for e in events} == {"processed"}
    products = sorted(d["product_id"] for d in await _deals(client))
    assert products == sorted([cat["dress"]["id"], cat["tote"]["id"]])


async def test_a_failing_event_leaves_no_partial_writes(
    client: httpx.AsyncClient, business_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    cat = await _catalog(client)
    original = deals_module.deal_for_comment

    async def explode_on_tote(session: Any, **kwargs: Any) -> Deal:
        if kwargs["post"].external_id == "18000000000000103":
            raise RuntimeError("boom")
        return await original(session, **kwargs)

    monkeypatch.setattr(deals_module, "deal_for_comment", explode_on_tote)
    good = _comment("c1", "18000000000000101")
    bad = _comment("c2", "18000000000000103")
    await deliver(client, {"object": "instagram", "entry": [*good["entry"], *bad["entry"]]})

    [contact] = (await client.get("/api/contacts")).json()
    detail = (await client.get(f"/api/contacts/{contact['id']}")).json()
    [engagement] = detail["engagements"]  # the tote comment's engagement was rolled back
    assert engagement["post_id"] == cat["dress_post"]["id"]
    assert len(detail["deals"]) == 1
    [event] = (await client.get("/api/webhook-events")).json()
    assert event["status"] == "failed"
    assert "RuntimeError (details in server log)" in event["error"]
