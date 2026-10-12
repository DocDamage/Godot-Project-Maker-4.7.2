"""The pack list of the Project page: one card per pack, folders and archives can be dropped."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QRect, QSize, Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QPainter, QPen
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QStyle, QStyledItemDelegate

from rpggen.core import pack_sniff
from rpggen.gui import theme

CARD_ROLE = Qt.ItemDataRole.UserRole + 1  # the dict a pack card is drawn from
# T16.22: the packs taken from a bundle stand under a row that names the archive. That row
# has the archive's path here, and so has every pack under it.
GROUP_ROLE = Qt.ItemDataRole.UserRole + 2  # on the row of the group
MEMBER_ROLE = Qt.ItemDataRole.UserRole + 3  # on a pack of the group
CHIP_TOKENS = {"format": "accent", "ok": "success", "warn": "warning", "error": "danger"}


class PackCardDelegate(QStyledItemDelegate):
    """Draws a pack as a card: the name with the format and licence chips and a remove button
    on its line (a click on the cross emits ``removeRequested(row)``), and under it
    kind/files/size, or the pack's error. The row of a bundle's group has *Choose packs…* at
    the right of its second line (a click emits ``chooseRequested(row)``)."""

    removeRequested = Signal(int)  # noqa: N815
    chooseRequested = Signal(int)  # noqa: N815
    HEIGHT = 50  # two lines: the name with its chips, and the details

    def sizeHint(self, option, index) -> QSize:  # noqa: ANN001
        return QSize(220, self.HEIGHT)

    @staticmethod
    def remove_rect(rect: QRect) -> QRect:
        return QRect(rect.right() - 26, rect.top() + 5, 20, 20)

    @staticmethod
    def choose_rect(rect: QRect, width: int) -> QRect:
        """Where *Choose packs…* stands on the row of a group, ``width`` px of text wide."""
        return QRect(rect.right() - 12 - width, rect.top() + 24, width, 16)

    def paint(self, painter: QPainter, option, index) -> None:  # noqa: ANN001
        card = index.data(CARD_ROLE) or {}
        painter.save()
        rect = option.rect.adjusted(2, 2, -2, -2)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        hover = bool(option.state & QStyle.StateFlag.State_MouseOver)
        painter.setBrush(theme.color("surface_hover" if (hover or selected) else "surface"))
        painter.setPen(
            QPen(theme.color("accent"), 2) if selected else QPen(theme.color("border"), 1)
        )
        radius = theme.px("radius_card")
        painter.drawRoundedRect(rect, radius, radius)
        ink = theme.color("text")
        muted = theme.color("text_muted")
        left = rect.left() + 12
        # the first line: the name, and at its right the chips (format, licence) and the cross
        painter.setPen(ink)
        painter.drawText(self.remove_rect(rect), Qt.AlignmentFlag.AlignCenter, "×")
        x = rect.right() - 32
        font = painter.font()
        for text, kind in reversed(card.get("chips", [])):
            chip_w = painter.fontMetrics().horizontalAdvance(text) + 14
            chip = QRect(x - chip_w, rect.top() + 6, chip_w, 18)
            if chip.left() < left + 80:
                break  # the name keeps some room in a narrow list
            color = theme.color(CHIP_TOKENS.get(kind, CHIP_TOKENS["format"]))
            painter.setPen(QPen(color, 1))
            painter.setBrush(theme.color("surface_hover"))
            painter.drawRoundedRect(chip, 9, 9)
            painter.setPen(color)
            painter.drawText(chip, Qt.AlignmentFlag.AlignCenter, text)
            x = chip.left() - 6
        width = max(40, x - left - 4)
        bold = painter.font()
        bold.setBold(True)
        painter.setFont(bold)
        painter.setPen(ink)
        name = card.get("name") or str(index.data(Qt.ItemDataRole.UserRole) or "")
        painter.drawText(
            QRect(left, rect.top() + 5, width, 18),
            Qt.AlignmentFlag.AlignVCenter,
            painter.fontMetrics().elidedText(name, Qt.TextElideMode.ElideMiddle, width),
        )
        painter.setFont(font)
        # the second line: kind, files and size, or what is wrong with the pack
        below = rect.width() - 24
        action = card.get("action")
        if action:  # the group of a bundle: its packs can be chosen again
            action_w = painter.fontMetrics().horizontalAdvance(action)
            link = painter.font()
            link.setUnderline(True)
            painter.setFont(link)
            painter.setPen(theme.color("accent"))
            painter.drawText(
                self.choose_rect(rect, action_w), Qt.AlignmentFlag.AlignVCenter, action
            )
            painter.setFont(font)
            below -= action_w + 12
        error = card.get("error")
        if error:
            painter.setPen(theme.color("danger"))
            line = "⚠ " + error
            mode = Qt.TextElideMode.ElideRight
        else:
            painter.setPen(muted)
            line = card.get("detail") or str(index.data(Qt.ItemDataRole.UserRole) or "")
            mode = Qt.TextElideMode.ElideMiddle
        painter.drawText(
            QRect(left, rect.top() + 24, below, 16),
            Qt.AlignmentFlag.AlignVCenter,
            painter.fontMetrics().elidedText(line, mode, below),
        )
        painter.restore()

    def editorEvent(self, event, model, option, index) -> bool:  # noqa: ANN001
        if (
            event.type() == QEvent.Type.MouseButtonRelease
            and event.button() == Qt.MouseButton.LeftButton
        ):
            rect = option.rect.adjusted(2, 2, -2, -2)
            where = event.position().toPoint()
            if self.remove_rect(rect).contains(where):
                self.removeRequested.emit(index.row())
                return True
            action = (index.data(CARD_ROLE) or {}).get("action")
            if action:
                width = option.fontMetrics.horizontalAdvance(action)
                if self.choose_rect(rect, width).contains(where):
                    self.chooseRequested.emit(index.row())
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
        self.on_paths_dropped = lambda paths: None
        self.card_delegate = PackCardDelegate(self)
        self.setItemDelegate(self.card_delegate)
        self.setSpacing(1)

    def paintEvent(self, event) -> None:  # noqa: ANN001
        super().paintEvent(event)
        if self.count():
            return
        painter = QPainter(self.viewport())
        pen = QPen(theme.color("border_strong"))
        pen.setStyle(Qt.PenStyle.DashLine)
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawRoundedRect(self.viewport().rect().adjusted(6, 6, -6, -6), 6, 6)
        painter.setPen(theme.color("text_muted"))
        painter.drawText(
            self.viewport().rect(), Qt.AlignmentFlag.AlignCenter, self.tr(self.EMPTY_TEXT)
        )
        painter.end()

    def pack_items(self) -> list[QListWidgetItem]:
        """The rows that are packs (the row of a bundle's group is not one)."""
        items = [self.item(i) for i in range(self.count())]
        return [item for item in items if not item.data(GROUP_ROLE)]

    def paths(self) -> list[Path]:
        return [
            Path(item.data(Qt.ItemDataRole.UserRole) or item.text()) for item in self.pack_items()
        ]

    def add_path(self, path: Path | str) -> QListWidgetItem:
        """A pack at the end of the list. A pack taken from a bundle (``<archive>/<folder>``)
        goes to the end of its bundle's group, which is made when it is the first."""
        item = QListWidgetItem(str(path))
        item.setData(Qt.ItemDataRole.UserRole, str(path))
        member = pack_sniff.split_member(path)
        if member is None:
            self.addItem(item)
            return item
        bundle = str(member[0])
        item.setData(MEMBER_ROLE, bundle)
        rows = self.group_rows(bundle)
        if not rows:
            header = QListWidgetItem(member[0].name)
            header.setData(GROUP_ROLE, bundle)
            self.addItem(header)
            self.addItem(item)
        else:
            self.insertItem(rows[-1] + 1, item)
        return item

    def _bundle_of(self, row: int) -> str:
        item = self.item(row)
        return str(item.data(GROUP_ROLE) or item.data(MEMBER_ROLE) or "") if item else ""

    def group_rows(self, bundle: Path | str) -> list[int]:
        """The rows of a bundle's group: its own row first, then its packs."""
        key = str(bundle).casefold()
        return [row for row in range(self.count()) if self._bundle_of(row).casefold() == key]

    def bundle_at(self, row: int) -> Path | None:
        """The bundle of the group ``row`` is in (its own row or one of its packs)."""
        bundle = self._bundle_of(row)
        return Path(bundle) if bundle else None

    def bundles(self) -> list[Path]:
        """The bundles that have a group, in the order of the list."""
        rows = [self.item(row) for row in range(self.count())]
        return [Path(item.data(GROUP_ROLE)) for item in rows if item.data(GROUP_ROLE)]

    def remove_rows(self, rows: list[int]) -> None:
        """Take these rows out. The row of a group takes its packs with it, and a group whose
        last pack went goes too."""
        doomed = set(rows)
        for row in rows:
            item = self.item(row)
            if item is not None and item.data(GROUP_ROLE):
                doomed.update(self.group_rows(item.data(GROUP_ROLE)))
        for row in sorted(doomed, reverse=True):
            self.takeItem(row)
        for bundle in self.bundles():
            left = self.group_rows(bundle)
            if len(left) == 1:
                self.takeItem(left[0])

    def _set_dragging(self, on: bool) -> None:
        """The dashed border while a drag is over the list."""
        if bool(self.property("dragOver")) != on:
            self.setProperty("dragOver", on)
            theme.repolish(self)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            self._set_dragging(True)
            event.acceptProposedAction()

    def dragLeaveEvent(self, event) -> None:  # noqa: ANN001, N802
        self._set_dragging(False)
        super().dragLeaveEvent(event)

    def dragMoveEvent(self, event) -> None:  # noqa: ANN001
        event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        self._set_dragging(False)
        dropped = [Path(u.toLocalFile()) for u in event.mimeData().urls() if u.isLocalFile()]
        if dropped:
            self.on_paths_dropped(dropped)
            event.acceptProposedAction()
