from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from rpggen.errors_table import CODES, CodeInfo

__all__ = ["CODES", "CodeInfo", "Issue", "IssueList", "RpgGenError", "Severity", "format_message"]


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


_SEVERITY_ORDER = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}


class _SafeDict(dict[str, Any]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def format_message(code: str, /, file: str | None = None, **detail: Any) -> str:
    """Format the code's message template; unknown placeholders stay as ``{name}``."""
    values = dict(detail)
    if file is not None:
        values.setdefault("file", file)
    return CODES[code].message.format_map(_SafeDict(values))


@dataclass(frozen=True, slots=True)
class Issue:
    code: str
    severity: Severity
    message: str  # what is wrong, one sentence
    fix: str  # recommended fix, one sentence
    file: str | None = None  # posix relative path when relevant
    detail: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "code": self.code,
            "severity": str(self.severity),
            "message": self.message,
            "fix": self.fix,
        }
        if self.file is not None:
            out["file"] = self.file
        return out


def make_issue(code: str, message: str | None, file: str | None, detail: dict[str, Any]) -> Issue:
    """Build an Issue for ``code`` (KeyError if unknown); message defaults to the template."""
    info = CODES[code]
    text = message if message is not None else format_message(code, file, **detail)
    return Issue(code, Severity(info.severity), text, info.fix, file, dict(detail))


class RpgGenError(Exception):
    """A fatal, coded problem. ``message`` defaults to the code's formatted template."""

    def __init__(
        self, code: str, /, message: str | None = None, *, file: str | None = None, **detail: Any
    ) -> None:
        base = make_issue(code, message, file, detail)
        # Fatal errors always report as errors, whatever the table says for the code.
        self.issue_value = Issue(code, Severity.ERROR, base.message, base.fix, file, dict(detail))
        self.code = code
        self.file = file
        self.detail = dict(detail)
        super().__init__(f"{code}: {self.issue_value.message}")

    @property
    def issue(self) -> Issue:
        return self.issue_value


class IssueList(list[Issue]):
    """A list of issues with helpers; severity and fix come from ``CODES``."""

    def add(
        self, code: str, /, message: str | None = None, file: str | None = None, **detail: Any
    ) -> Issue:
        issue = make_issue(code, message, file, detail)
        self.append(issue)
        return issue

    def has_errors(self) -> bool:
        return any(i.severity is Severity.ERROR for i in self)

    def to_json(self) -> list[dict[str, Any]]:
        ordered = sorted(self, key=lambda i: (_SEVERITY_ORDER[i.severity], i.code, i.file or ""))
        return [i.to_json() for i in ordered]
