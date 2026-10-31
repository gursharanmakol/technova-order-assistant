"""Regression test for ticket SUP-2291.

Prove that the assistant's status answer is backed by a real MCP tool call,
and that the assistant still can never cancel orders.

How to work with this file:
1. Complete the TODOs.
2. Run the tests before your fix. They must fail.
3. Fix the root cause.
4. Run the tests again. They must pass.

Run with:  uv run python lab.py test

What run_ask() gives you (details in lab_support/evidence.py):
  run.answer              final answer shown to the user
  run.server_info         {"name": ..., "version": ...} from server/discover
  run.discovered_tools    tool names the server advertised in tools/list
  run.offered_tools       tool names the Host gave the model
  run.model_choices       [{"name": ..., "arguments": ...}] the model chose
  run.tool_calls          every tools/call on the wire, each with its response
  run.tool_call(name)     the tools/call for one tool, or None. Its fields:
                            .arguments .request_id .responded .is_error .structured
  run.server_received     requests the server logged: (method, name, request_id)
"""

import pytest

from lab_support.evidence import run_ask

QUESTION = "What is the status of order ORD-10042?"
ORDER_ID = "ORD-10042"
STATUS_TOOL = "get_order_status"
BLOCKED_TOOL = "cancel_order"


def test_status_answer_is_backed_by_a_real_tool_call():
    run = run_ask(QUESTION)

    # Worked example (discovery): the server advertised the tool a status question needs.
    assert STATUS_TOOL in run.discovered_tools

    # TODO 1 (exposure and selection): prove the Host gave the model that tool,
    # and the model chose it with this order's number.

    # TODO 2 (invocation): prove a tools/call for that tool crossed the wire,
    # and the server's own log received the same request id.

    # TODO 3 (result and grounding): prove that call came back successful with
    # structured data, and the answer states the status, carrier and delivery
    # date from that result. Compare against the result, not typed-in values.

    pytest.fail("Complete TODO 1 to 3 above, then delete this line.")


def test_assistant_never_offers_or_calls_cancel_order():
    run = run_ask(QUESTION)

    # TODO 4 (policy): prove the Host never gave BLOCKED_TOOL to the model,
    # no tools/call for it crossed the wire, and the server never received one.

    pytest.fail("Complete TODO 4 above, then delete this line.")
