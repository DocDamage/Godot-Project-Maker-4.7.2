"""The Audit page's Packs tab: the licence, author and URL of each pack, as read from its
licence files and corrected by the user. The game's Credits screen shows them (T12.51)."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from rpggen.core import licenses
from rpggen.core.catalog import CatalogPack
from rpggen.gui.edits import EditSession


class PackLicenseBox(QGroupBox):
    """One pack: licence, author, URL, "credit in the game", and a warning when a credit is
    required but no author is known."""

    def __init__(self, session: EditSession, pack_id: str, parent: QWidget | None = None) -> None:
        super().__init__(pack_id, parent)
        self.session = session
        self.pack_id = pack_id
        self.setObjectName(f"packInfo_{pack_id}")
        form = QFormLayout(self)
        self.license_combo = QComboBox()
        self.license_combo.setObjectName(f"packLicense_{pack_id}")
        self.license_combo.setToolTip(self.tr("The licence the pack's files name"))
        self.author_edit = QLineEdit()
        self.author_edit.setObjectName(f"packAuthor_{pack_id}")
        self.author_edit.setPlaceholderText(self.tr("Not found in the licence files"))
        self.author_edit.setToolTip(self.tr("Who made the pack: the Credits screen names them"))
        self.url_edit = QLineEdit()
        self.url_edit.setObjectName(f"packUrl_{pack_id}")
        self.url_edit.setPlaceholderText("https://")
        self.url_edit.setToolTip(self.tr("Where the pack comes from (shown on the Credits screen)"))
        self.credit_box = QCheckBox(
            self.tr("Credit the pack in the game (the licence asks for it)")
        )
        self.credit_box.setObjectName(f"packCredit_{pack_id}")
        self.files_label = QLabel()
        self.files_label.setObjectName(f"packLicenseFiles_{pack_id}")
        self.files_label.setWordWrap(True)
        self.files_label.setProperty("muted", True)
        self.warning = QLabel(
            self.tr("This licence asks for credit, but no author is known: enter who made it.")
        )
        self.warning.setObjectName(f"packCreditWarning_{pack_id}")
        self.warning.setWordWrap(True)
        self.warning.setProperty("state", "warning")
        form.addRow(self.tr("Licence"), self.license_combo)
        form.addRow(self.tr("Author"), self.author_edit)
        form.addRow(self.tr("URL"), self.url_edit)
        form.addRow("", self.credit_box)
        form.addRow("", self.warning)
        form.addRow("", self.files_label)
        self.license_combo.activated.connect(self._on_license)
        self.author_edit.editingFinished.connect(
            lambda: self._set("author", self.author_edit.text().strip())
        )
        self.url_edit.editingFinished.connect(
            lambda: self._set("url", self.url_edit.text().strip())
        )
        self.credit_box.toggled.connect(lambda on: self._set("attribution_required", on))

    def _set(self, key: str, value: object) -> None:
        self.session.set_pack_license(self.pack_id, key, value)

    def _on_license(self, index: int) -> None:
        self._set("license_id", str(self.license_combo.itemData(index) or ""))

    def show_pack(self, pack: CatalogPack) -> None:
        found = pack.effective_license()
        detected = licenses.PackLicense.from_json(pack.license)
        for widget in (self.license_combo, self.author_edit, self.url_edit, self.credit_box):
            widget.blockSignals(True)
        ids = list(dict.fromkeys([*licenses.KNOWN_IDS, detected.license_id, found.license_id]))
        ids = [i for i in ids if i != licenses.UNKNOWN] + [licenses.UNKNOWN]
        self.license_combo.clear()
        for license_id in ids:
            text = licenses.label(license_id)
            if license_id == detected.license_id:
                text += " " + self.tr("(found in the files)")
            self.license_combo.addItem(text, license_id)
        self.license_combo.setCurrentIndex(ids.index(found.license_id))
        if self.author_edit.text() != found.author:
            self.author_edit.setText(found.author)
        if self.url_edit.text() != found.url:
            self.url_edit.setText(found.url)
        self.credit_box.setChecked(found.attribution_required)
        for widget in (self.license_combo, self.author_edit, self.url_edit, self.credit_box):
            widget.blockSignals(False)
        self.warning.setVisible(found.attribution_required and not found.author.strip())
        files = ", ".join(f.rsplit("/", 1)[-1] for f in pack.license_files)
        self.files_label.setText(
            self.tr("Read from: {0}").format(files) if files else self.tr("No licence file found.")
        )


class PackInfoPanel(QWidget):
    """A box per pack of the catalog being audited."""

    def __init__(self, session: EditSession, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("packInfoPanel")
        self.session = session
        self.boxes: dict[str, PackLicenseBox] = {}
        self._layout = QVBoxLayout(self)
        intro = QLabel(
            self.tr(
                "What the licence files of each pack say. Correct anything that is wrong: the "
                "game's Credits screen lists every pack with its author and licence."
            )
        )
        intro.setWordWrap(True)
        intro.setProperty("muted", True)
        self._layout.addWidget(intro)
        self._layout.addStretch(1)
        session.changed.connect(lambda _ids: self.refresh())
        self.refresh()

    def refresh(self) -> None:
        packs = sorted(self.session.catalog.packs, key=lambda p: p.pack_id.casefold())
        if [p.pack_id for p in packs] != list(self.boxes):
            for box in self.boxes.values():
                self._layout.removeWidget(box)
                box.deleteLater()
            self.boxes = {}
            for pack in packs:
                box = PackLicenseBox(self.session, pack.pack_id, self)
                self._layout.insertWidget(self._layout.count() - 1, box)
                self.boxes[pack.pack_id] = box
        for pack in packs:
            self.boxes[pack.pack_id].show_pack(pack)
