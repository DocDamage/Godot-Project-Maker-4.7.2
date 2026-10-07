"""Dialogs of the pack profile feature."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QVBoxLayout,
    QWidget,
)

from rpggen.core import profile_registry, profiles


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


class FindProfileDialog(QDialog):
    """Lists the registry profiles that match the user's packs; the user picks one."""

    def __init__(self, found: list[profile_registry.Candidate], parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("findProfileDialog")
        self.setWindowTitle(self.tr("Find profile online"))
        self.found = found
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                self.tr(
                    "These community profiles match your packs. A profile only holds audit "
                    "decisions (no images); it is checked before it is installed."
                )
            )
        )
        self.list = QListWidget()
        self.list.setObjectName("profileCandidates")
        for c in found:
            by = f" - {c.author}" if c.author else ""
            self.list.addItem(f"{c.title}{by} ({round(c.overlap * 100)}% match, {c.license})")
        if found:
            self.list.setCurrentRow(0)
        layout.addWidget(self.list)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self.tr("Install"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected(self) -> profile_registry.Candidate | None:
        row = self.list.currentRow()
        return self.found[row] if 0 <= row < len(self.found) else None
