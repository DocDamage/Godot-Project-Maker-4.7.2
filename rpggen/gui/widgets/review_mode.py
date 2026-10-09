"""Review mode of the Audit page (T13.01): one asset at a time, with a large preview.

The widget only shows: the page keeps the grid's selection as "the asset shown", lends its own
``AssetDetail`` panel for the right-hand side and handles every key, so nothing is edited twice
and leaving the mode changes no state.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from rpggen.gui.widgets.image_view import ImageView

QUICK_KEYS = "CX123456789N"


class ReviewMode(QWidget):
    """Left two thirds: the preview, the counter and the key line. Right third: ``side``, the
    box the page puts its detail panel in."""

    quickKey = Signal(str)  # noqa: N815 - the keys of the grid: C, X, 1-9, N, SHIFT+N
    leaveRequested = Signal()  # noqa: N815 - Esc

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("reviewMode")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        row = QHBoxLayout(self)
        row.setContentsMargins(6, 0, 6, 0)
        left = QVBoxLayout()
        self.preview = ImageView("reviewPreview")
        self.preview.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # the keys stay with the mode
        self.preview.setAccessibleName(self.tr("Preview of the asset under review"))
        left.addWidget(self.preview, 1)
        self.no_picture_label = QLabel()
        self.no_picture_label.setObjectName("reviewNoPicture")
        self.no_picture_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_picture_label.setWordWrap(True)
        self.no_picture_label.setVisible(False)
        left.addWidget(self.no_picture_label, 1)
        self.counter_label = QLabel()
        self.counter_label.setObjectName("reviewCounter")
        left.addWidget(self.counter_label)
        self.keys_label = QLabel(
            self.tr("C Confirm · X Exclude · 1–9 Role · N Next · Shift+N Previous · Esc Back")
        )
        self.keys_label.setObjectName("reviewKeys")
        self.keys_label.setWordWrap(True)
        left.addWidget(self.keys_label)
        row.addLayout(left, 2)
        self.side = QVBoxLayout()
        self.side.setContentsMargins(0, 0, 0, 0)
        row.addLayout(self.side, 1)

    def show_picture(self, path: Path | None, grid: dict | None, note: str = "") -> None:
        """The asset's image with its tile or frame grid, or ``note`` when it has none (a sound,
        a font, a file that is gone)."""
        has_picture = path is not None
        self.preview.setVisible(has_picture)
        self.no_picture_label.setVisible(not has_picture)
        self.no_picture_label.setText(note)
        self.preview.set_image(path, grid)

    def set_counter(self, text: str) -> None:
        self.counter_label.setText(text)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        modifiers = event.modifiers()
        text = event.text().upper()
        if event.key() == Qt.Key.Key_Escape:
            self.leaveRequested.emit()
        elif event.key() == Qt.Key.Key_N and modifiers == Qt.KeyboardModifier.ShiftModifier:
            self.quickKey.emit("SHIFT+N")
        elif modifiers == Qt.KeyboardModifier.NoModifier and len(text) == 1 and text in QUICK_KEYS:
            self.quickKey.emit(text)
        else:
            super().keyPressEvent(event)
            return
        event.accept()
