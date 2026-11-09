"""Views of a saved run: a numbered timeline, and the full content of one event.

Event numbers follow the order in which events happened in that run. A
response is matched to its request by the JSON-RPC id the two messages carry,
whatever that id is.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lab_support.tap import PROJECT_ROOT

RUN_FILE = PROJECT_ROOT / "traces" / "last_run.jsonl"
SERVER_LOG = PROJECT_ROOT / "traces" / "server.log"

_PARTIES = {
    "client_to_server": "host -> server",
    "server_to_client": "server -> host",
    "host_to_model": "host -> model",
    "model_to_host": "model -> host",
}
_HOST_KINDS = {
    "request": "request",
    "tool_result": "tool result",
    "final_answer": "final answer",
}


def save_run(result: Any, path: Path = RUN_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = {
        "type": "run",
        "question": result.question,
        "answer": result.answer,
        "model": result.model_name,
        "real_llm": result.model_is_real_llm,
    }
    lines = [json.dumps(header, ensure_ascii=True)]
    lines += [json.dumps({"type": "event", **event}, ensure_ascii=True) for event in result.events]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_run(path: Path = RUN_FILE) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    header = next(record for record in records if record.get("type") == "run")
    events = [record for record in records if record.get("type") == "event"]
    return header, events


def describe(events: list[dict[str, Any]]) -> list[tuple[int, str, str]]:
    """One (number, parties, event) row per event, in the order they happened."""
    methods_by_id: dict[Any, str] = {}
    for event in events:
        message = event.get("message")
        if event.get("direction") == "client_to_server" and isinstance(message, dict):
            if "method" in message and "id" in message:
                methods_by_id[message["id"]] = message["method"]

    rows = []
    for number, event in enumerate(events, start=1):
        rows.append((number, _PARTIES.get(event.get("direction", ""), "?"), _what(event, methods_by_id)))
    return rows


def _what(event: dict[str, Any], methods_by_id: dict[Any, str]) -> str:
    if event.get("source") == "host":
        if event.get("kind") == "tool_choice":
            return f"tool choice: {event['payload'].get('name')}"
        return _HOST_KINDS.get(event.get("kind", ""), str(event.get("kind")))
    message = event.get("message")
    if not isinstance(message, dict):
        return "unreadable message"
    method = message.get("method")
    if method == "tools/call":
        return f"tools/call: {(message.get('params') or {}).get('name')}"
    if method:
        return method if "id" in message else f"notification {method}"
    request = methods_by_id.get(message.get("id"), "unknown request")
    return f"{request} error" if "error" in message else f"{request} result"


def render_trace(header: dict[str, Any], events: list[dict[str, Any]]) -> str:
    from lab_support.term import bold, dim

    columns = "   #  from -> to       event"
    hint = "Full content of one event: uv run python lab.py show <number>"
    lines = [
        "Trace of the last run",
        f"Question: {header['question']}",
        f"Model:    {_model_label(header)}",
        "",
        bold(columns),
    ]
    for number, parties, what in describe(events):
        lines.append(f"{number:>4}  {parties:<16} {what}")
    lines += ["", dim(hint)]
    return "\n".join(lines)


_SCHEMA_KEYS = {"inputSchema", "outputSchema", "input_schema", "$defs"}


def render_event(header: dict[str, Any], events: list[dict[str, Any]], number: int, brief: bool = False) -> str:
    from lab_support.term import bold, color_json, dim

    rows = describe(events)
    _, parties, what = rows[number - 1]
    event = events[number - 1]
    body = event.get("message") if event.get("source") == "wire" else event.get("payload")
    if body is None:
        body = {key: value for key, value in event.items() if key not in ("type", "source", "direction")}
    lines = [bold(f"Event {number}   {parties}   {what}")]
    if brief:
        body = _collapse_schemas(body)
        lines.append(dim("(schemas shown as {...}; run without --brief for the full content)"))
    dumped = json.dumps(body, indent=2, ensure_ascii=True)
    return "\n".join([*lines, "", color_json(dumped)])


def _collapse_schemas(value: Any) -> Any:
    """Same content, with every JSON schema replaced by {...}. Nothing else changes."""
    if isinstance(value, dict):
        return {key: "{...}" if key in _SCHEMA_KEYS else _collapse_schemas(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_collapse_schemas(item) for item in value]
    return value


def _model_label(header: dict[str, Any]) -> str:
    if header.get("real_llm"):
        return str(header.get("model"))
    return f"{header.get('model')} (a deterministic simulated model, not an LLM)"
