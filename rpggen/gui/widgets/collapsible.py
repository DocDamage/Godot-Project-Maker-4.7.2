"""A section that folds away: a ▸ / ▾ arrow, a title and a body."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QToolButton, QVBoxLayout, QWidget


class CollapsibleSection(QWidget):
    toggled = Signal(bool)

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._title = title
        self.header = QToolButton()
        self.header.setObjectName("collapsibleHeader")
        self.header.setCheckable(True)
        self.header.setChecked(False)
        self.header.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.header.setStyleSheet(
            "QToolButton { border: none; font-weight: bold; text-align: left; }"
        )
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
        arrow = "▾" if self.header.isChecked() else "▸"
        self.header.setText(f"{arrow} {self._title}")

    def _on_toggled(self, checked: bool) -> None:
        self.body.setVisible(checked)
        self._update_text()
        self.toggled.emit(checked)

    def is_open(self) -> bool:
        return self.header.isChecked()

    def set_open(self, value: bool) -> None:
        self.header.setChecked(value)
