"""Deterministic order records.

This module has no MCP or model dependency. Every new OrderStore starts from
the same seed. Reads never change a record. Only cancel_order can change one,
and only for an order that has not shipped.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

ORDER_ID = "ORD-10042"

_SEED_ORDERS: dict[str, dict[str, str]] = {
    ORDER_ID: {
        "order_id": ORDER_ID,
        "status": "shipped",
        "carrier": "FedEx",
        "shipped_on": "2026-10-29",
        "estimated_delivery": "2026-11-03",
    },
}

_SEED_ITEMS: dict[str, list[dict[str, Any]]] = {
    ORDER_ID: [
        {"product": "WH-1000 Headphones", "quantity": 1},
        {"product": "EB-20 Earbuds", "quantity": 1},
    ],
}

CANCELABLE_STATUSES = frozenset({"processing"})


@dataclass(frozen=True)
class ToolSuccess:
    payload: dict[str, Any]


@dataclass(frozen=True)
class ToolRejection:
    code: str
    reason: str
    details: dict[str, Any]


ToolOutcome = ToolSuccess | ToolRejection


class OrderStore:
    """In-memory copy of the order records."""

    def __init__(self) -> None:
        self.orders: dict[str, dict[str, str]] = copy.deepcopy(_SEED_ORDERS)
        self.items: dict[str, list[dict[str, Any]]] = copy.deepcopy(_SEED_ITEMS)

    def snapshot(self) -> dict[str, Any]:
        return {"orders": copy.deepcopy(self.orders), "items": copy.deepcopy(self.items)}

    def order_status(self, order_id: str) -> ToolOutcome:
        before = self.snapshot()
        order = self.orders.get(order_id)
        self._require_unchanged(before)
        if order is None:
            return _unknown(order_id)
        return ToolSuccess(payload=copy.deepcopy(order))

    def order_items(self, order_id: str) -> ToolOutcome:
        before = self.snapshot()
        items = self.items.get(order_id)
        self._require_unchanged(before)
        if items is None:
            return _unknown(order_id)
        return ToolSuccess(payload={"order_id": order_id, "items": copy.deepcopy(items)})

    def cancel_order(self, order_id: str) -> ToolOutcome:
        before = self.snapshot()
        order = self.orders.get(order_id)
        if order is None:
            self._require_unchanged(before)
            return _unknown(order_id)
        if order["status"] not in CANCELABLE_STATUSES:
            self._require_unchanged(before)
            return ToolRejection(
                code="not_cancelable",
                reason=f"Order {order_id} is already {order['status']} and cannot be canceled.",
                details={"order_id": order_id, "status": order["status"]},
            )
        previous = order["status"]
        order["status"] = "canceled"
        return ToolSuccess(
            payload={"order_id": order_id, "previous_status": previous, "status": "canceled", "mutated": True}
        )

    def _require_unchanged(self, before: dict[str, Any]) -> None:
        if self.snapshot() != before:
            raise RuntimeError("Order records changed during a read or a rejection.")


def _unknown(order_id: str) -> ToolRejection:
    return ToolRejection(
        code="unknown_order",
        reason=f"No order exists with number {order_id}.",
        details={"order_id": order_id},
    )
