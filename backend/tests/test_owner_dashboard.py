"""Phase 5: the pipeline board, deal detail, moving deals by hand, taking over a chat, and insights."""

import dataclasses
import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import update

from app.models import Business, Conversation
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
from tests.test_agent_runtime import SpySender

SHOPPER = "9100000000000042"


@pytest.fixture
async def app() -> AsyncIterator[FastAPI]:
    async for built in _build_app(make_settings(agent_enabled=True)):
        async with built.state.sessionmaker() as session:
            session.add(Business(name="Bloom & Thread", currency="USD", ig_account_id=IG_ACCOUNT_ID))
            await session.commit()
        yield built


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver", auth=OWNER_AUTH) as c:
        yield c


@pytest.fixture
async def catalog(client: httpx.AsyncClient) -> dict:
    dress = await create_product(
        client, name="Linen wrap dress", price_minor=6800, attributes={"sizes": "XS-XL"}
    )
    tote = await create_product(client, name="Hand-painted canvas tote", price_minor=3200)
    return {
        "dress": dress,
        "tote": tote,
        "dress_post": await create_post(
            client, external_id="18000000000000101", product_id=dress["id"], caption="Linen is back"
        ),
        "tote_post": await create_post(
            client, external_id="18000000000000102", product_id=tote["id"], caption="Totes!"
        ),
    }


async def comment(client: httpx.AsyncClient, post_id: int, username: str, text: str = "price?") -> dict:
    response = await client.post(
        "/api/simulator/instagram/comment", json={"post_id": post_id, "username": username, "text": text}
    )
    assert response.status_code == 200, response.text
    return response.json()


async def dm(client: httpx.AsyncClient, username: str, text: str) -> dict:
    response = await client.post("/api/simulator/instagram/dm", json={"username": username, "text": text})
    assert response.status_code == 200, response.text
    return response.json()


async def buy(client: httpx.AsyncClient, post_id: int, username: str) -> None:
    await comment(client, post_id, username)
    reply = (await dm(client, username, "I'll take it"))["agent_runs"][0]["reply_text"]
    path = re.search(r"/pay/[\w-]+", reply)
    assert path, reply
    browser = httpx.AsyncClient(transport=client._transport, base_url="http://testserver")  # no owner login
    assert (await browser.post(path.group(0))).status_code == 200


def real_dm(mid: str, text: str, *, at: datetime) -> dict:
    return meta.direct_message(
        IG_ACCOUNT_ID, mid=mid, sender_id=SHOPPER, text=text, timestamp_ms=int(at.timestamp() * 1000)
    )


# --- pipeline & deal detail ---------------------------------------------------------------------


async def test_pipeline_groups_deals_with_totals_and_attribution(
    client: httpx.AsyncClient, catalog: dict
) -> None:
    await buy(client, catalog["dress_post"]["id"], "ana")
    await comment(client, catalog["tote_post"]["id"], "ben")
    await dm(client, "cleo", "my order arrived damaged, I want a refund")

    board = (await client.get("/api/pipeline")).json()
    assert board["currency"] == "USD"
    assert [c["stage"] for c in board["columns"]] == [
        "new",
        "engaged",
        "qualified",
        "payment_sent",
        "won",
        "lost",
    ]
    columns = {c["stage"]: c for c in board["columns"]}
    [won] = columns["won"]["deals"]
    assert (columns["won"]["count"], columns["won"]["amount_minor"]) == (1, 6800)
    assert won["contact_name"] == "@ana"
    assert won["source_post"]["caption"] == "Linen is back"
    assert won["conversation_id"] is not None
    assert won["last_message"].startswith("Payment received")
    [handed] = [d for c in board["columns"] for d in c["deals"] if d["needs_owner"]]  # cleo's refund request
    assert (
        handed["agent_paused"] is True and handed["contact_name"] == "@cleo"
    )  # handle known, as after a lookup
    [tote] = [
        d for c in board["columns"] for d in c["deals"] if d["product_name"] == "Hand-painted canvas tote"
    ]
    assert tote["needs_owner"] is False


async def test_deal_detail_tells_the_story(client: httpx.AsyncClient, catalog: dict) -> None:
    await buy(client, catalog["dress_post"]["id"], "ana")
    [deal] = (await client.get("/api/deals")).json()
    detail = (await client.get(f"/api/deals/{deal['id']}")).json()
    assert [(c["from_stage"], c["to_stage"], c["actor"]) for c in detail["stage_changes"]] == [
        (None, "new", "system"),
        ("new", "engaged", "system"),
        ("engaged", "payment_sent", "agent"),
        ("payment_sent", "won", "system"),
    ]
    [link] = detail["payment_links"]
    assert (link["status"], link["amount_minor"]) == ("paid", 6800)
    assert (await client.get("/api/deals/999999")).status_code == 404


async def test_owner_can_move_a_deal_and_closing_it_retires_payment_links(
    app: FastAPI, client: httpx.AsyncClient, catalog: dict
) -> None:
    await comment(client, catalog["dress_post"]["id"], "ana")
    await dm(client, "ana", "I'll take it")
    [deal] = (await client.get("/api/deals")).json()

    moved = await client.patch(f"/api/deals/{deal['id']}", json={"stage": "won"})  # paid in cash
    assert moved.status_code == 200, moved.text
    assert moved.json()["stage_changes"][-1] == {
        **moved.json()["stage_changes"][-1],
        "actor": "owner",
        "to_stage": "won",
    }
    assert [link["status"] for link in moved.json()["payment_links"]] == ["expired"]

    back = await client.patch(f"/api/deals/{deal['id']}", json={"stage": "qualified"})  # owner can move back
    assert back.json()["stage"] == "qualified"
    assert (await client.patch(f"/api/deals/{deal['id']}", json={"stage": None})).status_code == 422
    assert (await client.patch(f"/api/deals/{deal['id']}", json={"stage": "shipped"})).status_code == 422


async def test_reopening_a_deal_that_would_duplicate_an_open_one_is_a_conflict(
    client: httpx.AsyncClient, catalog: dict
) -> None:
    await comment(client, catalog["dress_post"]["id"], "ana")
    [first] = (await client.get("/api/deals")).json()
    await client.patch(f"/api/deals/{first['id']}", json={"stage": "lost"})
    await comment(
        client, catalog["dress_post"]["id"], "ana", "actually, still available?"
    )  # opens a new deal
    response = await client.patch(f"/api/deals/{first['id']}", json={"stage": "engaged"})
    assert response.status_code == 409
    assert "already has another open deal" in response.json()["detail"]


# --- taking over a chat ------------------------------------------------------------------------------


@pytest.fixture
def live(app: FastAPI) -> SpySender:
    spy = SpySender()
    app.state.agent = dataclasses.replace(app.state.agent, live_sender=spy)
    return spy


async def _conversation_id(client: httpx.AsyncClient) -> int:
    [conversation] = (await client.get("/api/conversations")).json()
    return conversation["id"]


async def test_owner_reply_pauses_the_agent_and_is_sent_once(
    client: httpx.AsyncClient, catalog: dict, live: SpySender
) -> None:
    await deliver(client, real_dm("m.1", "is the dress in stock?", at=datetime.now(UTC)))
    live.sent.clear()
    conversation_id = await _conversation_id(client)

    sent = await client.post(
        f"/api/conversations/{conversation_id}/messages", json={"text": "Yes! I'll hold one for you"}
    )
    assert sent.status_code == 201, sent.text
    assert sent.json()["author"] == "owner"
    assert [(r.kind, r.id, text) for _, r, text in live.sent] == [
        ("user", SHOPPER, "Yes! I'll hold one for you")
    ]
    assert live.tags == [None, None]  # the agent's earlier reply, then the owner's: both within 24 hours

    [conversation] = (await client.get("/api/conversations")).json()
    assert (conversation["agent_paused"], conversation["paused_reason"]) == (True, "you took over this chat")
    live.sent.clear()
    await deliver(client, real_dm("m.2", "great, thanks!", at=datetime.now(UTC)))
    assert live.sent == []  # the agent stays out of it

    echo = meta.echo_message(
        IG_ACCOUNT_ID, mid="mid.live.2", recipient_id=SHOPPER, text="Yes! I'll hold one for you"
    )
    await deliver(client, echo)  # Meta echoes the owner's message back: stored once
    thread = (await client.get(f"/api/conversations/{conversation_id}")).json()
    assert sum(m["text"] == "Yes! I'll hold one for you" for m in thread["messages"]) == 1


async def test_owner_can_reply_for_7_days_with_the_human_agent_tag(
    app: FastAPI, client: httpx.AsyncClient, live: SpySender
) -> None:
    await deliver(client, real_dm("m.old", "hello?", at=datetime.now(UTC) - timedelta(days=3)))
    conversation_id = await _conversation_id(client)
    sent = await client.post(
        f"/api/conversations/{conversation_id}/messages", json={"text": "Sorry for the wait!"}
    )
    assert sent.status_code == 201, sent.text
    assert live.tags[-1] == "HUMAN_AGENT"

    async with app.state.sessionmaker() as session:
        await session.execute(
            update(Conversation).values(last_inbound_at=datetime.now(UTC) - timedelta(days=8))
        )
        await session.commit()
    late = await client.post(f"/api/conversations/{conversation_id}/messages", json={"text": "Still there?"})
    assert late.status_code == 409
    assert "7 days" in late.json()["detail"]


async def test_a_refused_send_stores_nothing(app: FastAPI, client: httpx.AsyncClient) -> None:
    from app.channels.messaging import SendError

    class RefusingSender(SpySender):
        async def send_text(self, account_id, recipient, text, tag=None):  # type: ignore[no-untyped-def]
            raise SendError("Instagram Send API 400: (#10) not allowed")

    await deliver(client, real_dm("m.1", "hi", at=datetime.now(UTC)))
    app.state.agent = dataclasses.replace(app.state.agent, live_sender=RefusingSender())
    conversation_id = await _conversation_id(client)
    before = len((await client.get(f"/api/conversations/{conversation_id}")).json()["messages"])
    response = await client.post(f"/api/conversations/{conversation_id}/messages", json={"text": "hello"})
    assert response.status_code == 502
    after = (await client.get(f"/api/conversations/{conversation_id}")).json()
    assert len(after["messages"]) == before
    assert after["agent_paused"] is False


async def test_owner_messages_are_validated_and_scoped(client: httpx.AsyncClient, catalog: dict) -> None:
    await dm(client, "ana", "hi")
    conversation_id = await _conversation_id(client)
    assert (
        await client.post(f"/api/conversations/{conversation_id}/messages", json={"text": ""})
    ).status_code == 422
    assert (
        await client.post(f"/api/conversations/{conversation_id}/messages", json={"text": "x" * 1001})
    ).status_code == 422
    assert (await client.post("/api/conversations/999999/messages", json={"text": "hi"})).status_code == 404
    cross_site = await client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"text": "hi"},
        headers={"Origin": "https://evil.example"},
    )
    assert cross_site.status_code == 403


# --- insights ----------------------------------------------------------------------------------------


async def test_insights_answer_which_post_made_money(client: httpx.AsyncClient, catalog: dict) -> None:
    await buy(client, catalog["dress_post"]["id"], "ana")  # won $68
    await buy(client, catalog["dress_post"]["id"], "ben")  # won $68
    await comment(client, catalog["dress_post"]["id"], "cleo")
    await dm(client, "cleo", "no thanks, not interested")  # lost
    await comment(client, catalog["tote_post"]["id"], "dev")
    await dm(client, "dev", "size small please")  # qualified (the tote has no sizes, but the detail is kept)
    await dm(client, "eli", "I want a refund for my last order")  # hand-off, product-less deal

    stats = (await client.get("/api/insights", params={"days": 30})).json()
    assert (stats["leads"], stats["deals"], stats["won"], stats["revenue_minor"]) == (5, 5, 2, 13600)
    assert stats["conversion_rate"] == pytest.approx(0.4)
    assert stats["handoffs"] == 1
    assert stats["agent_replies"] >= 8
    assert stats["median_agent_reply_seconds"] is not None and stats["median_agent_reply_seconds"] < 5
    assert [(f["stage"], f["reached"]) for f in stats["funnel"]] == [
        ("new", 5),
        ("engaged", 5),
        ("qualified", 1 + 2),  # dev qualified; ana and ben went straight to payment, which is past qualified
        ("payment_sent", 2),
        ("won", 2),
    ]
    top, second = stats["by_post"]
    assert (top["post"]["caption"], top["leads"], top["deals"], top["won"], top["revenue_minor"]) == (
        "Linen is back",
        3,
        3,
        2,
        13600,
    )
    assert (second["post"]["caption"], second["won"], second["revenue_minor"]) == ("Totes!", 0, 0)
    assert stats["by_channel"] == [{"channel": "instagram", "deals": 5, "won": 2, "revenue_minor": 13600}]
    assert (await client.get("/api/insights", params={"days": 0})).status_code == 422


async def test_insights_with_no_activity(client: httpx.AsyncClient) -> None:
    stats = (await client.get("/api/insights")).json()
    assert (stats["deals"], stats["conversion_rate"], stats["median_agent_reply_seconds"]) == (0, None, None)
    assert stats["by_post"] == [] and stats["by_channel"] == []
    assert all(step["reached"] == 0 for step in stats["funnel"])


# --- regressions from adversarial review --------------------------------------------------------------


async def test_the_agent_sends_nothing_if_the_owner_takes_over_while_it_thinks(
    app: FastAPI, client: httpx.AsyncClient, live: SpySender
) -> None:
    from tests.test_agent_runtime import ScriptedModel, call, say

    class OwnerJumpsIn(ScriptedModel):
        async def complete(self, messages, tools):  # type: ignore[no-untyped-def]
            if len(self.seen) == 0:  # while the model is thinking, the owner replies from the inbox
                [conversation] = (await client.get("/api/conversations")).json()
                sent = await client.post(
                    f"/api/conversations/{conversation['id']}/messages", json={"text": "I've got this"}
                )
                assert sent.status_code == 201, sent.text
            return await super().complete(messages, tools)

    # the turn also tries to hand off: that must not overwrite the owner's takeover either
    app.state.agent = dataclasses.replace(
        app.state.agent, llm=OwnerJumpsIn(call("hand_off_to_owner", reason="refund"), say("Holding message"))
    )
    await deliver(client, real_dm("m.1", "price?", at=datetime.now(UTC)))
    assert [text for _, _, text in live.sent] == ["I've got this"]
    [conversation] = (await client.get("/api/conversations")).json()
    assert (conversation["paused_by"], conversation["paused_reason"]) == ("owner", "you took over this chat")
    [run] = (await client.get(f"/api/conversations/{conversation['id']}/agent-runs")).json()
    assert run["status"] == "skipped" and "owner took over" in run["error"]


async def _paid_deal(client: httpx.AsyncClient, catalog: dict) -> dict:
    await buy(client, catalog["dress_post"]["id"], "ana")
    [deal] = (await client.get("/api/deals")).json()
    return deal


async def test_a_paid_deal_cannot_be_moved_out_of_won(client: httpx.AsyncClient, catalog: dict) -> None:
    deal = await _paid_deal(client, catalog)
    for stage in ("lost", "qualified"):
        response = await client.patch(f"/api/deals/{deal['id']}", json={"stage": stage})
        assert response.status_code == 409
        assert "paid" in response.json()["detail"]
    assert (await client.get(f"/api/deals/{deal['id']}")).json()["stage"] == "won"


async def test_pulling_a_deal_out_of_checkout_kills_its_link(
    client: httpx.AsyncClient, catalog: dict
) -> None:
    await comment(client, catalog["dress_post"]["id"], "ana")
    reply = (await dm(client, "ana", "I'll take it"))["agent_runs"][0]["reply_text"]
    path = re.search(r"/pay/[\w-]+", reply).group(0)  # type: ignore[union-attr]
    [deal] = (await client.get("/api/deals")).json()
    moved = await client.patch(f"/api/deals/{deal['id']}", json={"stage": "new"})
    assert [link["status"] for link in moved.json()["payment_links"]] == ["expired"]
    browser = httpx.AsyncClient(transport=client._transport, base_url="http://testserver")
    assert (await browser.post(path)).status_code == 410


async def test_a_cash_sale_can_carry_its_amount(client: httpx.AsyncClient, catalog: dict) -> None:
    await dm(client, "zoe", "hi! do you do custom orders?")  # product-less deal
    [deal] = (await client.get("/api/deals")).json()
    won = await client.patch(f"/api/deals/{deal['id']}", json={"stage": "won", "amount_minor": 12000})
    assert (won.json()["stage"], won.json()["amount_minor"]) == ("won", 12000)
    stats = (await client.get("/api/insights")).json()
    assert (stats["won"], stats["revenue_minor"]) == (1, 12000)


async def test_needs_owner_comes_from_who_paused_not_the_reason_text(
    app: FastAPI, client: httpx.AsyncClient, catalog: dict
) -> None:
    from tests.test_agent_runtime import ScriptedModel, call, say

    app.state.agent = dataclasses.replace(
        app.state.agent,
        llm=ScriptedModel(call("hand_off_to_owner", reason="you took over this chat"), say("ok")),
    )
    await dm(client, "mallory", "hi")
    board = (await client.get("/api/pipeline")).json()
    [card] = [d for c in board["columns"] for d in c["deals"]]
    assert card["needs_owner"] is True
    assert board["needs_owner"] == 1


async def test_column_totals_count_every_deal_even_when_cards_are_capped(
    client: httpx.AsyncClient, catalog: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.crm import pipeline

    monkeypatch.setattr(pipeline, "CARDS_PER_COLUMN", 2)
    for name in ("a1", "a2", "a3"):
        await buy(client, catalog["tote_post"]["id"], name)
    won = next(c for c in (await client.get("/api/pipeline")).json()["columns"] if c["stage"] == "won")
    assert (won["count"], won["amount_minor"], len(won["deals"])) == (3, 9600, 2)


async def test_insights_work_at_volume(app: FastAPI, client: httpx.AsyncClient) -> None:
    from sqlalchemy import text

    await dm(client, "bulk", "hi")
    async with app.state.sessionmaker() as session:
        await session.execute(
            text(
                "INSERT INTO deals (business_id, contact_id, channel, stage, details, amount_minor) "
                "SELECT business_id, contact_id, 'instagram', 'lost', '{}', 100 "
                "FROM deals, generate_series(1, 33000)"
            )
        )
        await session.commit()
    response = await client.get("/api/insights", params={"days": 365})
    assert response.status_code == 200, response.text
    assert response.json()["deals"] == 33001


async def test_a_corrected_misclick_does_not_count_as_won_in_the_funnel(
    client: httpx.AsyncClient, catalog: dict
) -> None:
    await comment(client, catalog["tote_post"]["id"], "ana")
    [deal] = (await client.get("/api/deals")).json()
    await client.patch(f"/api/deals/{deal['id']}", json={"stage": "won"})
    await client.patch(f"/api/deals/{deal['id']}", json={"stage": "new"})  # oops, wrong card
    funnel = {f["stage"]: f["reached"] for f in (await client.get("/api/insights")).json()["funnel"]}
    assert (funnel["payment_sent"], funnel["won"]) == (0, 0)


async def test_leads_mean_the_same_thing_in_totals_and_per_post(
    app: FastAPI, client: httpx.AsyncClient, catalog: dict
) -> None:
    from app.models import Contact

    await comment(client, catalog["dress_post"]["id"], "old.friend")
    async with app.state.sessionmaker() as session:  # someone first seen two months ago...
        await session.execute(update(Contact).values(created_at=datetime.now(UTC) - timedelta(days=60)))
        await session.commit()
    await comment(client, catalog["dress_post"]["id"], "old.friend", "back again!")  # ...comments today
    stats = (await client.get("/api/insights", params={"days": 7})).json()
    assert stats["leads"] == 0
    assert sum(p["leads"] for p in stats["by_post"]) == 0


async def test_a_hand_off_after_a_model_error_is_counted(app: FastAPI, client: httpx.AsyncClient) -> None:
    from app.agent.llm import LLMError
    from tests.test_agent_runtime import ScriptedModel

    app.state.agent = dataclasses.replace(
        app.state.agent, llm=ScriptedModel(LLMError("billing", retryable=False))
    )
    await dm(client, "kim", "hello")
    stats = (await client.get("/api/insights")).json()
    assert (stats["agent_replies"], stats["handoffs"]) == (1, 1)


@pytest.mark.parametrize(("text", "reason"), [("   \n\t ", "empty"), ("é" * 501, "1000 bytes")])
async def test_owner_messages_must_be_sendable(client: httpx.AsyncClient, text: str, reason: str) -> None:
    await dm(client, "ana", "hi")
    conversation_id = await _conversation_id(client)
    response = await client.post(f"/api/conversations/{conversation_id}/messages", json={"text": text})
    assert response.status_code == 422, reason
    assert (await client.get("/api/conversations")).json()[0]["agent_paused"] is False


async def test_the_owner_can_privately_reply_to_a_shopper_who_only_commented(
    client: httpx.AsyncClient, catalog: dict, live: SpySender
) -> None:
    def real_comment(comment_id: str) -> dict:
        return meta.comment_via_changes(
            IG_ACCOUNT_ID,
            comment_id=comment_id,
            media_id="18000000000000101",
            from_id=SHOPPER,
            username="real",
            text="price?",
            time=int(datetime.now(UTC).timestamp()),
        )

    await deliver(client, real_comment("17900000000000001"))  # the agent's private reply uses comment 1
    conversation_id = await _conversation_id(client)
    await client.patch(f"/api/conversations/{conversation_id}", json={"agent_paused": True})
    blocked = await client.post(f"/api/conversations/{conversation_id}/messages", json={"text": "hi again"})
    assert blocked.status_code == 409  # that comment's one private reply is used up

    await deliver(client, real_comment("17900000000000002"))  # a new comment: one new private reply allowed
    sent = await client.post(f"/api/conversations/{conversation_id}/messages", json={"text": "It's $68!"})
    assert sent.status_code == 201, sent.text
    assert (live.sent[-1][1].kind, live.sent[-1][1].id) == ("comment", "17900000000000002")


def test_owner_replies_are_tagged_a_little_before_24_hours_to_allow_for_clock_skew() -> None:
    from app.channels.messaging import owner_route

    now = datetime(2026, 11, 1, 12, tzinfo=UTC)
    early = owner_route(
        now=now, contact_external_id="1", last_inbound_at=now - timedelta(hours=23, minutes=40)
    )
    edge = owner_route(
        now=now, contact_external_id="1", last_inbound_at=now - timedelta(hours=23, minutes=55)
    )
    assert getattr(early, "tag", "x") is None
    assert getattr(edge, "tag", None) == "HUMAN_AGENT"


async def test_receipts_say_test_mode_only_to_real_shoppers(
    app: FastAPI, client: httpx.AsyncClient, catalog: dict, live: SpySender
) -> None:
    from tests.test_agent_runtime import ScriptedModel, call, say

    await buy(client, catalog["tote_post"]["id"], "sim.shopper")  # simulated: the owner testing
    simulated = [m for c in (await client.get("/api/conversations")).json() for m in [c["last_message"]]]
    assert simulated[0]["text"].endswith("We'll be in touch about delivery.")

    app.state.agent = dataclasses.replace(
        app.state.agent,
        llm=ScriptedModel(call("create_payment_link", product_id=catalog["tote"]["id"]), say("here")),
    )
    await deliver(client, real_dm("m.real", "I'll take the tote", at=datetime.now(UTC)))
    path = re.search(r"/pay/[\w-]+", live.sent[-1][2]).group(0)  # type: ignore[union-attr]
    browser = httpx.AsyncClient(transport=client._transport, base_url="http://testserver")
    await browser.post(path)
    assert live.sent[-1][2].endswith("(Test checkout: no money was taken.)")
