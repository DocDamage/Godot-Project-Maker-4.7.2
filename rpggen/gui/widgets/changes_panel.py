"""The audit page's "Changes (n)" tab: what was changed since the analysis, each with a Revert."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rpggen.core import labels
from rpggen.gui import edits
from rpggen.gui.edits import Change, EditSession

KIND_LABELS = {
    "role": "Role",
    "excluded": "Excluded",
    "grid": "Grid",
    "collision": "Collision",
    "animations": "Animations",
    "objects": "Objects",
    "rules": "Folder rules",
    "other": "Other",
}
MAX_VALUE = 60


def format_value(key: str, value: Any) -> str:
    """A short, readable form of a facet value for the before / after columns."""
    if value is None:
        return "—"
    if key == "role" and isinstance(value, str):
        return labels.role_label(value)
    if isinstance(value, dict):
        if key == "animations":
            return f"{len(value)} animations"
        if key == "grid" and "cell" in value:
            return "cells " + "x".join(str(n) for n in value["cell"])
        if key == "collision" and "profile" in value:
            return str(value["profile"])
        text = ", ".join(f"{k}: {v}" for k, v in value.items())
    elif isinstance(value, list):
        text = ", ".join(str(v) for v in value)
    else:
        text = str(value)
    return text if len(text) <= MAX_VALUE else text[: MAX_VALUE - 1] + "…"


class ChangesPanel(QWidget):
    """A table of ``edits.describe_changes`` with a kind filter and a Revert button per row."""

    countChanged = Signal(int)  # noqa: N815 - the number of changes (all kinds)
    assetActivated = Signal(str)  # noqa: N815 - double click: the asset to show in the grid

    def __init__(self, session: EditSession, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("changesPanel")
        self.session = session
        self.changes: list[Change] = []  # all of them
        self.shown: list[Change] = []  # after the filter
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.summary_label = QLabel()
        self.summary_label.setObjectName("changesSummary")
        top.addWidget(self.summary_label, 1)
        top.addWidget(QLabel(self.tr("Show")))
        self.kind_filter = QComboBox()
        self.kind_filter.setObjectName("changesKind")
        self.kind_filter.setToolTip(self.tr("Show only one kind of change"))
        self.kind_filter.addItem(self.tr("All changes"), "")
        for kind in edits.CHANGE_KINDS:
            self.kind_filter.addItem(self.tr(KIND_LABELS[kind]), kind)
        top.addWidget(self.kind_filter)
        layout.addLayout(top)
        self.table = QTableWidget(0, 5)
        self.table.setObjectName("changesTable")
        self.table.setHorizontalHeaderLabels(
            [self.tr("Kind"), self.tr("What"), self.tr("Detected"), self.tr("Now"), ""]
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setToolTip(self.tr("Double-click a row to select the asset in the grid"))
        layout.addWidget(self.table, 1)
        self.empty_label = QLabel(self.tr("Nothing has been changed since the analysis."))
        self.empty_label.setObjectName("changesEmpty")
        self.empty_label.setProperty("muted", True)
        layout.addWidget(self.empty_label)
        self.kind_filter.currentIndexChanged.connect(lambda _i: self._fill())
        self.table.cellDoubleClicked.connect(self._on_double_clicked)
        session.changed.connect(lambda _ids: self.refresh())
        self.refresh()

    # ------------------------------------------------------------------ content

    def count(self) -> int:
        """How many changes there are, whatever the filter."""
        return len(self.changes)

    def refresh(self) -> None:
        """Re-read the catalog (called on every edit, undo and redo)."""
        self.changes = edits.describe_changes(self.session.catalog)
        self._fill()
        self.countChanged.emit(len(self.changes))

    def _fill(self) -> None:
        kind = self.kind_filter.currentData()
        self.shown = [c for c in self.changes if not kind or c.kind == kind]
        self.table.setRowCount(len(self.shown))
        for row, change in enumerate(self.shown):
            cells = (
                self.tr(KIND_LABELS.get(change.kind, change.kind)),
                change.label,
                format_value(change.key, change.before),
                format_value(change.key, change.after),
            )
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setToolTip(text)
                self.table.setItem(row, col, item)
            button = QPushButton(self.tr("Revert"))
            button.setObjectName(f"revert_{row}")
            button.setToolTip(self.tr("Put the detected value back (one undo step)"))
            button.clicked.connect(lambda _=False, c=change: self.revert(c))
            self.table.setCellWidget(row, 4, button)
        self.summary_label.setText(
            self.tr("{0} change(s) since the analysis").format(len(self.changes))
        )
        self.empty_label.setVisible(not self.changes)
        self.table.setVisible(bool(self.changes))

    def revert(self, change: Change) -> bool:
        return self.session.revert(change)

    def _on_double_clicked(self, row: int, _col: int) -> None:
        if 0 <= row < len(self.shown) and self.shown[row].asset_id:
            self.assetActivated.emit(self.shown[row].asset_id)

    def row_texts(self) -> list[tuple[str, str, str, str]]:
        """(kind, what, detected, now) of the rows shown, for tests."""

        def text(row: int, col: int) -> str:
            item = self.table.item(row, col)
            return item.text() if item is not None else ""

        return [
            (text(r, 0), text(r, 1), text(r, 2), text(r, 3)) for r in range(self.table.rowCount())
        ]
