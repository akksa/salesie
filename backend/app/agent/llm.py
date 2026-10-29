"""Provider-neutral chat types. The agent runtime only talks to LLMClient, so the deterministic mock and
Muse Spark (Meta Model API, or Muse Spark Open on Baseten) are interchangeable."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

Role = Literal["system", "user", "assistant", "tool"]


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ChatMessage:
    role: Role
    content: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class AssistantTurn:
    text: str | None
    tool_calls: tuple[ToolCall, ...] = ()
    usage: dict[str, int] = field(default_factory=dict)


class LLMError(Exception):
    """The model call failed. `retryable` is False for auth, billing and bad-request errors."""

    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


class LLMClient(Protocol):
    @property
    def model_name(self) -> str: ...

    async def complete(self, messages: Sequence[ChatMessage], tools: Sequence[ToolSpec]) -> AssistantTurn: ...
