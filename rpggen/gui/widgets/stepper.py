"""Rows painted as steps (T15.07, T15.15): a circle joined to the next one by a line, a name
and a note. The wizard's sidebar and the Generate page's phase list both use it; the lists stay
plain ``QListWidget``s, so their text, tooltips and accessible names are what they were.
"""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, QPoint, QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem

from rpggen.gui import icons, theme

# what a row is: set with ``item.setData(StateRole, ...)``
PENDING = "pending"  # not reached yet: an outlined circle
CURRENT = "current"  # the step the user is on: the accent
RUNNING = "running"  # a phase at work: a turning ring
DONE = "done"
ATTENTION = "attention"
ERROR = "error"
SKIPPED = "skipped"  # a check that did not run: a dash, never a tick

StateRole = Qt.ItemDataRole.UserRole + 20  # one of the states above
LabelRole = Qt.ItemDataRole.UserRole + 21  # the name beside the circle
NoteRole = Qt.ItemDataRole.UserRole + 22  # at the right (a count, a duration)
NumberRole = Qt.ItemDataRole.UserRole + 23  # in the circle of a pending or current row ("" = none)

CIRCLE = 24
ROW_HEIGHT = 44
NARROW_BELOW = 100  # a row narrower than this shows the circle only
SPIN_FRAMES = 12
_FILLS = {DONE: "success", ATTENTION: "warning", ERROR: "danger"}
_GLYPHS = {DONE: "check", ATTENTION: "alert-triangle", ERROR: "x"}


class StepDelegate(QStyledItemDelegate):
    """Paints a row as a step. ``compact`` rows (the phase list) are lower and have no bar at
    the left edge; ``spin_frame`` turns the ring of a running row (the owner advances it)."""

    def __init__(self, parent=None, *, compact: bool = False) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.compact = compact
        self.spin_frame = 0
        self.row_height = 32 if compact else ROW_HEIGHT
        self.circle = 18 if compact else CIRCLE

    # -------------------------------------------------------------- geometry (tests read it)

    def circle_rect(self, row: QRect) -> QRect:
        narrow = row.width() < NARROW_BELOW
        left = row.left() + ((row.width() - self.circle) // 2 if narrow else 16)
        return QRect(left, row.top() + (row.height() - self.circle) // 2, self.circle, self.circle)

    def sizeHint(  # noqa: N802 - Qt override
        self, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex
    ) -> QSize:
        return QSize(40, self.row_height)

    # -------------------------------------------------------------- painting

    def paint(  # noqa: C901 - one row, drawn part by part
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        row = option.rect  # type: ignore[attr-defined]
        state_flags = option.state  # type: ignore[attr-defined]
        enabled = bool(state_flags & QStyle.StateFlag.State_Enabled)
        state = str(index.data(StateRole) or PENDING)
        label = str(index.data(LabelRole) or "")
        note = str(index.data(NoteRole) or "")
        number = str(index.data(NumberRole) or "")
        narrow = row.width() < NARROW_BELOW
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if not enabled and not self.compact:
            painter.setOpacity(0.6)
        if enabled and state_flags & QStyle.StateFlag.State_MouseOver and not self.compact:
            painter.fillRect(row, theme.color("surface_hover"))
        if state == CURRENT and not self.compact:
            painter.fillRect(
                QRect(row.left(), row.top() + 4, 3, row.height() - 8), theme.color("accent")
            )

        circle = self.circle_rect(row)
        self._paint_lines(painter, index, row, circle)
        self._paint_circle(painter, state, number, circle)

        if not narrow:
            text_left = circle.right() + 12
            font = QFont(option.font)  # type: ignore[attr-defined]
            if state == CURRENT:
                font.setWeight(QFont.Weight.DemiBold)
            painter.setFont(font)
            metrics = painter.fontMetrics()
            note_width = metrics.horizontalAdvance(note) + 12 if note else 0
            muted = state in (PENDING, SKIPPED) or not enabled
            painter.setPen(theme.color("text_muted" if muted else "text"))
            room = QRect(
                text_left, row.top(), row.right() - text_left - note_width - 4, row.height()
            )
            painter.drawText(
                room,
                int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                metrics.elidedText(label, Qt.TextElideMode.ElideRight, max(room.width(), 0)),
            )
            if note:
                painter.setFont(QFont(option.font))  # type: ignore[attr-defined]
                painter.setPen(theme.color("text_muted"))
                painter.drawText(
                    QRect(row.right() - note_width - 4, row.top(), note_width, row.height()),
                    int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight),
                    note,
                )
        painter.restore()

    def _paint_lines(
        self,
        painter: QPainter,
        index: QModelIndex | QPersistentModelIndex,
        row: QRect,
        circle: QRect,
    ) -> None:
        """The 2 px line to the rows above and below: green when the step it leaves is done."""
        model = index.model()
        x = circle.center().x()
        if index.row() > 0:
            above = model.index(index.row() - 1, index.column()).data(StateRole)
            painter.setPen(QPen(self._line_colour(str(above or PENDING)), 2))
            painter.drawLine(QPoint(x, row.top()), QPoint(x, circle.top() - 2))
        if index.row() < model.rowCount() - 1:
            painter.setPen(QPen(self._line_colour(str(index.data(StateRole) or PENDING)), 2))
            painter.drawLine(QPoint(x, circle.bottom() + 3), QPoint(x, row.bottom()))

    @staticmethod
    def _line_colour(state: str) -> QColor:
        return theme.color("success" if state == DONE else "border_strong")

    def _paint_circle(self, painter: QPainter, state: str, number: str, circle: QRect) -> None:
        if state in _FILLS:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(theme.color(_FILLS[state]))
            painter.drawEllipse(circle)
            size = circle.width() - 10
            glyph = icons.pixmap(_GLYPHS[state], "on_status", size)
            painter.drawPixmap(circle.left() + 5, circle.top() + 5, glyph)
            return
        if state == CURRENT:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(theme.color("accent"))
            painter.drawEllipse(circle)
            self._paint_number(painter, number, circle, "on_accent")
            return
        inner = circle.adjusted(1, 1, -1, -1)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if state == RUNNING:
            painter.setPen(QPen(theme.color("border"), 2))
            painter.drawEllipse(inner)
            painter.setPen(QPen(theme.color("accent"), 2, c=Qt.PenCapStyle.RoundCap))
            start = -(360 * 16 * (self.spin_frame % SPIN_FRAMES)) // SPIN_FRAMES + 90 * 16
            painter.drawArc(inner, start, -100 * 16)
            return
        painter.setPen(QPen(theme.color("border_strong"), 1.5))
        painter.drawEllipse(inner)
        if state == SKIPPED:
            painter.setPen(QPen(theme.color("text_muted"), 2, c=Qt.PenCapStyle.RoundCap))
            y = circle.center().y() + 1
            painter.drawLine(QPoint(circle.left() + 6, y), QPoint(circle.right() - 5, y))
            return
        self._paint_number(painter, number, circle, "text_muted")

    @staticmethod
    def _paint_number(painter: QPainter, number: str, circle: QRect, colour: str) -> None:
        if not number:
            return
        font = QFont(painter.font())
        font.setPixelSize(theme.px("font_caption"))
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(theme.color(colour))
        painter.drawText(circle, int(Qt.AlignmentFlag.AlignCenter), number)
