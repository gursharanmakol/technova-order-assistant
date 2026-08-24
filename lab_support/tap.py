"""The official MCP client stdio transport, with a tap on its JSON-RPC messages.

The tap records each message object the SDK puts on, or takes off, the stdio
pipe, in the order it happens. It does not create, change, or drop any
protocol traffic. The server's own log goes to a separate file.
"""

from __future__ import annotations

import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, TextIO

from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.shared.message import SessionMessage

PROJECT_ROOT = Path(__file__).resolve().parents[1]

_REDACT_KEYS = {"authorization", "token", "api_key", "apikey", "password", "secret", "access_token"}


def server_parameters(module: str) -> StdioServerParameters:
    """Start the server module with this Python, from the project folder."""
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", module],
        cwd=PROJECT_ROOT,
        env={"PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"},
    )


@asynccontextmanager
async def traced_stdio(parameters: StdioServerParameters, events: list[dict[str, Any]], errlog: TextIO):
    async with stdio_client(parameters, errlog=errlog) as (read_stream, write_stream):
        yield _Tap(read_stream, "server_to_client", events), _Tap(write_stream, "client_to_server", events)


class _Tap:
    """Forward one stdio stream and record each message exactly once."""

    def __init__(self, inner: Any, direction: str, events: list[dict[str, Any]]) -> None:
        self._inner = inner
        self._direction = direction
        self._events = events

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def __aiter__(self) -> _Tap:
        return self

    async def __anext__(self) -> Any:
        item = await self._inner.__anext__()
        _record(self._events, self._direction, item)
        return item

    async def receive(self) -> Any:
        item = await self._inner.receive()
        _record(self._events, self._direction, item)
        return item

    async def send(self, item: Any) -> None:
        _record(self._events, self._direction, item)
        await self._inner.send(item)

    async def __aenter__(self) -> _Tap:
        await self._inner.__aenter__()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> Any:
        return await self._inner.__aexit__(exc_type, exc, tb)

    async def aclose(self) -> None:
        await self._inner.aclose()


def _record(events: list[dict[str, Any]], direction: str, item: Any) -> None:
    entry: dict[str, Any] = {"source": "wire", "direction": direction}
    if isinstance(item, Exception):
        entry["parse_error"] = f"{type(item).__name__}: {item}"
    elif not isinstance(item, SessionMessage):
        entry["unexpected_frame"] = type(item).__name__
    else:
        raw = item.message.model_dump_json(by_alias=True, exclude_unset=True)
        entry["message"] = sanitize(json.loads(raw))
    events.append(entry)


def sanitize(value: Any) -> Any:
    """Redact credential-shaped keys if a message ever contains one."""
    if isinstance(value, dict):
        return {
            key: "[redacted]" if key.lower() in _REDACT_KEYS else sanitize(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    return value
