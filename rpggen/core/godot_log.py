from __future__ import annotations

from rpggen.errors import Issue, IssueList

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
