"""Types passed between the Host and a model.

A model never talks to MCP. It sees only the question, the conversation so far,
and the tool descriptions the Host gives it. It answers with either tool choices
or a final text answer. The Host turns tool choices into MCP calls.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol


@dataclass(frozen=True)
class ToolSpec:
    """One tool, as the server described it in tools/list."""

    name: str
    description: str
    input_schema: dict[str, Any]
    read_only: bool


@dataclass(frozen=True)
class ToolCall:
    """A tool choice returned by the model."""

    call_id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class UserMessage:
    text: str
    role: Literal["user"] = "user"


@dataclass(frozen=True)
class AssistantMessage:
    text: str | None
    tool_calls: tuple[ToolCall, ...] = ()
    role: Literal["assistant"] = "assistant"


@dataclass(frozen=True)
class ToolResultMessage:
    """A tool result handed back to the model, with isError preserved."""

    call_id: str
    name: str
    content: str
    is_error: bool
    role: Literal["tool"] = "tool"


Message = UserMessage | AssistantMessage | ToolResultMessage


@dataclass(frozen=True)
class ModelTurn:
    """One model response: tool choices or a final text answer."""

    text: str | None
    tool_calls: tuple[ToolCall, ...] = ()
    usage: dict[str, int] = field(default_factory=dict)


class Model(Protocol):
    name: str
    is_real_llm: bool

    async def complete(
        self,
        system_prompt: str,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec],
    ) -> ModelTurn: ...
