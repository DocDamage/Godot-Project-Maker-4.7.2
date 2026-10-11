"""The header every wizard page starts with (T15.06): the page's title, one line that says what
the page is for, a slot for the page's own controls and the help button.

The title, the controls and the help button share a line while they fit. On a page that is too
narrow for that (a wide font, a long title, many controls) the controls go on a line of their
own under the title, so the header never keeps its page from being made narrower."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
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
        # the page's own controls: children of the header, in a layout that is moved between
        # the title's line and a line of its own
        self.slot = QHBoxLayout()
        self.slot.setContentsMargins(0, 0, 0, 0)
        self.slot.setSpacing(theme.px("space_8"))
        self.help_button = QPushButton()
        self.help_button.setObjectName("pageHelp")
        buttons.icon_only(self.help_button, "help-circle", self.tr("Help for this page (F1)"))
        self.help_button.clicked.connect(self.helpRequested)
        # the title, the page's own controls and the help button on one line; the purpose
        # under them over the whole width, so that a full slot does not squeeze it
        self._grid = grid
        self._stacked: bool | None = None
        grid.addWidget(self.title_label, 0, 0)
        grid.addWidget(self.help_button, 0, 2)
        grid.setColumnStretch(1, 1)
        self._arrange(False)

    # ------------------------------------------------------------------ layout

    def _row_width(self) -> int:
        """The width the title, the controls and the help button need on one line."""
        gap = self._grid.horizontalSpacing()
        return (
            self.title_label.minimumSizeHint().width()
            + self.slot.minimumSize().width()
            + self.help_button.sizeHint().width()
            + 2 * gap
        )

    def _stacked_width(self) -> int:
        """The width the header needs with the controls on a line of their own."""
        gap = self._grid.horizontalSpacing()
        top = self.title_label.minimumSizeHint().width() + gap + self.help_button.sizeHint().width()
        return max(top, self.slot.minimumSize().width())

    def _arrange(self, stacked: bool) -> None:
        if stacked == self._stacked:
            return
        self._stacked = stacked
        grid = self._grid
        if self.slot.parent() is not None:
            grid.removeItem(self.slot)
            self.slot.setParent(None)  # a layout is added to a layout only without a parent
        grid.removeWidget(self.purpose_label)
        if stacked:
            grid.addLayout(self.slot, 1, 0, 1, 3, Qt.AlignmentFlag.AlignLeft)
            grid.addWidget(self.purpose_label, 2, 0, 1, 3)
        else:
            right = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            grid.addLayout(self.slot, 0, 1, right)
            grid.addWidget(self.purpose_label, 1, 0, 1, 3)

    @property
    def stacked(self) -> bool:
        """True while the page's controls are on a line of their own under the title."""
        return bool(self._stacked)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        # what the narrower of the two arrangements needs: the header gives way to its page
        hint = super().minimumSizeHint()
        return QSize(min(hint.width(), self._stacked_width()), hint.height())

    def resizeEvent(self, event) -> None:  # noqa: ANN001, N802
        super().resizeEvent(event)
        self._arrange(self.slot.count() > 0 and self.width() < self._row_width())

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
