"""The pack list of the Project page: one card per pack, folders and archives can be dropped."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QDragEnterEvent, QDropEvent, QPainter, QPalette, QPen
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QStyle, QStyledItemDelegate

CARD_ROLE = Qt.ItemDataRole.UserRole + 1  # the dict a pack card is drawn from
CHIP_COLORS = {"format": "#1976d2", "ok": "#388e3c", "warn": "#ef6c00", "error": "#d32f2f"}


class PackCardDelegate(QStyledItemDelegate):
    """Draws a pack as a card: name, kind/files/size, a format chip, a licence chip, an inline
    error and a remove button (a click on the cross emits ``removeRequested(row)``)."""

    removeRequested = Signal(int)  # noqa: N815
    HEIGHT = 68

    def sizeHint(self, option, index) -> QSize:  # noqa: ANN001
        return QSize(220, self.HEIGHT)

    @staticmethod
    def remove_rect(rect: QRect) -> QRect:
        return QRect(rect.right() - 26, rect.top() + 6, 20, 20)

    def paint(self, painter: QPainter, option, index) -> None:  # noqa: ANN001
        card = index.data(CARD_ROLE) or {}
        painter.save()
        rect = option.rect.adjusted(2, 2, -2, -2)
        palette = option.palette
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(palette.highlight() if selected else palette.base())
        painter.setPen(QPen(palette.color(QPalette.ColorRole.Mid)))
        painter.drawRoundedRect(rect, 6, 6)
        ink = palette.highlightedText().color() if selected else palette.text().color()
        muted = palette.color(QPalette.ColorRole.PlaceholderText) if not selected else ink
        left, width = rect.left() + 10, rect.width() - 46
        font = painter.font()
        bold = painter.font()
        bold.setBold(True)
        painter.setFont(bold)
        painter.setPen(ink)
        name = card.get("name") or str(index.data(Qt.ItemDataRole.UserRole) or "")
        painter.drawText(
            QRect(left, rect.top() + 4, width, 18),
            Qt.AlignmentFlag.AlignVCenter,
            painter.fontMetrics().elidedText(name, Qt.TextElideMode.ElideMiddle, width),
        )
        painter.setFont(font)
        painter.setPen(muted)
        detail = card.get("detail") or str(index.data(Qt.ItemDataRole.UserRole) or "")
        painter.drawText(
            QRect(left, rect.top() + 22, width, 16),
            Qt.AlignmentFlag.AlignVCenter,
            painter.fontMetrics().elidedText(detail, Qt.TextElideMode.ElideMiddle, width),
        )
        painter.setPen(ink)
        painter.drawText(self.remove_rect(rect), Qt.AlignmentFlag.AlignCenter, "×")
        x = left
        for text, kind in card.get("chips", []):
            chip_w = painter.fontMetrics().horizontalAdvance(text) + 14
            chip = QRect(x, rect.top() + 42, chip_w, 18)
            if chip.right() > rect.right() - 6:
                break
            color = QColor(CHIP_COLORS.get(kind, CHIP_COLORS["format"]))
            fill = QColor(color)
            fill.setAlpha(50)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill)
            painter.drawRoundedRect(chip, 8, 8)
            painter.setPen(ink if not selected else ink)
            painter.drawText(chip, Qt.AlignmentFlag.AlignCenter, text)
            x += chip_w + 6
        error = card.get("error")
        if error:
            painter.setPen(QColor(CHIP_COLORS["error"]))
            painter.drawText(
                QRect(left, rect.top() + 42, width + 30, 18),
                Qt.AlignmentFlag.AlignVCenter,
                painter.fontMetrics().elidedText(
                    "⚠ " + error, Qt.TextElideMode.ElideRight, width + 30
                ),
            )
        painter.restore()

    def editorEvent(self, event, model, option, index) -> bool:  # noqa: ANN001
        if (
            event.type() == QEvent.Type.MouseButtonRelease
            and event.button() == Qt.MouseButton.LeftButton
            and self.remove_rect(option.rect.adjusted(2, 2, -2, -2)).contains(
                event.position().toPoint()
            )
        ):
            self.removeRequested.emit(index.row())
            return True
        return super().editorEvent(event, model, option, index)


class PackList(QListWidget):
    """The pack list; files and folders can be dropped onto it. Empty, it draws a dashed frame
    that says what to drop."""

    EMPTY_TEXT = "Drop asset packs here: folders, .zip, .7z or .rar"

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("packList")
        self.setAcceptDrops(True)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.setMinimumHeight(140)
        self.on_paths_dropped = lambda paths: None
        self.card_delegate = PackCardDelegate(self)
        self.setItemDelegate(self.card_delegate)
        self.setSpacing(1)

    def paintEvent(self, event) -> None:  # noqa: ANN001
        super().paintEvent(event)
        if self.count():
            return
        painter = QPainter(self.viewport())
        pen = QPen(self.palette().color(QPalette.ColorRole.Mid))
        pen.setStyle(Qt.PenStyle.DashLine)
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawRoundedRect(self.viewport().rect().adjusted(6, 6, -6, -6), 6, 6)
        painter.setPen(self.palette().color(QPalette.ColorRole.PlaceholderText))
        painter.drawText(
            self.viewport().rect(), Qt.AlignmentFlag.AlignCenter, self.tr(self.EMPTY_TEXT)
        )
        painter.end()

    def paths(self) -> list[Path]:
        return [
            Path(self.item(i).data(Qt.ItemDataRole.UserRole) or self.item(i).text())
            for i in range(self.count())
        ]

    def add_path(self, path: Path | str) -> QListWidgetItem:
        item = QListWidgetItem(str(path))
        item.setData(Qt.ItemDataRole.UserRole, str(path))
        self.addItem(item)
        return item

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:  # noqa: ANN001
        event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        dropped = [Path(u.toLocalFile()) for u in event.mimeData().urls() if u.isLocalFile()]
        if dropped:
            self.on_paths_dropped(dropped)
            event.acceptProposedAction()
