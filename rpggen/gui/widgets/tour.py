"""A tour: a few callouts, each pointing at one widget of a page (T13.09).

Nothing is dimmed and nothing is blocked: the callout is a small panel over the window, beside
the widget it is about, and the page stays usable while it shows. *Next*, *Back* and *Skip* are
ordinary buttons (Tab reaches them; Next has the focus), and Esc skips.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

WIDTH = 320
GAP = 8  # between the widget and its callout


@dataclass(frozen=True)
class TourStep:
    widget: QWidget  # what the callout points at
    title: str
    text: str


def place(anchor: QRect, size: tuple[int, int], host: QRect) -> QPoint:
    """Where a callout of ``size`` goes for a widget at ``anchor`` (both in the host's
    coordinates): below it, else above it, else beside it, and always inside the host."""
    width, height = size
    x = anchor.left()
    if anchor.bottom() + GAP + height <= host.bottom():
        y = anchor.bottom() + GAP
    elif anchor.top() - GAP - height >= host.top():
        y = anchor.top() - GAP - height
    else:  # a widget as tall as the window: over its lower part, to the side that has room
        y = host.bottom() - height - GAP
        if anchor.right() + GAP + width <= host.right():
            x = anchor.right() + GAP
        elif anchor.left() - GAP - width >= host.left():
            x = anchor.left() - GAP - width
    # whatever the widget's place (it may be scrolled out of view), the callout is in the host
    x = max(host.left() + GAP, min(x, host.right() - width - GAP))
    y = max(host.top() + GAP, min(y, host.bottom() - height - GAP))
    return QPoint(x, y)


class Tour(QFrame):
    """The callout of a running tour. ``host`` is the widget it is drawn over (the window's
    page area); the steps' widgets are somewhere below it."""

    finished = Signal(bool)  # True when it was skipped (or closed with Esc), False at the end

    def __init__(self, host: QWidget, steps: Sequence[TourStep], name: str = "") -> None:
        super().__init__(host)
        self.setObjectName("tourCallout")
        self.name = name
        self.steps = list(steps)
        self.index = -1
        self.running = False
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setAutoFillBackground(True)
        self.setFixedWidth(WIDTH)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        layout = QVBoxLayout(self)
        self.title_label = QLabel()
        self.title_label.setObjectName("tourTitle")
        self.text_label = QLabel()
        self.text_label.setObjectName("tourText")
        self.text_label.setWordWrap(True)
        self.count_label = QLabel()
        self.count_label.setObjectName("tourCount")
        self.count_label.setProperty("muted", True)
        layout.addWidget(self.title_label)
        layout.addWidget(self.text_label)
        row = QHBoxLayout()
        self.skip_button = QPushButton(self.tr("Skip"))
        self.skip_button.setObjectName("tourSkip")
        self.skip_button.setToolTip(self.tr("Close the tour (Esc). Help > Show the tour again."))
        self.back_button = QPushButton(self.tr("Back"))
        self.back_button.setObjectName("tourBack")
        self.next_button = QPushButton(self.tr("Next"))
        self.next_button.setObjectName("tourNext")
        self.next_button.setDefault(True)
        row.addWidget(self.count_label, 1)
        row.addWidget(self.skip_button)
        row.addWidget(self.back_button)
        row.addWidget(self.next_button)
        layout.addLayout(row)
        self.skip_button.clicked.connect(self.skip)
        self.back_button.clicked.connect(self.back)
        self.next_button.clicked.connect(self.next)
        self.hide()
        host.installEventFilter(self)

    # ------------------------------------------------------------------ steps

    def start(self) -> bool:
        """Show the first step; False for a tour without steps."""
        if not self.steps:
            return False
        self.running = True
        self.go(0)
        return True

    def go(self, index: int) -> None:
        self.index = max(0, min(index, len(self.steps) - 1))
        step = self.steps[self.index]
        self.title_label.setText(f"<b>{step.title}</b>")
        self.text_label.setText(step.text)
        self.count_label.setText(self.tr("{0} of {1}").format(self.index + 1, len(self.steps)))
        self.back_button.setEnabled(self.index > 0)
        last = self.index == len(self.steps) - 1
        self.next_button.setText(self.tr("Done") if last else self.tr("Next"))
        self.setAccessibleName(f"{step.title}. {step.text}")
        self.adjustSize()
        self.reposition()
        self.show()
        self.raise_()
        self.next_button.setFocus()

    def reposition(self) -> None:
        """Beside the step's widget, as the window is now."""
        if not 0 <= self.index < len(self.steps):
            return
        host = self.parentWidget()
        widget = self.steps[self.index].widget
        if host is None:
            return
        top_left = widget.mapTo(host, QPoint(0, 0)) if host.isAncestorOf(widget) else QPoint(0, 0)
        anchor = QRect(top_left, widget.size())
        self.move(place(anchor, (self.width(), self.height()), host.rect()))

    def next(self) -> None:
        if self.index >= len(self.steps) - 1:
            self._end(skipped=False)
        else:
            self.go(self.index + 1)

    def back(self) -> None:
        if self.index > 0:
            self.go(self.index - 1)

    def skip(self) -> None:
        self._end(skipped=True)

    def _end(self, skipped: bool) -> None:
        if not self.running:
            return
        self.running = False
        self.hide()
        self.finished.emit(skipped)

    # ------------------------------------------------------------------ keys and the window

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.skip()
            event.accept()
            return
        super().keyPressEvent(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if self.running and event.type() in (QEvent.Type.Resize, QEvent.Type.LayoutRequest):
            self.reposition()
        return False
