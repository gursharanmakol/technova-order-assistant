"""A deterministic stand-in for a language model. It is NOT an LLM.

The lab uses it so every learner, on every machine, sees the same run. Like a
real model, it never talks to MCP and only sees what the Host gives it: the
question, the conversation so far, and the tool descriptions.

Rules, applied in order:
1. If the conversation has no tool result yet, pick one read-only tool:
   a. a tool whose description mentions "status", otherwise
   b. a tool whose description mentions "order".
   Call it with the order number from the question. One tool call per question.
2. Answer from the tool result. For anything the question asks about that the
   result does not contain, use the stand-in's default assumption, the way a
   real model can fill a gap with a confident guess.
3. If there is no order number in the question, ask for one.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from typing import Any

from assistant_host.model_api import (
    Message,
    ModelTurn,
    ToolCall,
    ToolResultMessage,
    ToolSpec,
    UserMessage,
)

STANDIN_NAME = "scripted-stand-in"
STANDIN_LABEL = "scripted-stand-in: a deterministic simulated model, not an LLM"

_ORDER_ID = re.compile(r"\bORD-[0-9]{5}\b")
_DEFAULT_STATUS = "is being prepared and should ship within 2 business days"


class ScriptedStandIn:
    name = STANDIN_NAME
    is_real_llm = False

    async def complete(
        self,
        system_prompt: str,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec],
    ) -> ModelTurn:
        order_id = _order_id(messages)
        if order_id is None:
            return ModelTurn(text="Please include your order number, for example ORD-10042.")

        results = [m for m in messages if isinstance(m, ToolResultMessage)]
        if not results:
            tool = _pick_tool(tools)
            if tool is not None:
                call = ToolCall(call_id="call_1", name=tool.name, arguments={"order_id": order_id})
                return ModelTurn(text=None, tool_calls=(call,))
            return ModelTurn(text=f"Your order {order_id} {_DEFAULT_STATUS}.")

        return ModelTurn(text=_answer(order_id, results[-1]))


def _order_id(messages: Sequence[Message]) -> str | None:
    for message in reversed(messages):
        if isinstance(message, UserMessage):
            match = _ORDER_ID.search(message.text)
            return match.group(0) if match else None
    return None


def _pick_tool(tools: Sequence[ToolSpec]) -> ToolSpec | None:
    readable = [tool for tool in tools if tool.read_only]
    for word in ("status", "order"):
        for tool in readable:
            if word in tool.description.lower():
                return tool
    return None


def _answer(order_id: str, result: ToolResultMessage) -> str:
    data = _parse(result.content)
    if result.is_error:
        reason = data.get("reason", "the lookup failed")
        return f"I could not look up order {order_id}: {reason}"
    if "status" in data:
        status = data["status"]
        if status == "shipped":
            return (
                f"Order {order_id} has shipped via {data.get('carrier')} and is expected "
                f"to arrive on {data.get('estimated_delivery')}."
            )
        if status == "canceled":
            return f"Order {order_id} was canceled."
        return f"Order {order_id} is {status}."
    if "items" in data:
        products = ", ".join(item.get("product", "?") for item in data["items"])
        return f"Your order {order_id} ({products}) {_DEFAULT_STATUS}."
    return f"Your order {order_id} {_DEFAULT_STATUS}."


def _parse(content: str) -> dict[str, Any]:
    try:
        value = json.loads(content)
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}
