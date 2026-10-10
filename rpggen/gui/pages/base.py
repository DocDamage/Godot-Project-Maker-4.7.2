"""Base class of the seven wizard pages."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QCoreApplication, Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from rpggen.errors import Issue
from rpggen.gui import theme
from rpggen.gui.models.forms import (  # noqa: F401 - the pages import them from here
    EMPTY_CODE,
    FORM_CODE,
    form_error,
    form_missing,
    form_ok,
)
from rpggen.gui.state import WizardState
from rpggen.gui.widgets.page_header import PageHeader

PAGE_TOP = 20  # the top margin of a page: between space_16 and space_24, as the design has it


class WizardPage(QWidget):
    """One wizard page. The window calls ``enter`` / ``validate`` / ``leave``; pages own no logic
    beyond editing the state."""

    title = ""
    next_label: str | None = None  # None keeps the default label ("Next")
    allow_back = True
    allow_next = True
    help_anchor = ""  # title of the user-guide section F1 opens (a "## " heading of the guide)
    shows_inline_errors = False  # True when the page prints its own field messages

    # The header of the page (T15.06): ``heading`` when it differs from the sidebar's name, and
    # one line that says what the page is for (marked with QT_TRANSLATE_NOOP("WizardPage", ...)).
    heading = ""
    purpose = ""

    # the header under the name the pages use; a page may give the name to a widget of its
    # own (the Results page's line that says how the run went), ``page_header`` is always it
    header: Any
    page_header: PageHeader

    changed = Signal()  # emitted when a value changes so the window re-validates
    helpRequested = Signal(str)  # noqa: N815 - the header's help button: the guide's section

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        translate = QCoreApplication.translate
        # ``page_header`` is the same object: a page may use the name ``header`` for a widget
        # of its own (the Results page's line that says how the run went)
        self.page_header = self.header = PageHeader(
            translate("MainWindow", self.heading or self.title)
            if (self.heading or self.title)
            else "",
            translate("WizardPage", self.purpose) if self.purpose else "",
        )
        self.header.helpRequested.connect(lambda: self.helpRequested.emit(self.help_anchor))

    def page_layout(self) -> QVBoxLayout:
        """The page's outer layout with the margins every page has and the header in place;
        the page adds its body to it."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            theme.px("space_24"), PAGE_TOP, theme.px("space_24"), theme.px("space_16")
        )
        layout.setSpacing(theme.px("space_12"))
        layout.addWidget(self.header)
        return layout

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
