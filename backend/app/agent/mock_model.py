"""A deterministic stand-in for Muse Spark, used until Meta Model API credits arrive (LLM_PROVIDER=mock).

It speaks the same LLMClient protocol as the real model: it picks tools from simple intent rules, then writes
a reply using only the tool results, the facts Salesie gave it and the owner's shop notes. It never invents
prices or policies. Every agent run records it as "mock-sales-brain", so it is never mistaken for Muse Spark.
"""

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from app.agent.llm import AssistantTurn, ChatMessage, ToolCall, ToolSpec

_DECLINE = re.compile(
    r"\b(no thanks|no thank you|not interested|never ?mind|maybe later|not now|don'?t want|do not want|"
    r"changed my mind|no longer|not anymore|i'?ll pass)\b"
)
_HUMAN = re.compile(
    r"\b(refund|broken|damaged|complain\w*|angry|scam|human|real person|manager|wrong item|never arrived|"
    r"(?:speak|talk) to (?:the )?owner)\b"
)
_BUY = re.compile(
    r"\b(buy|checkout|check out|send (?:me )?(?:the |a )?link|i'?ll take|take (?:it|one|two|three|\d)|"
    r"order (?:it|one|two|three|\d)|purchase|i want (?:to buy|one|two|three|it|\d)|go ahead)\b"
)
_AFFIRM = re.compile(r"^\W*(yes|yep|yeah|yup|sure|ok|okay|yes please|sounds good|let'?s do it|perfect)\b")
_THANKS = re.compile(r"\b(thanks|thank you|thx|ty)\b")
_SIZES = {"xxs": "XXS", "xs": "XS", "small": "S", "medium": "M", "large": "L", "xl": "XL", "xxl": "XXL"}
_SIZE = re.compile(
    r"\b(xxs|xs|xxl|xl|small|medium|large)\b|\bsize\s+(\w{1,3})\b|^\W*(s|m|l)\W*(?:please|pls)?\W*$"
)
_COLOUR = re.compile(
    r"\b(black|white|red|blue|green|sage|pink|beige|natural|navy|grey|gray|brown|yellow|purple|silver|gold)\b"
)
_NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
_QUANTITY = re.compile(
    r"\b(?:take|want|need|order|buy|get)\s+(?:a\s+)?(\d|one|two|three|four|five)\b"
    r"|\b(\d|two|three|four|five)\s+(?:pcs|pieces|pairs|units|of (?:these|them|those))\b"
)
_SHIPPING = re.compile(r"\b(ship\w*|deliver\w*|returns?|exchange|cod|cash on delivery|pay on delivery)\b")
_OBJECTION = re.compile(r"\b(expensive|too much|pricey|cheaper|discount|coupon|sale)\b")
_DEAL_LINE = re.compile(r"^- (.+?) \(product id (\d+)(?:, ([^)]+))?\), stage (\w+)", re.MULTILINE)
_HANDLE = re.compile(r"Shopper: @([\w.]+)")
ALREADY_SENT = "Your checkout link is in my last message. Let me know if you have any trouble!"
NOT_FOUND = "Hmm, I couldn't find that in our shop. What are you looking for? Happy to help!"
_CONTEXT_PREFIX = "Context from this shopper"
_COMMENT = re.compile(r'^\(public comment on your post\) "(.*)"$', re.DOTALL)


@dataclass(frozen=True)
class _Deal:
    name: str
    product_id: int
    price: str | None
    stage: str


class MockSalesModel:
    @property
    def model_name(self) -> str:
        return "mock-sales-brain"

    async def complete(self, messages: Sequence[ChatMessage], tools: Sequence[ToolSpec]) -> AssistantTurn:
        text = _shopper_text(messages)
        facts = (messages[1].content or "") if len(messages) > 1 else ""
        deals = [_Deal(m[0], int(m[1]), m[2] or None, m[3]) for m in _DEAL_LINE.findall(facts)]
        results = _tool_results_this_turn(messages)
        if not results:
            return _first_move(text, deals, _last_reply(messages))
        if follow_up := _second_move(text, results):
            return follow_up
        return AssistantTurn(text=_compose(text, facts, deals, _shop_notes(messages), results, messages))


def _first_move(text: str, deals: list[_Deal], last_reply: str) -> AssistantTurn:
    focus = _named(deals, text) or (deals[0] if deals else None)
    if _DECLINE.search(text):
        if focus is None:
            return AssistantTurn(text="No problem at all! If you change your mind, just message us 😊")
        lost = {"stage": "lost", "reason": "shopper declined", "product_id": focus.product_id}
        return _calls(("update_deal_stage", lost))
    if _HUMAN.search(text):
        return _calls(("hand_off_to_owner", {"reason": f"Shopper wrote: {text[:150]}"}))
    details = _details(text)
    if _wants_to_buy(text):
        if focus is None:  # e.g. started in DMs: buy what was just discussed
            return _calls(("search_catalog", {"query": f"{text} {last_reply}"[:200]}))
        if focus.stage == "payment_sent" and not details and _quantity(text) == 1:
            return AssistantTurn(text=ALREADY_SENT)
        calls: list[tuple[str, dict[str, Any]]] = []
        if details:
            calls.append(("note_customer_details", {"details": details, "product_id": focus.product_id}))
        calls.append(("create_payment_link", {"product_id": focus.product_id, "quantity": _quantity(text)}))
        return _calls(*calls)
    if details and focus is not None:
        calls = [("note_customer_details", {"details": details, "product_id": focus.product_id})]
        if focus.stage in ("new", "engaged"):
            reason = f"wants {_describe(details)}"
            qualified = {"stage": "qualified", "reason": reason, "product_id": focus.product_id}
            calls.append(("update_deal_stage", qualified))
        return _calls(*calls)
    if _THANKS.search(text) and "?" not in text:
        return AssistantTurn(text="You're welcome! 😊 Let me know if there's anything else I can help with.")
    if focus is not None and not _mentions_other_product(text, focus):
        return _calls(("get_product", {"product_id": focus.product_id}))
    return _calls(("search_catalog", {"query": text[:200]}))


def _second_move(text: str, results: dict[str, dict[str, Any]]) -> AssistantTurn | None:
    """After a search for a shopper who wants to buy: check out the product they meant."""
    if "create_payment_link" in results or "search_catalog" not in results or not _wants_to_buy(text):
        return None
    products = results["search_catalog"].get("products", [])
    if not products:
        return None
    named = next((p for p in products if _name_in(p["name"], text)), None)
    chosen = named or (products[0] if len(products) == 1 else None)
    if chosen is None:
        return None
    return _calls(("create_payment_link", {"product_id": chosen["id"], "quantity": _quantity(text)}))


def _compose(
    text: str,
    facts: str,
    deals: list[_Deal],
    notes: str,
    results: dict[str, dict[str, Any]],
    messages: Sequence[ChatMessage],
) -> str:
    handle = _HANDLE.search(facts)
    greeting = f"Hi {handle.group(1)}! " if handle and _is_first_reply(messages) else ""
    if "hand_off_to_owner" in results:
        return "Thanks for letting us know. I've passed this to the owner, who will reply here shortly 🙏"
    if link := results.get("create_payment_link"):
        if "url" not in link:
            return "Sorry, I couldn't create a checkout link just now. The owner will follow up with you."
        times = f" x{link['quantity']}" if link["quantity"] > 1 else ""
        total = f"{link['product']}{times} ({link['total']})"
        return f"Lovely! Here's your secure checkout for the {total}: {link['url']}"
    if results.get("update_deal_stage", {}).get("stage") == "lost":
        return "No problem at all! If you change your mind, just message us 😊"
    if noted := results.get("note_customer_details", {}):
        if "saved" in noted:
            deal = next((d for d in deals if d.product_id == noted.get("deal_product_id")), None)
            product = f"The {deal.name} is {deal.price}. " if deal and deal.price else ""
            return f"Great choice, {_describe(noted['saved'])}! {product}Shall I send you a checkout link?"
    if product := results.get("get_product", {}).get("product"):
        return greeting + _product_reply(product, text, notes)
    if (found := results.get("search_catalog")) is not None:
        products = found.get("products", [])
        if not products:
            return greeting + NOT_FOUND
        listing = ", ".join(f"the {p['name']} ({p['price']})" for p in products[:3])
        ask = "Would you like it?" if len(products) == 1 else "Which one caught your eye?"
        return f"{greeting}We have {listing}. {ask}"
    return "Thanks for your message! How can I help?"


def _product_reply(product: dict[str, Any], text: str, notes: str) -> str:
    price = f" is {product['price']}" if product.get("price") else " is available"
    attributes = product.get("attributes") or {}
    extras = ", ".join(f"{k} {v}" for k, v in attributes.items() if isinstance(v, str | int))
    sentence = f"The {product['name']}{price}" + (f" ({extras})" if extras else "") + "."
    if _OBJECTION.search(text):
        return f"I totally get it! {sentence} We don't run discounts, but I'm happy to answer any questions."
    if _SHIPPING.search(text):
        return notes.strip().split("\n")[0] if notes.strip() else "I'll check delivery with the owner."
    question = "Which size would you like?" if "sizes" in attributes else "Would you like to order one?"
    return f"{sentence} {question}"


# --- reading the conversation ---------------------------------------------------------------


def _shopper_text(messages: Sequence[ChatMessage]) -> str:
    """The shopper's messages since our last reply, lowercased, without Salesie's comment framing."""
    collected: list[str] = []
    for message in reversed(messages):
        if message.role == "assistant" and not message.tool_calls:
            break
        if message.role == "user" and message.content and not message.content.startswith(_CONTEXT_PREFIX):
            collected.append(_COMMENT.sub(r"\1", message.content))
    return " ".join(reversed(collected)).lower()


def _last_reply(messages: Sequence[ChatMessage]) -> str:
    replies = (m.content or "" for m in reversed(messages) if m.role == "assistant" and not m.tool_calls)
    return next(replies, "")


def _tool_results_this_turn(messages: Sequence[ChatMessage]) -> dict[str, dict[str, Any]]:
    names: dict[str, str] = {}
    results: dict[str, dict[str, Any]] = {}
    for message in messages:
        if message.role == "user":
            names, results = {}, {}
        for call in message.tool_calls:
            names[call.id] = call.name
        if message.role == "tool" and message.tool_call_id in names:
            results[names[message.tool_call_id]] = json.loads(message.content or "{}")
    return results


def _shop_notes(messages: Sequence[ChatMessage]) -> str:
    instructions = (messages[0].content or "") if messages else ""
    notes = instructions.split("Shop notes from the owner:", 1)[-1]
    return "" if notes.strip().startswith("(none") else notes


def _is_first_reply(messages: Sequence[ChatMessage]) -> bool:
    return not any(m.role == "assistant" and not m.tool_calls for m in messages)


def _wants_to_buy(text: str) -> bool:
    if _BUY.search(text):
        return True
    return bool(_AFFIRM.search(text)) and "?" not in text and len(text.split()) <= 6


def _named(deals: list[_Deal], text: str) -> _Deal | None:
    return next((d for d in deals if _name_in(d.name, text)), None)


def _name_in(name: str, text: str) -> bool:
    words = [w for w in re.findall(r"[a-z]+", name.lower()) if len(w) > 3]
    return any(w in text for w in words)


def _mentions_other_product(text: str, focus: _Deal) -> bool:
    """A question about something other than the deal's product (e.g. "do you sell earrings?")."""
    asks_about_range = re.search(r"\b(do you (?:sell|have)|anything else|other)\b", text)
    return bool(asks_about_range) and not _name_in(focus.name, text)


def _details(text: str) -> dict[str, str]:
    details: dict[str, str] = {}
    if size := _SIZE.search(text):
        raw = next(g for g in size.groups() if g)
        details["size"] = _SIZES.get(raw, raw.upper())
    if colour := _COLOUR.search(text):
        details["colour"] = colour.group(1)
    return details


def _quantity(text: str) -> int:
    match = _QUANTITY.search(text)
    if not match:
        return 1
    raw = next(g for g in match.groups() if g)
    return _NUMBERS.get(raw, int(raw) if raw.isdigit() else 1)


def _describe(details: dict[str, str]) -> str:
    return " ".join(f"{k} {v}" for k, v in details.items())


def _calls(*calls: tuple[str, dict[str, Any]]) -> AssistantTurn:
    return AssistantTurn(
        text=None, tool_calls=tuple(ToolCall(f"mock_{i}", name, args) for i, (name, args) in enumerate(calls))
    )
