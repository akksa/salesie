"""The Muse Spark client against Meta Model API's documented Chat Completions shapes (dev.meta.ai/docs).
httpx.MockTransport stands in for the network: the only double here."""

import json

import httpx
import pytest

from app.agent.llm import ChatMessage, LLMError, ToolCall, ToolSpec
from app.agent.muse import MuseClient

TOOLS = [
    ToolSpec(
        "get_product",
        "Get one product",
        {"type": "object", "properties": {"product_id": {"type": "integer"}}},
    )
]


def client_with(handler) -> MuseClient:
    return MuseClient(
        api_key="sk-test",
        base_url="https://api.meta.ai/v1",
        model="muse-spark-1.3",
        transport=httpx.MockTransport(handler),
    )


async def test_request_follows_the_chat_completions_format() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "Hi!"}}]})

    history = [
        ChatMessage("system", "You sell dresses"),
        ChatMessage("user", "price?"),
        ChatMessage("assistant", None, tool_calls=(ToolCall("call_1", "get_product", {"product_id": 7}),)),
        ChatMessage("tool", '{"price": "$68.00"}', tool_call_id="call_1"),
    ]
    turn = await client_with(handler).complete(history, TOOLS)

    [request] = captured
    assert str(request.url) == "https://api.meta.ai/v1/chat/completions"
    assert request.headers["authorization"] == "Bearer sk-test"
    body = json.loads(request.content)
    assert body["model"] == "muse-spark-1.3"
    assert body["tools"] == [
        {
            "type": "function",
            "function": {
                "name": "get_product",
                "description": "Get one product",
                "parameters": TOOLS[0].parameters,
            },
        }
    ]
    assistant = body["messages"][2]
    assert assistant["tool_calls"] == [
        {
            "id": "call_1",
            "type": "function",
            "function": {"name": "get_product", "arguments": '{"product_id": 7}'},
        }
    ]
    assert body["messages"][3] == {"role": "tool", "content": '{"price": "$68.00"}', "tool_call_id": "call_1"}
    assert "stop" not in body and "logit_bias" not in body  # rejected with 400 by Meta Model API
    assert turn.text == "Hi!"


async def test_reasoning_is_kept_low_so_the_reply_has_room() -> None:
    # Muse Spark always reasons, and reasoning counts against max_completion_tokens: at the default effort
    # a 1024-token budget ran out mid-thought on a real comment and the planning text went to the shopper.
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        choice = {"message": {"content": "Hi!"}, "finish_reason": "stop"}
        return httpx.Response(200, json={"choices": [choice]})

    await client_with(handler).complete([ChatMessage("user", "hi")], TOOLS)
    plain = MuseClient(
        api_key="k",
        base_url="https://inference.example/v1",
        model="m",
        reasoning_effort=None,  # for an endpoint that doesn't take the setting
        transport=httpx.MockTransport(handler),
    )
    await plain.complete([ChatMessage("user", "hi")], TOOLS)

    assert (bodies[0]["reasoning_effort"], bodies[0]["max_completion_tokens"]) == ("low", 4096)
    assert "reasoning_effort" not in bodies[1]


async def test_a_reply_cut_off_by_the_token_limit_is_never_used() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        cut = {"message": {"content": "Got it — I'll send the price and ask"}, "finish_reason": "length"}
        return httpx.Response(200, json={"choices": [cut]})

    with pytest.raises(LLMError) as raised:
        await client_with(handler).complete([ChatMessage("user", "price?")], TOOLS)
    assert raised.value.retryable is False  # the owner gets the chat; the shopper gets the holding message


async def test_tool_calls_are_parsed_from_json_string_arguments() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_a",
                    "type": "function",
                    "function": {"name": "get_product", "arguments": '{"product_id": 3}'},
                },
                {
                    "id": "call_b",
                    "type": "function",
                    "function": {"name": "get_product", "arguments": "not json"},
                },
            ],
        }
        usage = {"prompt_tokens": 120, "completion_tokens": 30, "total_tokens": 150}
        return httpx.Response(
            200, json={"choices": [{"message": message, "finish_reason": "tool_calls"}], "usage": usage}
        )

    turn = await client_with(handler).complete([ChatMessage("user", "hi")], TOOLS)
    assert turn.text is None
    assert turn.tool_calls[0] == ToolCall("call_a", "get_product", {"product_id": 3})
    assert turn.tool_calls[1].arguments == {"_unparseable_arguments": "not json"}
    assert turn.usage["total_tokens"] == 150


async def test_billing_errors_are_not_retried() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            402, json={"error": {"message": "Insufficient balance", "type": "billing_error"}}
        )

    with pytest.raises(LLMError) as raised:
        await client_with(handler).complete([ChatMessage("user", "hi")], TOOLS)
    assert calls == 1
    assert raised.value.retryable is False
    assert str(raised.value) == "billing: insufficient balance: Insufficient balance"


async def test_rate_limits_are_retried_after_the_advertised_delay() -> None:
    responses = [
        httpx.Response(429, headers={"retry-after": "0"}, json={"error": {"message": "slow down"}}),
        httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "ok"}}]}),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return responses.pop(0)

    turn = await client_with(handler).complete([ChatMessage("user", "hi")], TOOLS)
    assert turn.text == "ok"
    assert responses == []


async def test_a_response_without_choices_is_an_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": "x"})

    with pytest.raises(LLMError, match="no choices"):
        await client_with(handler).complete([ChatMessage("user", "hi")], TOOLS)


async def test_arguments_already_decoded_and_missing_ids_are_tolerated() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        call = {"type": "function", "function": {"name": "get_product", "arguments": {"product_id": 3}}}
        return httpx.Response(200, json={"choices": [{"message": {"content": None, "tool_calls": [call]}}]})

    turn = await client_with(handler).complete([ChatMessage("user", "hi")], TOOLS)
    assert turn.tool_calls == (ToolCall("call_0", "get_product", {"product_id": 3}),)


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, json={"choices": [{"message": None}]}),
        httpx.Response(200, json={"choices": [{"message": {"tool_calls": "nope"}}]}),
        httpx.Response(200, text="<html>gateway</html>"),
    ],
)
async def test_malformed_responses_become_model_errors(response: httpx.Response) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return response

    with pytest.raises(LLMError):
        await client_with(handler).complete([ChatMessage("user", "hi")], TOOLS)


async def test_nan_arguments_stay_strings() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        call = {
            "id": "c",
            "type": "function",
            "function": {"name": "search_catalog", "arguments": '{"query": NaN}'},
        }
        return httpx.Response(200, json={"choices": [{"message": {"tool_calls": [call]}}]})

    turn = await client_with(handler).complete([ChatMessage("user", "hi")], TOOLS)
    assert turn.tool_calls[0].arguments == {"query": "NaN"}
