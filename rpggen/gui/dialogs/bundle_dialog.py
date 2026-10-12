"""Choose packs (T16.22): the pack folders of a bundle as a checklist. Nothing is unpacked
here: the rows come from the listing of the archive (``pack_sniff.BundlePack``)."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rpggen.core.pack_sniff import BUNDLE_TICK_ALL, BundlePack
from rpggen.gui.models.project_model import format_size

COLUMNS = ("Pack", "Images", "Size")
MB = 1024 * 1024


class BundleDialog(QDialog):
    """One row per pack folder: its name, how many pictures it has and its size. ``ticked``
    is the choice the project has now (None the first time: every row is ticked for a bundle
    of ``BUNDLE_TICK_ALL`` folders or fewer, none above that). Accepting leaves the choice
    in ``chosen()``."""

    def __init__(
        self,
        bundle_name: str,
        packs: tuple[BundlePack, ...],
        ticked: set[str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("bundleDialog")
        self.setWindowTitle(self.tr("Choose packs"))
        self.resize(560, 480)
        self.packs = packs
        if ticked is None:
            ticked = {p.name for p in packs} if len(packs) <= BUNDLE_TICK_ALL else set()
        layout = QVBoxLayout(self)
        intro = QLabel(
            self.tr(
                "{0} holds {1} packs. Tick the ones to add: each becomes a pack of its own, "
                "and only those are unpacked."
            ).format(bundle_name, len(packs))
        )
        intro.setObjectName("bundleIntro")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setObjectName("bundleSearch")
        self.search.setPlaceholderText(self.tr("Search packs"))
        self.search.setToolTip(self.tr("Show the packs whose name has these words"))
        self.search.setClearButtonEnabled(True)
        top.addWidget(self.search, 1)
        self.all_button = QPushButton(self.tr("Select all"))
        self.all_button.setObjectName("bundleSelectAll")
        self.all_button.setToolTip(self.tr("Tick every pack that is shown"))
        self.none_button = QPushButton(self.tr("Select none"))
        self.none_button.setObjectName("bundleSelectNone")
        self.none_button.setToolTip(self.tr("Clear every pack that is shown"))
        for button in (self.all_button, self.none_button):
            button.setAutoDefault(False)  # Enter is the Add button's, wherever the focus is
            top.addWidget(button)
        layout.addLayout(top)
        self.table = QTableWidget(len(packs), len(COLUMNS))
        self.table.setObjectName("bundleTable")
        self.table.setAccessibleName(self.tr("The packs of the bundle"))
        self.table.setHorizontalHeaderLabels([self.tr(c) for c in COLUMNS])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setTabKeyNavigation(False)  # Tab leaves the list
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        right = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        for row, pack in enumerate(packs):
            name = QTableWidgetItem(pack.name)
            name.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
            )
            on = pack.name in ticked
            name.setCheckState(Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)
            self.table.setItem(row, 0, name)
            for column, text in ((1, str(pack.images)), (2, format_size(pack.bytes))):
                cell = QTableWidgetItem(text)
                cell.setTextAlignment(right)
                self.table.setItem(row, column, cell)
        self.table.resizeColumnToContents(1)
        self.table.resizeColumnToContents(2)
        layout.addWidget(self.table, 1)
        self.empty_label = QLabel(self.tr("No pack has these words."))
        self.empty_label.setObjectName("bundleEmpty")
        self.empty_label.setProperty("muted", True)
        self.empty_label.setVisible(False)
        layout.addWidget(self.empty_label)
        bottom = QHBoxLayout()
        self.total_label = QLabel()
        self.total_label.setObjectName("bundleTotal")
        bottom.addWidget(self.total_label, 1)
        box = QDialogButtonBox()
        self.add_button = box.addButton(self.tr("Add"), QDialogButtonBox.ButtonRole.AcceptRole)
        self.add_button.setObjectName("bundleAdd")
        self.cancel_button = box.addButton(
            self.tr("Cancel"), QDialogButtonBox.ButtonRole.RejectRole
        )
        self.cancel_button.setObjectName("bundleCancel")
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        bottom.addWidget(box)
        layout.addLayout(bottom)

        self.search.textChanged.connect(self._filter)
        self.table.itemChanged.connect(self._on_item_changed)
        self.all_button.clicked.connect(lambda: self.set_shown(True))
        self.none_button.clicked.connect(lambda: self.set_shown(False))
        self.search.installEventFilter(self)
        self.table.installEventFilter(self)
        QWidget.setTabOrder(self.search, self.all_button)
        QWidget.setTabOrder(self.all_button, self.none_button)
        QWidget.setTabOrder(self.none_button, self.table)
        self.search.setFocus()
        self._refresh_total()

    # ------------------------------------------------------------------ the choice

    def _name_item(self, row: int) -> QTableWidgetItem:
        item = self.table.item(row, 0)
        assert item is not None
        return item

    def is_ticked(self, row: int) -> bool:
        return self._name_item(row).checkState() == Qt.CheckState.Checked

    def set_ticked(self, row: int, on: bool) -> None:
        self._name_item(row).setCheckState(Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)

    def chosen(self) -> list[str]:
        """The names of the ticked pack folders, in the bundle's order (hidden rows too)."""
        return [p.name for row, p in enumerate(self.packs) if self.is_ticked(row)]

    def shown_rows(self) -> list[int]:
        return [r for r in range(self.table.rowCount()) if not self.table.isRowHidden(r)]

    def set_shown(self, on: bool) -> None:
        """*Select all* and *Select none*: the rows the search shows; a hidden row keeps its
        tick."""
        self.table.blockSignals(True)
        for row in self.shown_rows():
            self.set_ticked(row, on)
        self.table.blockSignals(False)
        self._refresh_total()

    # ------------------------------------------------------------------ search and total

    def _filter(self, text: str) -> None:
        words = text.casefold().split()
        for row, pack in enumerate(self.packs):
            name = pack.name.casefold()
            self.table.setRowHidden(row, not all(word in name for word in words))
        self.empty_label.setVisible(not self.shown_rows())

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() == 0:
            self._refresh_total()

    def _refresh_total(self) -> None:
        picked = [p for row, p in enumerate(self.packs) if self.is_ticked(row)]
        self.total_label.setText(
            self.tr("{0} of {1} packs · {2} images · {3} MB").format(
                len(picked),
                len(self.packs),
                sum(p.images for p in picked),
                f"{sum(p.bytes for p in picked) / MB:.1f}",
            )
        )
        self.add_button.setEnabled(bool(picked))

    # ------------------------------------------------------------------ keyboard

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt override
        """Down or Enter in the search field goes to the first row shown (Enter there would
        otherwise add at once); Space in the list ticks or clears the selected rows."""
        if event.type() == QEvent.Type.KeyPress and isinstance(event, QKeyEvent):
            key = event.key()
            if watched is self.search and key in (
                Qt.Key.Key_Down,
                Qt.Key.Key_Return,
                Qt.Key.Key_Enter,
            ):
                shown = self.shown_rows()
                if shown:
                    self.table.setFocus()
                    self.table.setCurrentCell(shown[0], 0)
                return True
            if watched is self.table and key == Qt.Key.Key_Space:
                rows = sorted({i.row() for i in self.table.selectedIndexes()})
                if rows:
                    current = self.table.currentRow()
                    on = not self.is_ticked(current if current in rows else rows[0])
                    for row in rows:
                        self.set_ticked(row, on)
                    return True
        return super().eventFilter(watched, event)
