"""TechNova order assistant: command-line entry point for the MCP lab.

Commands:
  check                 confirm your setup
  ask "<question>"      ask the assistant a question
  trace                 numbered timeline of the last run
  show <number>         full content of one event from the last run
                        (add --brief to show JSON schemas as {...})
  server-log            the order service's own log from the last run
  test                  run your regression test in tests/
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from lab_support.term import bold, dim, finish, paint_check_line

MIN_PYTHON = (3, 12)
TESTED_MCP = "2.3.0"
EXAMPLE = 'uv run python lab.py ask "What is the status of order ORD-10042?"'


def _emit(text: str = "") -> None:
    print(text)


def _fail(message: str) -> int:
    _emit(paint_check_line(message) if message.startswith("[FAIL]") else message)
    finish()
    return 1


def cmd_check() -> int:
    _emit("TechNova order assistant: MCP lab")
    version = ".".join(str(part) for part in sys.version_info[:3])
    if sys.version_info[:2] < MIN_PYTHON:
        _emit(paint_check_line(f"[FAIL] Python {version}. This lab needs Python 3.12 or newer."))
        finish()
        return 1
    _emit(paint_check_line(f"[OK] Python {version}"))

    try:
        from importlib.metadata import version as package_version

        mcp_version = package_version("mcp")
    except Exception:  # noqa: BLE001 - reported to the learner
        _emit(paint_check_line("[FAIL] The mcp package is not installed. See the setup steps in the README."))
        finish()
        return 1
    if mcp_version == TESTED_MCP:
        _emit(paint_check_line(f"[OK] mcp {mcp_version}"))
    else:
        _emit(
            paint_check_line(
                f"[WARN] mcp {mcp_version} installed, the lab was tested with {TESTED_MCP}. Output may differ."
            )
        )

    try:
        from order_service import __version__ as service_version
        from order_service.server import SERVER_NAME
        from order_service.store import OrderStore

        orders = len(OrderStore().orders)
    except Exception as exc:  # noqa: BLE001 - reported to the learner
        _emit(paint_check_line(f"[FAIL] The order service did not load: {type(exc).__name__}: {exc}"))
        finish()
        return 1
    _emit(paint_check_line(f"[OK] Order service: {SERVER_NAME} {service_version}"))
    _emit(paint_check_line(f"[OK] Order records: {orders}"))

    try:
        from assistant_host.host import load_config

        load_config()
    except Exception as exc:  # noqa: BLE001 - reported to the learner
        _emit(paint_check_line(f"[FAIL] The assistant configuration did not load: {type(exc).__name__}: {exc}"))
        finish()
        return 1
    _emit(paint_check_line("[OK] Assistant configuration"))
    _emit(paint_check_line(f"Ready. Next: {EXAMPLE}"))
    finish()
    return 0


def cmd_ask(question: str) -> int:
    import anyio

    from assistant_host.host import run_question
    from lab_support.timeline import save_run

    result = anyio.run(run_question, question)
    save_run(result)
    _emit(result.answer)
    _emit()
    if not result.model_is_real_llm:
        note = f"(answered by {result.model_name}: a deterministic simulated model, not an LLM)"
        _emit(dim(note))
    finish()
    return 0


def _load_last_run():
    from lab_support.timeline import RUN_FILE, load_run

    if not RUN_FILE.exists():
        return None, f"[FAIL] No saved run yet. First run: {EXAMPLE}"
    return load_run(RUN_FILE), None


def cmd_trace() -> int:
    from lab_support.timeline import render_trace

    run, err = _load_last_run()
    if err is not None:
        return _fail(err)
    _emit(render_trace(*run))
    finish()
    return 0


def cmd_show(number: int, brief: bool) -> int:
    from lab_support.timeline import render_event

    run, err = _load_last_run()
    if err is not None:
        return _fail(err)
    header, events = run
    if not 1 <= number <= len(events):
        return _fail(f"[FAIL] No event {number}. The last run has events 1 to {len(events)}.")
    _emit(render_event(header, events, number, brief=brief))
    finish()
    return 0


def cmd_test() -> int:
    root = Path(__file__).resolve().parent
    return subprocess.call([sys.executable, "-m", "pytest", "tests"], cwd=root)


def cmd_server_log() -> int:
    from lab_support.timeline import SERVER_LOG

    if not SERVER_LOG.exists():
        return _fail(f"[FAIL] No server log yet. First run: {EXAMPLE}")
    header = "Order service log from the last run (written by the server process itself)"
    _emit(bold(header))
    _emit()
    _emit(SERVER_LOG.read_text(encoding="utf-8").rstrip())
    finish()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lab.py", description="TechNova order assistant: MCP lab")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="confirm your setup")
    ask = commands.add_parser("ask", help="ask the assistant a question")
    ask.add_argument("question")
    commands.add_parser("trace", help="numbered timeline of the last run")
    show = commands.add_parser("show", help="full content of one event from the last run")
    show.add_argument("number", type=int)
    show.add_argument("--brief", action="store_true", help="show JSON schemas as {...}")
    commands.add_parser("server-log", help="the order service's own log from the last run")
    commands.add_parser("test", help="run your regression test in tests/")
    args = parser.parse_args(argv)

    if args.command == "check":
        return cmd_check()
    if args.command == "ask":
        return cmd_ask(args.question)
    if args.command == "trace":
        return cmd_trace()
    if args.command == "show":
        return cmd_show(args.number, args.brief)
    if args.command == "test":
        return cmd_test()
    return cmd_server_log()


if __name__ == "__main__":
    raise SystemExit(main())
