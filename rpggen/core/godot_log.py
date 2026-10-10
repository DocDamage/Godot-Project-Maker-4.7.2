from __future__ import annotations

import re
from dataclasses import dataclass

from rpggen.errors import Issue, IssueList

# CSI sequences (colours, cursor moves) and the two-character escapes a terminal understands
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b[@-Z\\-_]")


def strip_ansi(text: str) -> str:
    """``text`` without terminal escape sequences (Godot colours its errors and rich prints)."""
    return ANSI_RE.sub("", text) if "\x1b" in text else text


MARKERS = ("SCRIPT ERROR:", "Parse Error:", "ERROR:", "[RPG-")

# Substrings of log lines that are known to be harmless and must not fail a run.
# Every entry needs a comment explaining why it is ignored.
IGNORED_ERROR_PATTERNS: list[str] = []


def scan(log_text: str) -> list[Issue]:
    """Turn runtime problems found in a Godot log into VAL-013 issues (one per offending line)."""
    issues = IssueList()
    for raw in log_text.splitlines():
        line = raw.strip()
        if not line or not any(m in line for m in MARKERS):
            continue
        if any(pat in line for pat in IGNORED_ERROR_PATTERNS):
            continue
        issues.add("VAL-013", line=line[:300])
    return list(issues)


# --------------------------------------------------------------------------- the cause (T15.21)

ERROR_PREFIXES = ("SCRIPT ERROR:", "USER SCRIPT ERROR:", "USER ERROR:", "ERROR:", "Parser Error:")
_RES_PATH = re.compile(r"(res://[^\s:)\]\"']+)(?::(\d+))?")
TAIL_LINES = 30  # how much of a failed phase's log the Results page shows


@dataclass(frozen=True)
class GodotError:
    """The first error of a Godot log: what Godot said, and where when it named a place."""

    message: str  # the line without its "ERROR:" prefix
    path: str | None = None  # a res:// path the error names
    line: int | None = None  # the line in that file
    raw: str = ""  # the log line as it was printed

    def sentence(self) -> str:
        """ "Parse Error: Expected parameter name. (line 3 of res://x.gd)"."""
        if self.path and self.line:
            return f"{self.message} (line {self.line} of {self.path})"
        if self.path and self.path not in self.message:
            return f"{self.message} ({self.path})"
        return self.message


def first_error(text: str) -> GodotError | None:
    """The first ``ERROR:`` / ``SCRIPT ERROR:`` / ``Parser Error:`` line of a Godot log (a line
    with "Parse Error" counts whatever it starts with). The place is read from the line itself
    or from the ``at:`` lines Godot prints under it; a place inside the engine's own source
    (``core/io/file.cpp:123``) is not one."""
    lines = strip_ansi(text).splitlines()
    for index, raw in enumerate(lines):
        line = raw.strip()
        prefix = next((p for p in ERROR_PREFIXES if line.startswith(p)), None)
        if prefix is None and "Parse Error" not in line:
            continue
        if any(pattern in line for pattern in IGNORED_ERROR_PATTERNS):
            continue
        message = line[len(prefix) :].strip() if prefix else line
        where = _RES_PATH.search(line)
        follow = index + 1
        while where is None and follow < len(lines) and follow <= index + 3:
            below = lines[follow].strip()
            if not below.startswith(("at:", "GDScript backtrace", "[")):
                break
            where = _RES_PATH.search(below)
            follow += 1
        # a sentence's full stop after the path is not part of it
        path = where.group(1).rstrip(".,;") if where else None
        number = int(where.group(2)) if where and where.group(2) else None
        return GodotError(message[:300], path, number, line[:300])
    return None


def tail(text: str, lines: int = TAIL_LINES) -> str:
    """The last ``lines`` lines of a log, without colour codes."""
    return "\n".join(strip_ansi(text).splitlines()[-lines:])
