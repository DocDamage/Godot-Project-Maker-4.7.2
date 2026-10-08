"""A read-only, size-limited, monospace log that follows new lines unless the user scrolled up."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QPlainTextEdit, QWidget

MAX_LINES = 5_000


class LogView(QPlainTextEdit):
    """Lines arrive one at a time or in batches (``append_lines``). Only the last ``max_lines`` are
    kept: when older ones are dropped for the first time ``truncated`` is emitted and ``dropped``
    stays True, so that the window can point to the complete log on disk."""

    truncated = Signal()

    def __init__(self, parent: QWidget | None = None, max_lines: int = MAX_LINES) -> None:
        super().__init__(parent)
        self.setObjectName("logView")
        self.setReadOnly(True)
        self.setMaximumBlockCount(max_lines)
        self.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._max_lines = max_lines
        self._added = 0
        self.dropped = False

    def at_bottom(self) -> bool:
        bar = self.verticalScrollBar()
        return bar is None or bar.value() >= bar.maximum() - 2

    def append_line(self, line: str) -> None:
        """Add text (it may hold several lines) and follow the end unless the user scrolled up."""
        follow = self.at_bottom()
        self.appendPlainText(line)
        self._added += line.count("\n") + 1
        if not self.dropped and self._added > self._max_lines:
            self.dropped = True
            self.truncated.emit()
        if follow:
            bar = self.verticalScrollBar()
            if bar is not None:
                bar.setValue(bar.maximum())

    def append_lines(self, lines: list[str]) -> None:
        """A batch in one step: one repaint and one scroll instead of one per line."""
        if lines:
            self.append_line("\n".join(lines))

    def clear(self) -> None:
        super().clear()
        self._added = 0
        self.dropped = False

    def lines(self) -> int:
        return self.blockCount()
