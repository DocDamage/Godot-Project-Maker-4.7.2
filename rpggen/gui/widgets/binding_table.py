"""The input bindings table: type ``W, Up`` or double-click a cell and press the key."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent, QKeySequence, QMouseEvent
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem

from rpggen.core import options

KEYS_COLUMN = 1
MOUSE_COLUMN = 2
PRESS_TEXT = "Press a key…"
MOUSE_BUTTONS = {
    Qt.MouseButton.LeftButton: 1,
    Qt.MouseButton.RightButton: 2,
    Qt.MouseButton.MiddleButton: 3,
}


class BindingTable(QTableWidget):
    """A cell of the Keys or Mouse buttons column can be filled by pressing the key (or clicking
    the mouse button) after a double-click; Escape cancels. Typing still works."""

    def __init__(self, columns: int) -> None:
        super().__init__(0, columns)
        self._capturing: tuple[int, int] | None = None
        self._before = ""
        self.cellDoubleClicked.connect(self.start_capture)

    def start_capture(self, row: int, col: int) -> None:
        if col not in (KEYS_COLUMN, MOUSE_COLUMN):
            return
        item = self.item(row, col)
        if item is None:
            return
        self._capturing = (row, col)
        self._before = item.text()
        self.blockSignals(True)
        item.setText(PRESS_TEXT if col == KEYS_COLUMN else "Click a mouse button…")
        self.blockSignals(False)
        self.setFocus()

    def is_capturing(self) -> bool:
        return self._capturing is not None

    def _finish(self, text: str) -> None:
        assert self._capturing is not None
        row, col = self._capturing
        self._capturing = None
        item = self.item(row, col)
        if item is not None:
            item.setText(text)  # itemChanged tells the page when the text changed

    def _append(self, value: str) -> str:
        values = [v.strip() for v in self._before.split(",") if v.strip()]
        if value not in values:
            values.append(value)
        return ", ".join(values)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt override
        if self._capturing is None or self._capturing[1] != KEYS_COLUMN:
            super().keyPressEvent(event)
            return
        if event.key() == Qt.Key.Key_Escape:
            self._finish(self._before)
        else:
            name = options.key_name(QKeySequence(event.key()).toString())
            self._finish(self._append(name) if name else self._before)
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._capturing is not None and self._capturing[1] == MOUSE_COLUMN:
            number = MOUSE_BUTTONS.get(event.button())
            if number is not None:
                self._finish(self._append(str(number)))
                event.accept()
                return
        super().mousePressEvent(event)

    def focusOutEvent(self, event) -> None:  # noqa: ANN001, N802
        if self._capturing is not None:
            self._finish(self._before)
        super().focusOutEvent(event)


def make_item(text: str, editable: bool = True) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    if not editable:
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    return item
