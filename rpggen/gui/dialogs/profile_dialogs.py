"""Dialogs of the pack profile feature."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from rpggen.core import profiles


class ExportProfileDialog(QDialog):
    """Asks for the pack, title, author and license of a profile to export."""

    def __init__(
        self,
        pack_ids: list[str],
        default_title: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("exportProfileDialog")
        self.setWindowTitle(self.tr("Export pack profile"))
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                self.tr(
                    "A profile stores your audit decisions for a pack, so anyone who owns the "
                    "same pack gets them automatically. It contains no images."
                )
            )
        )
        form = QFormLayout()
        self.pack_combo = QComboBox()
        self.pack_combo.setObjectName("profilePack")
        self.pack_combo.addItems(pack_ids)
        self.title_edit = QLineEdit(default_title)
        self.title_edit.setObjectName("profileTitle")
        self.author_edit = QLineEdit()
        self.author_edit.setObjectName("profileAuthor")
        self.license_edit = QLineEdit(profiles.DEFAULT_LICENSE)
        self.license_edit.setObjectName("profileLicense")
        if len(pack_ids) > 1:
            form.addRow(self.tr("Pack"), self.pack_combo)
        form.addRow(self.tr("Title"), self.title_edit)
        form.addRow(self.tr("Author"), self.author_edit)
        form.addRow(self.tr("License"), self.license_edit)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.title_edit.textChanged.connect(self._update_ok)
        self._update_ok()

    def _update_ok(self) -> None:
        self.ok_button.setEnabled(bool(self.title_edit.text().strip()))

    def pack_id(self) -> str:
        return self.pack_combo.currentText()

    def meta(self) -> dict[str, str]:
        return {
            "title": self.title_edit.text().strip(),
            "author": self.author_edit.text().strip(),
            "license": self.license_edit.text().strip() or profiles.DEFAULT_LICENSE,
        }
