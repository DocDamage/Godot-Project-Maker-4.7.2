"""Dialogs of the Options page: managing presets and choosing the solid IntGrid values."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class ManagePresetsDialog(QDialog):
    """Rename and delete the saved presets."""

    def __init__(self, names: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("managePresets")
        self.setWindowTitle(self.tr("Manage presets"))
        self.resize(360, 300)
        self.renames: dict[str, str] = {}  # old name -> new name
        self.deleted: list[str] = []
        layout = QVBoxLayout(self)
        self.list = QListWidget()
        self.list.setObjectName("presetList")
        self.list.addItems(names)
        layout.addWidget(self.list)
        row = QHBoxLayout()
        self.rename_button = QPushButton(self.tr("Rename…"))
        self.rename_button.setObjectName("renamePreset")
        self.delete_button = QPushButton(self.tr("Delete"))
        self.delete_button.setObjectName("deletePreset")
        row.addWidget(self.rename_button)
        row.addWidget(self.delete_button)
        row.addStretch(1)
        layout.addLayout(row)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.rename_button.clicked.connect(self.rename_current)
        self.delete_button.clicked.connect(self.delete_current)

    def ask_name(self, current: str) -> str | None:  # overridden by tests
        text, ok = QInputDialog.getText(
            self, self.tr("Rename preset"), self.tr("New name"), text=current
        )
        return text.strip() if ok and text.strip() else None

    def rename_current(self) -> None:
        item = self.list.currentItem()
        if item is None:
            return
        new = self.ask_name(item.text())
        names = [self.list.item(i).text() for i in range(self.list.count())]
        if new is None or new == item.text() or new in names or new == self.tr("Defaults"):
            return
        self.renames[item.text()] = new
        item.setText(new)

    def delete_current(self) -> None:
        row = self.list.currentRow()
        if row < 0:
            return
        self.deleted.append(self.list.takeItem(row).text())


class SolidValuesDialog(QDialog):
    """Which values of the IntGrid layers of the imported maps block the player."""

    def __init__(self, rows: list[dict[str, Any]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("solidValues")
        self.setWindowTitle(self.tr("Solid values"))
        self.resize(520, 340)
        layout = QVBoxLayout(self)
        text = QLabel(
            self.tr(
                "A checked value of an LDtk IntGrid layer is solid: it becomes collision on the "
                "imported map."
            )
        )
        text.setWordWrap(True)
        layout.addWidget(text)
        self.list = QListWidget()
        self.list.setObjectName("solidList")
        for row in rows:
            item = QListWidgetItem(row["label"])
            item.setData(Qt.ItemDataRole.UserRole, (row["map"], row["layer"], int(row["value"])))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if row["solid"] else Qt.CheckState.Unchecked)
            self.list.addItem(item)
        layout.addWidget(self.list)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def choices(self) -> dict[tuple[str, str, int], bool]:
        out: dict[tuple[str, str, int], bool] = {}
        for i in range(self.list.count()):
            item = self.list.item(i)
            out[item.data(Qt.ItemDataRole.UserRole)] = item.checkState() == Qt.CheckState.Checked
        return out
