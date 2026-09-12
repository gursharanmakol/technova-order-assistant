"""The support assistant (the Host).

For each question it starts the order service, connects to it as an MCP
client, discovers its tools, gives the model the tools this deployment uses,
runs the model's tool choices through the MCP client, and returns the model's
final answer. Every step is recorded, in order, for the trace.
"""

from __future__ import annotations

import json
import tomllib
from contextlib import AsyncExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import anyio
from mcp import Client
from mcp.types import CallToolResult, Implementation, TextContent

from assistant_host import __version__
from assistant_host.model_api import (
    AssistantMessage,
    Message,
    Model,
    ToolCall,
    ToolResultMessage,
    ToolSpec,
    UserMessage,
)
from assistant_host.model_standin import ScriptedStandIn
from lab_support.tap import PROJECT_ROOT, server_parameters, traced_stdio

CONFIG_PATH = Path(__file__).with_name("host.toml")
SYSTEM_PROMPT = (
    "You are TechNova's order assistant. Answer customer questions about their orders "
    "in one or two sentences. Use the provided tools when they help."
)
MAX_MODEL_TURNS = 4
READ_TIMEOUT_SECONDS = 20.0
RUN_TIMEOUT_SECONDS = 60.0


class HostError(RuntimeError):
    pass


@dataclass
class HostConfig:
    server_module: str
    model_name: str
    tools: list[str]


@dataclass
class RunResult:
    question: str
    answer: str
    model_name: str
    model_is_real_llm: bool
    events: list[dict[str, Any]]
    server_log: str


def load_config(path: Path = CONFIG_PATH) -> HostConfig:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return HostConfig(
        server_module=data["server"]["orders"]["module"],
        model_name=data["model"]["name"],
        tools=list(data["tools"]["allowed"]),
    )


def make_model(name: str) -> Model:
    if name == "scripted-stand-in":
        return ScriptedStandIn()
    raise HostError(f"Unknown model {name!r} in host.toml.")


def tool_specs(tools: list[Any]) -> list[ToolSpec]:
    specs = []
    for tool in tools:
        annotations = tool.annotations
        read_only = bool(annotations and annotations.read_only_hint)
        specs.append(ToolSpec(tool.name, tool.description or "", tool.input_schema, read_only))
    return specs


def tool_result_for_model(call: ToolCall, result: CallToolResult) -> ToolResultMessage:
    if result.structured_content is not None:
        content = json.dumps(result.structured_content, separators=(",", ":"))
    else:
        content = "\n".join(block.text for block in result.content if isinstance(block, TextContent))
    return ToolResultMessage(call.call_id, call.name, content, bool(result.is_error))


def _spec_dict(spec: ToolSpec) -> dict[str, Any]:
    return {
        "name": spec.name,
        "description": spec.description,
        "input_schema": spec.input_schema,
        "read_only": spec.read_only,
    }


def _host_event(events: list[dict[str, Any]], direction: str, kind: str, payload: dict[str, Any]) -> None:
    events.append({"source": "host", "direction": direction, "kind": kind, "payload": payload})


async def run_question(
    question: str,
    *,
    config: HostConfig | None = None,
    model: Model | None = None,
    server_log_path: Path | None = None,
) -> RunResult:
    config = config or load_config()
    model = model or make_model(config.model_name)
    server_log_path = server_log_path or PROJECT_ROOT / "traces" / "server.log"
    server_log_path.parent.mkdir(parents=True, exist_ok=True)

    events: list[dict[str, Any]] = []
    with anyio.fail_after(RUN_TIMEOUT_SECONDS):
        async with AsyncExitStack() as stack:
            errlog = stack.enter_context(server_log_path.open("w", encoding="utf-8"))
            client = await stack.enter_async_context(
                Client(
                    traced_stdio(server_parameters(config.server_module), events, errlog),
                    mode="auto",
                    read_timeout_seconds=READ_TIMEOUT_SECONDS,
                    cache=None,
                    client_info=Implementation(name="technova-order-assistant", version=__version__),
                )
            )
            listing = await client.list_tools()
            discovered = tool_specs(listing.tools)
            for_model = [spec for spec in discovered if spec.name in config.tools]
            answer = await _converse(client, model, question, for_model, events)

    return RunResult(
        question=question,
        answer=answer,
        model_name=model.name,
        model_is_real_llm=model.is_real_llm,
        events=events,
        server_log=server_log_path.read_text(encoding="utf-8"),
    )


async def _converse(
    client: Client,
    model: Model,
    question: str,
    tools: list[ToolSpec],
    events: list[dict[str, Any]],
) -> str:
    history: list[Message] = [UserMessage(question)]
    tool_names = {spec.name for spec in tools}
    tool_payload = [_spec_dict(spec) for spec in tools]
    pending: list[ToolResultMessage] = []

    for turn_number in range(MAX_MODEL_TURNS):
        if turn_number == 0:
            _host_event(events, "host_to_model", "request",
                        {"system": SYSTEM_PROMPT, "question": question, "tools": tool_payload})
        else:
            _host_event(events, "host_to_model", "tool_result",
                        {"tool_results": [vars(r) for r in pending], "tools": tool_payload})
        pending = []

        turn = await model.complete(SYSTEM_PROMPT, list(history), list(tools))
        history.append(AssistantMessage(text=turn.text, tool_calls=turn.tool_calls))

        if not turn.tool_calls:
            if not turn.text:
                raise HostError("The model returned neither a tool choice nor an answer.")
            _host_event(events, "model_to_host", "final_answer",
                        {"model": model.name, "real_llm": model.is_real_llm, "text": turn.text})
            return turn.text

        for call in turn.tool_calls:
            _host_event(events, "model_to_host", "tool_choice",
                        {"model": model.name, "real_llm": model.is_real_llm,
                         "call_id": call.call_id, "name": call.name, "arguments": call.arguments})
            if call.name in tool_names:
                result = await client.call_tool(call.name, call.arguments)
                message = tool_result_for_model(call, result)
            else:
                message = ToolResultMessage(
                    call.call_id,
                    call.name,
                    json.dumps({"outcome": "rejected",
                                "reason": f"Tool {call.name!r} is not available to this assistant."}),
                    True,
                )
            pending.append(message)
            history.append(message)

    raise HostError("The model did not produce a final answer.")
