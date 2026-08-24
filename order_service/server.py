"""TechNova order service, an MCP server over stdio.

stdout carries the MCP stdio transport, so the server never prints to it.
Its own log (startup and every request it receives) goes to stderr.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Annotated, Any, Literal

import anyio
from mcp.server import MCPServer
from mcp.types import CallToolResult, TextContent, ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field, RootModel

from order_service import __version__
from order_service.store import OrderStore, ToolOutcome, ToolRejection, ToolSuccess

SERVER_NAME = "order-service"

_STORE = OrderStore()
_LOG = logging.getLogger("order_service")


async def _log_requests(ctx: Any, call_next: Any) -> Any:
    """Record every request this server receives, before it is handled."""
    if ctx.request_id is not None:
        params = ctx.params if isinstance(ctx.params, dict) else {}
        name = params.get("name") if ctx.method == "tools/call" else None
        target = f" name={name}" if name else ""
        _LOG.info("received %s%s id=%s", ctx.method, target, ctx.request_id)
    return await call_next(ctx)


server = MCPServer(
    SERVER_NAME,
    version=__version__,
    instructions="Order lookups for TechNova support tools. All records are synthetic.",
    middleware=[_log_requests],
)


class OrderStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id: str
    status: str
    carrier: str
    shipped_on: str
    estimated_delivery: str


class OrderItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product: str
    quantity: int


class OrderItems(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id: str
    items: list[OrderItem]


class CancelConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id: str
    previous_status: str
    status: str
    mutated: bool


class _Rejection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: Literal["rejected"]
    reason: str
    mutated: Literal[False]


class UnknownOrderRejection(_Rejection):
    code: Literal["unknown_order"]
    order_id: str


class NotCancelableRejection(_Rejection):
    code: Literal["not_cancelable"]
    order_id: str
    status: str


# Clients may validate isError results against outputSchema too, so each schema
# also describes the rejections its tool can return. The root stays an object.
_OBJECT_ROOT = ConfigDict(json_schema_extra={"type": "object"})


class OrderStatusResult(RootModel[OrderStatus | UnknownOrderRejection]):
    model_config = _OBJECT_ROOT


class OrderItemsResult(RootModel[OrderItems | UnknownOrderRejection]):
    model_config = _OBJECT_ROOT


class CancelOrderResult(RootModel[CancelConfirmation | UnknownOrderRejection | NotCancelableRejection]):
    model_config = _OBJECT_ROOT


OrderId = Annotated[
    str,
    Field(
        description="Order number, for example ORD-10042.",
        min_length=9,
        max_length=9,
        pattern=r"^ORD-[0-9]{5}$",
    ),
]

_READ_ONLY = ToolAnnotations(readOnlyHint=True)
_DESTRUCTIVE = ToolAnnotations(readOnlyHint=False, destructiveHint=True)


def _call_result(outcome: ToolOutcome) -> CallToolResult:
    if isinstance(outcome, ToolRejection):
        body: dict[str, object] = {
            "outcome": "rejected",
            "code": outcome.code,
            "reason": outcome.reason,
            "mutated": False,
            **outcome.details,
        }
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(body))],
            structured_content=body,
            is_error=True,
        )
    if not isinstance(outcome, ToolSuccess):
        raise RuntimeError("Tool returned an unknown outcome.")
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(outcome.payload))],
        structured_content=outcome.payload,
        is_error=False,
    )


@server.tool(annotations=_READ_ONLY)
def lookup_order(order_id: OrderId) -> Annotated[CallToolResult, OrderStatusResult]:
    """Return the current status, carrier, and estimated delivery date for an order."""
    return _call_result(_STORE.order_status(order_id))


@server.tool(annotations=_READ_ONLY)
def list_order_items(order_id: OrderId) -> Annotated[CallToolResult, OrderItemsResult]:
    """List the products and quantities in an order."""
    return _call_result(_STORE.order_items(order_id))


@server.tool(annotations=_DESTRUCTIVE)
def cancel_order(order_id: OrderId) -> Annotated[CallToolResult, CancelOrderResult]:
    """Cancel an order that has not shipped."""
    return _call_result(_STORE.cancel_order(order_id))


def _configure_log() -> None:
    _LOG.handlers.clear()
    _LOG.propagate = False
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(message)s"))
    _LOG.addHandler(handler)
    _LOG.setLevel(logging.INFO)


def main() -> None:
    _configure_log()
    _LOG.info("%s %s started pid=%s", SERVER_NAME, __version__, os.getpid())
    anyio.run(server.run_stdio_async)


if __name__ == "__main__":
    main()
