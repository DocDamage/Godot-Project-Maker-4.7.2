"""Base class of the seven wizard pages."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget

from rpggen.errors import Issue, Severity
from rpggen.gui.state import WizardState


class WizardPage(QWidget):
    """One wizard page. The window calls ``enter`` / ``validate`` / ``leave``; pages own no logic
    beyond editing the state."""

    title = ""
    next_label: str | None = None  # None keeps the default label ("Next")
    allow_back = True
    allow_next = True

    changed = Signal()  # emitted when a value changes so the window re-validates

    def enter(self, state: WizardState) -> None:  # noqa: B027 - optional hook
        """The page is shown: load widget values from ``state``."""

    def validate(self, state: WizardState) -> list[Issue]:
        """Issues of the current values; Next is disabled while an error exists."""
        return []

    def leave(self, state: WizardState) -> None:  # noqa: B027 - optional hook
        """Write the widget values into ``state``."""


FORM_CODE = "GUI-INPUT"  # form hints are not pipeline errors, so they have no table entry


def form_error(message: str, fix: str = "") -> Issue:
    return Issue(FORM_CODE, Severity.ERROR, message, fix)


def form_ok(message: str) -> Issue:
    return Issue(FORM_CODE, Severity.INFO, message, "")
