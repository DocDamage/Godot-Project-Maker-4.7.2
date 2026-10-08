"""Form messages of the wizard pages, and what a field's status line shows."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from rpggen.errors import Issue, Severity

FORM_CODE = "GUI-INPUT"  # form hints are not pipeline errors, so they have no table entry
EMPTY_CODE = "GUI-EMPTY"  # a required field that is only empty: Next stays enabled, pressing it
# marks the field and says what is missing

Translate = Callable[[str], str]


def no_translation(text: str) -> str:
    return text


def form_error(message: str, fix: str = "") -> Issue:
    return Issue(FORM_CODE, Severity.ERROR, message, fix)


def form_missing(message: str, fix: str = "") -> Issue:
    """An empty required field (not an error until the user presses Next)."""
    return Issue(EMPTY_CODE, Severity.ERROR, message, fix)


def form_ok(message: str) -> Issue:
    return Issue(FORM_CODE, Severity.INFO, message, "")


@dataclass(frozen=True)
class FieldStatus:
    """The line under a field: ``state`` is the style ("hint", "error", "warning", "ok" or ""
    for a neutral line such as "Checking…")."""

    text: str
    state: str = ""


def hint(text: str) -> FieldStatus:
    """A neutral grey line: what the field is for (shown until the user has touched it)."""
    return FieldStatus(text, "hint")


def status_of(issues: list[Issue], ok_text: str = "") -> FieldStatus:
    """The worst issue of ``issues`` (red, amber) or ``ok_text`` (green)."""
    worst = None
    for issue in issues:
        if issue.severity is Severity.ERROR:
            worst = issue
            break
        if issue.severity is Severity.WARNING and worst is None:
            worst = issue
    if worst is not None:
        state = "error" if worst.severity is Severity.ERROR else "warning"
        return FieldStatus(worst.message + (f" {worst.fix}" if worst.fix else ""), state)
    return FieldStatus(ok_text, "ok" if ok_text else "")
