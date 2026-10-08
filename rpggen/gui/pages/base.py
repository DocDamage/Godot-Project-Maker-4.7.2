"""Base class of the seven wizard pages."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget

from rpggen.errors import Issue
from rpggen.gui.models.forms import (  # noqa: F401 - the pages import them from here
    EMPTY_CODE,
    FORM_CODE,
    form_error,
    form_missing,
    form_ok,
)
from rpggen.gui.state import WizardState


class WizardPage(QWidget):
    """One wizard page. The window calls ``enter`` / ``validate`` / ``leave``; pages own no logic
    beyond editing the state."""

    title = ""
    next_label: str | None = None  # None keeps the default label ("Next")
    allow_back = True
    allow_next = True
    help_anchor = ""  # title of the user-guide section F1 opens (a "## " heading of the guide)
    shows_inline_errors = False  # True when the page prints its own field messages

    changed = Signal()  # emitted when a value changes so the window re-validates

    def enter(self, state: WizardState) -> None:  # noqa: B027 - optional hook
        """The page is shown: load widget values from ``state``."""

    def validate(self, state: WizardState) -> list[Issue]:
        """Issues of the current values; Next is disabled while an error exists."""
        return []

    def status(self, state: WizardState) -> tuple[str, int]:
        """What the sidebar shows for this step: (kind, count), kind one of ``none``, ``ok``,
        ``attention`` or ``error``. Computed from ``state`` alone, so it is right for a page that
        is not the current one."""
        return ("none", 0)

    def reveal_missing(self, state: WizardState) -> None:  # noqa: B027 - optional hook
        """Next was pressed while required fields are empty: mark them and focus the first."""

    def leave(self, state: WizardState) -> bool | None:
        """Write the widget values into ``state``. Returning False keeps the page open."""
        return None
