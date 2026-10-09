"""Options of the contact sheet export (T12.57): format, paper, which assets, grid overlay."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from rpggen.core import contact_sheet


@dataclass(frozen=True)
class SheetOptions:
    fmt: str  # "pdf" or "png"
    paper: str  # "A4" or "Letter"
    filtered: bool  # the audit's filtered set, else every asset
    grid_overlay: bool


class ContactSheetDialog(QDialog):
    def __init__(self, shown: int, total: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("contactSheetDialog")
        self.setWindowTitle(self.tr("Export contact sheet"))
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.format_combo = QComboBox()
        self.format_combo.setObjectName("sheetFormat")
        self.format_combo.addItem(self.tr("PDF (one file)"), "pdf")
        self.format_combo.addItem(self.tr("PNG (one file per page)"), "png")
        form.addRow(self.tr("Format"), self.format_combo)
        self.paper_combo = QComboBox()
        self.paper_combo.setObjectName("sheetPaper")
        for paper in contact_sheet.PAPERS:
            self.paper_combo.addItem(paper, paper)
        form.addRow(self.tr("Paper"), self.paper_combo)
        layout.addLayout(form)
        self.filtered_radio = QRadioButton(
            self.tr("The assets shown now ({0}, as filtered)").format(shown)
        )
        self.filtered_radio.setObjectName("sheetFiltered")
        self.all_radio = QRadioButton(self.tr("All assets ({0})").format(total))
        self.all_radio.setObjectName("sheetAll")
        group = QButtonGroup(self)
        group.addButton(self.filtered_radio)
        group.addButton(self.all_radio)
        (self.filtered_radio if shown < total else self.all_radio).setChecked(True)
        layout.addWidget(self.filtered_radio)
        layout.addWidget(self.all_radio)
        self.grid_box = QCheckBox(self.tr("Draw the tile and frame grid over the pictures"))
        self.grid_box.setObjectName("sheetGrid")
        layout.addWidget(self.grid_box)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok is not None:
            ok.setText(self.tr("Export…"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def options(self) -> SheetOptions:
        return SheetOptions(
            str(self.format_combo.currentData()),
            str(self.paper_combo.currentData()),
            self.filtered_radio.isChecked(),
            self.grid_box.isChecked(),
        )
