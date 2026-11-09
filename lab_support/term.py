"""Terminal presentation for the MCP lab: color and a trailing blank line.

Presentation applies only when stdout is a TTY, NO_COLOR is unset, and TERM
is not dumb. On Windows, virtual terminal processing is enabled with ctypes.
Every other case (pipes, redirects, tests, scripts) stays plain text.
"""

from __future__ import annotations

import os
import re
import sys

_CSI = "\x1b["
_RESET = _CSI + "0m"
_BOLD = _CSI + "1m"
_DIM = _CSI + "2m"
_RED = _CSI + "31m"
_GREEN = _CSI + "32m"
_YELLOW = _CSI + "33m"
_BLUE = _CSI + "34m"

_TAG_RE = re.compile(r"^\[(OK|WARN|FAIL)\]")
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def presentation() -> bool:
    if "NO_COLOR" in os.environ or os.environ.get("TERM") == "dumb":
        return False
    if not sys.stdout.isatty():
        return False
    return _enable_vt()


def _enable_vt() -> bool:
    if sys.platform != "win32":
        return True
    try:
        import ctypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel.GetStdHandle(-11)
        mode = ctypes.c_uint()
        if kernel.GetConsoleMode(handle, ctypes.byref(mode)) == 0:
            return False
        if kernel.SetConsoleMode(handle, mode.value | 0x0004) == 0:
            return False
    except (AttributeError, OSError):
        return False
    return True


def finish() -> None:
    """One trailing blank line after a presented command."""
    if presentation():
        sys.stdout.write("\n")
        sys.stdout.flush()


def bold(text: str) -> str:
    if not presentation():
        return text
    return _BOLD + text + _RESET


def dim(text: str) -> str:
    if not presentation():
        return text
    return _DIM + text + _RESET


def paint_check_line(line: str) -> str:
    """Color only the [OK]/[WARN]/[FAIL] tag; bold a Ready. line."""
    if not presentation():
        return line
    match = _TAG_RE.match(line)
    if match:
        tag = match.group(0)
        color = {"[OK]": _GREEN, "[WARN]": _YELLOW, "[FAIL]": _RED}[tag]
        return color + tag + _RESET + line[len(tag) :]
    if line.startswith("Ready."):
        return _BOLD + line + _RESET
    return line


def color_json(text: str) -> str:
    """Syntax-color a json.dumps result by token type only."""
    if not presentation():
        return text
    out: list[str] = []
    i = 0
    n = len(text)
    # stack entries: "object-key", "object-value", "array"
    stack: list[str] = []

    while i < n:
        ch = text[i]
        if ch in " \t\r\n":
            out.append(ch)
            i += 1
            continue
        if ch == "{":
            stack.append("object-key")
            out.append(ch)
            i += 1
            continue
        if ch == "[":
            stack.append("array")
            out.append(ch)
            i += 1
            continue
        if ch == "}":
            if stack and stack[-1].startswith("object"):
                stack.pop()
            out.append(ch)
            i += 1
            continue
        if ch == "]":
            if stack and stack[-1] == "array":
                stack.pop()
            out.append(ch)
            i += 1
            continue
        if ch == ",":
            if stack and stack[-1] == "object-value":
                stack[-1] = "object-key"
            out.append(ch)
            i += 1
            continue
        if ch == ":":
            if stack and stack[-1] == "object-key":
                stack[-1] = "object-value"
            out.append(ch)
            i += 1
            continue
        if ch == '"':
            end = _string_end(text, i)
            token = text[i:end]
            role = stack[-1] if stack else "array"
            if role == "object-key":
                out.append(_BOLD + _BLUE + token + _RESET)
            elif token == '"{...}"':
                out.append(_DIM + token + _RESET)
            else:
                out.append(_GREEN + token + _RESET)
            i = end
            continue
        if ch.isdigit() or (ch == "-" and i + 1 < n and text[i + 1].isdigit()):
            end = i + 1
            while end < n and (text[end].isdigit() or text[end] in ".eE+-"):
                end += 1
            out.append(_YELLOW + text[i:end] + _RESET)
            i = end
            continue
        if text.startswith("true", i):
            out.append(_YELLOW + "true" + _RESET)
            i += 4
            continue
        if text.startswith("false", i):
            out.append(_YELLOW + "false" + _RESET)
            i += 5
            continue
        if text.startswith("null", i):
            out.append(_YELLOW + "null" + _RESET)
            i += 4
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _string_end(text: str, start: int) -> int:
    i = start + 1
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "\\":
            i += 2
            continue
        if ch == '"':
            return i + 1
        i += 1
    return n


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)
