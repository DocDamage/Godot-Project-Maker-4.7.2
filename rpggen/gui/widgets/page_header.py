"""The header every wizard page starts with (T15.06): the page's title, one line that says what
the page is for, a slot for the page's own controls and the help button."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QPushButton, QWidget

from rpggen.gui import theme
from rpggen.gui.widgets import buttons


class PageHeader(QWidget):
    helpRequested = Signal()  # noqa: N815 - the help button was pressed (what F1 does)

    def __init__(self, title: str = "", purpose: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("pageHeader")
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(theme.px("space_12"))
        grid.setVerticalSpacing(2)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("pageTitle")
        self.title_label.setProperty("role", "title")
        self.purpose_label = QLabel(purpose)
        self.purpose_label.setObjectName("pagePurpose")
        self.purpose_label.setProperty("muted", True)
        self.purpose_label.setWordWrap(True)
        self.purpose_label.setMinimumWidth(1)  # it wraps to the page, it never widens it
        self.purpose_label.setVisible(bool(purpose))
        self.slot = QHBoxLayout()
        self.slot.setContentsMargins(0, 0, 0, 0)
        self.slot.setSpacing(theme.px("space_8"))
        self.help_button = QPushButton()
        self.help_button.setObjectName("pageHelp")
        buttons.icon_only(self.help_button, "help-circle", self.tr("Help for this page (F1)"))
        self.help_button.clicked.connect(self.helpRequested)
        # the title, the page's own controls and the help button on one line; the purpose
        # under them over the whole width, so that a full slot does not squeeze it
        grid.addWidget(self.title_label, 0, 0)
        grid.addLayout(self.slot, 0, 1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        grid.addWidget(self.help_button, 0, 2)
        grid.addWidget(self.purpose_label, 1, 0, 1, 3)
        grid.setColumnStretch(1, 1)

    def set_title(self, title: str) -> None:
        self.title_label.setText(title)

    def title(self) -> str:
        return self.title_label.text()

    def set_purpose(self, purpose: str) -> None:
        self.purpose_label.setText(purpose)
        self.purpose_label.setVisible(bool(purpose))

    def add_widget(self, widget: QWidget, stretch: int = 0) -> None:
        """Put one of the page's own controls between the texts and the help button."""
        self.slot.addWidget(widget, stretch, Qt.AlignmentFlag.AlignVCenter)
