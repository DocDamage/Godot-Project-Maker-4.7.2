from __future__ import annotations

import re

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
