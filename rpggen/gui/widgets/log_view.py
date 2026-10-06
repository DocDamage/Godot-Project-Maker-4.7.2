"""A read-only, size-limited, monospace log that follows new lines unless the user scrolled up."""

from __future__ import annotations

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QPlainTextEdit, QWidget

MAX_LINES = 10_000


class LogView(QPlainTextEdit):
    def __init__(self, parent: QWidget | None = None, max_lines: int = MAX_LINES) -> None:
        super().__init__(parent)
        self.setObjectName("logView")
        self.setReadOnly(True)
        self.setMaximumBlockCount(max_lines)
        self.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

    def at_bottom(self) -> bool:
        bar = self.verticalScrollBar()
        return bar is None or bar.value() >= bar.maximum() - 2

    def append_line(self, line: str) -> None:
        follow = self.at_bottom()
        self.appendPlainText(line)
        if follow:
            bar = self.verticalScrollBar()
            if bar is not None:
                bar.setValue(bar.maximum())

    def lines(self) -> int:
        return self.blockCount()
