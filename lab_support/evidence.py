"""Evidence from one real run, for your tests.

run_ask() asks the assistant one question exactly the way lab.py ask does:
it starts the real order service, talks to it over MCP, and runs the model.
It then gives you what was observed, one field per stage of the request path.

Everything comes from what actually happened in that run:
- discovered_tools, server_info and tool_calls come from the JSON-RPC messages
  the MCP client really sent and received. Each tools/call is matched to its
  response by the request id the two messages carried in this run.
- offered_tools and model_choices come from what the Host passed to the model
  and what the model returned.
- server_received comes from the order service's own log, written by the
  server process.

run_ask() does not touch the saved trace that lab.py trace shows.
"""

from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NamedTuple

import anyio

from assistant_host.host import run_question

_SERVER_LINE = re.compile(r"^received (?P<method>\S+)(?: name=(?P<name>\S+))? id=(?P<id>\S+)$")


@dataclass(frozen=True)
class ToolCallEvidence:
    """One tools/call request seen on the wire, with its matching response."""

    name: str  # tool named in the request
    arguments: dict[str, Any]  # arguments sent in the request
    request_id: str  # JSON-RPC id of the request in this run, as text
    responded: bool  # a response carrying the same id came back
    is_error: bool | None  # isError from that response (None if no response)
    structured: dict[str, Any] | None  # structuredContent from that response


class ServerReceipt(NamedTuple):
    """One request the order service logged as received."""

    method: str  # for example "tools/call"
    name: str | None  # tool name for tools/call, otherwise None
    request_id: str  # JSON-RPC id the server logged, as text


@dataclass(frozen=True)
class Run:
    question: str
    answer: str  # the final answer shown to the user
    server_info: dict[str, Any]  # name and version from the server/discover result
    discovered_tools: list[str]  # tool names in the server's tools/list result
    offered_tools: list[str]  # tool names in the Host's request to the model
    model_choices: list[dict[str, Any]]  # each {"name": ..., "arguments": ...} the model chose
    tool_calls: list[ToolCallEvidence]  # every tools/call on the wire, in order
    server_received: list[ServerReceipt]  # every request in the server's own log, in order

    def tool_call(self, name: str) -> ToolCallEvidence | None:
        """The first tools/call on the wire for this tool, or None if there was none."""
        return next((call for call in self.tool_calls if call.name == name), None)


def run_ask(question: str) -> Run:
    """Ask the assistant one question and return what was observed."""
    with tempfile.TemporaryDirectory(prefix="lab-evidence-") as folder:
        result = anyio.run(_run, question, Path(folder) / "server.log")
    return evidence_from(result)


async def _run(question: str, server_log: Path) -> Any:
    return await run_question(question, server_log_path=server_log)


def evidence_from(result: Any) -> Run:
    events = result.events
    wire = [(e["direction"], e["message"]) for e in events if e.get("source") == "wire" and "message" in e]
    requests = [m for d, m in wire if d == "client_to_server" and "method" in m and "id" in m]
    responses = {_text(m["id"]): m for d, m in wire if d == "server_to_client" and "id" in m and "method" not in m}

    def result_of(method: str) -> dict[str, Any]:
        request = next((m for m in requests if m["method"] == method), None)
        response = responses.get(_text(request["id"])) if request else None
        return (response or {}).get("result", {})

    host = [e for e in events if e.get("source") == "host"]
    first_request = next((e["payload"] for e in host if e.get("kind") == "request"), {})

    return Run(
        question=result.question,
        answer=result.answer,
        server_info=result_of("server/discover").get("_meta", {}).get("io.modelcontextprotocol/serverInfo", {}),
        discovered_tools=[tool["name"] for tool in result_of("tools/list").get("tools", [])],
        offered_tools=[tool["name"] for tool in first_request.get("tools", [])],
        model_choices=[
            {"name": e["payload"]["name"], "arguments": e["payload"]["arguments"]}
            for e in host
            if e.get("kind") == "tool_choice"
        ],
        tool_calls=[_call(m, responses) for m in requests if m["method"] == "tools/call"],
        server_received=_receipts(result.server_log),
    )


def _call(request: dict[str, Any], responses: dict[str, dict[str, Any]]) -> ToolCallEvidence:
    request_id = _text(request["id"])
    response = responses.get(request_id)
    outcome = (response or {}).get("result", {})
    params = request.get("params") or {}
    return ToolCallEvidence(
        name=params.get("name", ""),
        arguments=params.get("arguments") or {},
        request_id=request_id,
        responded=response is not None,
        is_error=outcome.get("isError") if response is not None else None,
        structured=outcome.get("structuredContent"),
    )


def _receipts(server_log: str) -> list[ServerReceipt]:
    receipts = []
    for line in server_log.splitlines():
        match = _SERVER_LINE.match(line.strip())
        if match:
            receipts.append(ServerReceipt(match["method"], match["name"], match["id"]))
    return receipts


def _text(value: Any) -> str:
    return str(value)
