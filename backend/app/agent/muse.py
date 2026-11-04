"""Muse Spark over an OpenAI-compatible Chat Completions endpoint.

Meta Model API: POST https://api.meta.ai/v1/chat/completions, `Authorization: Bearer $MODEL_API_KEY`,
model e.g. "muse-spark-1.3" (dev.meta.ai/docs/protocols/chat-completions). Tool calls come back as
choices[0].message.tool_calls[] with `function.arguments` as a JSON string; results go back as
role "tool" messages with tool_call_id. Errors: 402 = billing, 429/503 = retry later.
The same client serves Muse Spark Open on Baseten (https://inference.baseten.co/v1).
"""

import asyncio
import json
from collections.abc import Sequence
from typing import Any

import httpx

from app.agent.llm import AssistantTurn, ChatMessage, LLMError, ToolCall, ToolSpec
from app.sanitize import redact

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_MAX_ATTEMPTS = 3
_MAX_BACKOFF_SECONDS = 10.0


class MuseClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float = 60.0,
        reasoning_effort: str | None = "low",
        max_completion_tokens: int = 4096,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._model = model
        self._api_key = api_key
        # Muse Spark always reasons, and reasoning counts against max_completion_tokens. "low" halves reply
        # time and keeps the budget for the reply; None omits the setting (endpoints that don't take it).
        self._reasoning_effort = reasoning_effort
        self._max_completion_tokens = max_completion_tokens
        self._http = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
            transport=transport,
        )

    @property
    def model_name(self) -> str:
        return self._model

    async def aclose(self) -> None:
        await self._http.aclose()

    async def complete(self, messages: Sequence[ChatMessage], tools: Sequence[ToolSpec]) -> AssistantTurn:
        body: dict[str, Any] = {
            "model": self._model,
            "messages": [_message_json(m) for m in messages],
            "max_completion_tokens": self._max_completion_tokens,
        }
        if self._reasoning_effort:
            body["reasoning_effort"] = self._reasoning_effort
        if tools:
            body["tools"] = [_tool_json(t) for t in tools]
        data = await self._post_with_retry(body)
        return _parse_turn(data)

    async def _post_with_retry(self, body: dict[str, Any]) -> object:
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                response = await self._http.post("/chat/completions", json=body)
            except httpx.HTTPError as exc:
                if attempt == _MAX_ATTEMPTS:
                    raise LLMError(f"model request failed: {type(exc).__name__}", retryable=True) from exc
                await asyncio.sleep(min(2**attempt, _MAX_BACKOFF_SECONDS))
                continue
            if response.status_code < 400:
                try:
                    return response.json()
                except ValueError as exc:  # e.g. an HTML page from a gateway with status 200
                    raise LLMError("model response is not JSON", retryable=True) from exc
            error = redact(_error_message(response), [self._api_key])
            if response.status_code not in _RETRYABLE_STATUS or attempt == _MAX_ATTEMPTS:
                raise LLMError(error, retryable=response.status_code in _RETRYABLE_STATUS)
            await asyncio.sleep(_retry_after(response, attempt))
        raise LLMError("model request failed", retryable=True)  # unreachable; keeps type checkers happy


def _message_json(message: ChatMessage) -> dict[str, Any]:
    out: dict[str, Any] = {"role": message.role, "content": message.content}
    if message.tool_calls:
        out["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.name, "arguments": json.dumps(call.arguments)},
            }
            for call in message.tool_calls
        ]
    if message.tool_call_id:
        out["tool_call_id"] = message.tool_call_id
    return out


def _tool_json(tool: ToolSpec) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {"name": tool.name, "description": tool.description, "parameters": tool.parameters},
    }


def _parse_turn(data: object) -> AssistantTurn:
    """Parse an OpenAI-shaped completion. Anything malformed becomes an LLMError, never a crash."""
    try:
        choice = data["choices"][0]  # type: ignore[index]
        message = choice["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError("model response has no choices[0].message", retryable=False) from exc
    if isinstance(choice, dict) and choice.get("finish_reason") == "length":
        # Cut off mid-reply: what's there is half a sentence or the model's own planning, never a message
        raise LLMError("the model ran out of output tokens before finishing its reply", retryable=False)
    if not isinstance(message, dict):
        raise LLMError("model response message is not an object", retryable=False)
    raw_calls = message.get("tool_calls") or []
    if not isinstance(raw_calls, list):
        raise LLMError("model response tool_calls is not a list", retryable=False)
    calls = tuple(_parse_call(index, raw) for index, raw in enumerate(raw_calls))
    usage_raw = data.get("usage") if isinstance(data, dict) else None
    usage = (
        {k: v for k, v in (usage_raw or {}).items() if isinstance(v, int)}
        if isinstance(usage_raw, dict)
        else {}
    )
    content = message.get("content")
    return AssistantTurn(text=content if isinstance(content, str) else None, tool_calls=calls, usage=usage)


def _parse_call(index: int, raw: object) -> ToolCall:
    raw = raw if isinstance(raw, dict) else {}
    function_raw = raw.get("function")
    function: dict[str, Any] = function_raw if isinstance(function_raw, dict) else {}
    arguments: object = function.get("arguments") or {}
    if isinstance(arguments, str):  # the documented form: a JSON-encoded string
        try:
            arguments = json.loads(arguments, parse_constant=lambda name: name)  # NaN/Infinity stay strings
        except json.JSONDecodeError:
            arguments = {"_unparseable_arguments": arguments}
    if not isinstance(arguments, dict):
        arguments = {"_unparseable_arguments": arguments}
    call_id = raw.get("id")
    return ToolCall(
        id=call_id if isinstance(call_id, str) and call_id else f"call_{index}",  # the reply must echo an id
        name=str(function.get("name", "")),
        arguments=arguments,
    )


def _error_message(response: httpx.Response) -> str:
    try:
        message = response.json()["error"]["message"]
    except (ValueError, KeyError, TypeError):
        message = response.text[:200]
    labels = {401: "invalid API key", 402: "billing: insufficient balance", 429: "rate limited"}
    label = labels.get(response.status_code, f"HTTP {response.status_code}")
    return f"{label}: {message}"


def _retry_after(response: httpx.Response, attempt: int) -> float:
    header = response.headers.get("retry-after", "")
    if header.isdigit():
        return min(float(header), _MAX_BACKOFF_SECONDS)
    return min(2.0**attempt, _MAX_BACKOFF_SECONDS)
