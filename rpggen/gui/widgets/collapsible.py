"""A section that folds away: a chevron, a title and a body."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QToolButton, QVBoxLayout, QWidget

from rpggen.gui import icons


class CollapsibleSection(QWidget):
    toggled = Signal(bool)

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._title = title
        self.header = QToolButton()
        self.header.setObjectName("collapsibleHeader")
        self.header.setCheckable(True)
        self.header.setChecked(False)
        self.header.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        icons.set_icon(self.header, "chevron-right")
        self.header.setToolTip("Show or hide this section")
        self.body = QWidget()
        self.body.setVisible(False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.header)
        layout.addWidget(self.body)
        self.header.toggled.connect(self._on_toggled)
        self._update_text()

    def set_title(self, title: str) -> None:
        self._title = title
        self._update_text()

    def _update_text(self) -> None:
        self.header.setText(self._title)
        themed = self.header._themed_icon  # type: ignore[attr-defined]
        themed.name = "chevron-down" if self.header.isChecked() else "chevron-right"
        themed.apply()
        self.header.setAccessibleDescription("open" if self.header.isChecked() else "closed")

    def _on_toggled(self, checked: bool) -> None:
        self.body.setVisible(checked)
        self._update_text()
        self.toggled.emit(checked)

    def is_open(self) -> bool:
        return self.header.isChecked()

    def set_open(self, value: bool) -> None:
        self.header.setChecked(value)
