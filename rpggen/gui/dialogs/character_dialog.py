"""Audit → Compose LPC character…: choose the layers that go over a body (M16)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from rpggen.core import catalog as catalog_mod
from rpggen.core import lpc_compose
from rpggen.core.adapters import lpc

PREVIEW_SCALE = 4
PREVIEW_ROW = lpc.BY_NAME["walk"].row + lpc.LPC_DIRECTIONS.index("down")


def _short(asset: catalog_mod.Asset, pack_id: str) -> str:
    """The layer's name without the pack and the file every layer shares: ``hair/afro/adult``."""
    text = asset.path.split("/", 3)[-1].rsplit(".", 1)[0]
    for ending in ("/walk",):
        if text.endswith(ending):
            text = text[: -len(ending)]
    return text.replace("/walk/", "/").removeprefix("spritesheets/")


class CharacterDialog(QDialog):
    """One body, and for every part of a character the layers that fit it. The preview is the
    character as it stands, looking at the player."""

    def __init__(
        self,
        catalog: catalog_mod.Catalog,
        body: catalog_mod.Asset,
        pack_roots: dict[str, Path],
        definition: dict[str, Any] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("characterDialog")
        self.setWindowTitle(self.tr("Compose LPC character"))
        self.catalog, self.body, self.pack_roots = catalog, body, pack_roots
        self.existing = definition
        chosen = set(definition["layers"]) if definition else set()
        outer = QHBoxLayout(self)

        left = QVBoxLayout()
        self.preview = QLabel()
        self.preview.setObjectName("characterPreview")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setFixedSize(lpc.FRAME * PREVIEW_SCALE, lpc.FRAME * PREVIEW_SCALE)
        self.preview.setAccessibleName(self.tr("The character, looking at you"))
        left.addWidget(self.preview)
        left.addStretch(1)
        outer.addLayout(left)

        right = QVBoxLayout()
        intro = QLabel(
            self.tr(
                "An LPC character is a body with layers drawn over it. Choose one of each part, "
                "or none; the character becomes an asset of its own."
            )
        )
        intro.setWordWrap(True)
        intro.setProperty("role", "muted")
        right.addWidget(intro)
        form = QFormLayout()
        self.name_edit = QLineEdit(definition["name"] if definition else self._default_name())
        self.name_edit.setObjectName("characterName")
        self.name_edit.setToolTip(self.tr("The name of the character in the audit"))
        form.addRow(self.tr("Name"), self.name_edit)
        self.combos: dict[str, QComboBox] = {}
        for part, layers in lpc_compose.layers_for(catalog, body).items():
            combo = QComboBox()
            combo.setObjectName(f"part_{part}")
            combo.setToolTip(self.tr("The {0} layer of the character, or none").format(part))
            combo.addItem(self.tr("(none)"), "")
            for layer in layers:
                combo.addItem(_short(layer, body.pack_id), layer.id)
            picked = next((layer.id for layer in layers if layer.id in chosen), None)
            if picked is None and definition is None and len(layers) == 1:
                picked = layers[0].id  # no choice to make: it is on
            combo.setCurrentIndex(max(0, combo.findData(picked or "")))
            combo.currentIndexChanged.connect(self._refresh)
            self.combos[part] = combo
            form.addRow(part.replace("_", " ").capitalize(), combo)
        right.addLayout(form)
        self.note = QLabel()
        self.note.setObjectName("characterNote")
        self.note.setWordWrap(True)
        self.note.setProperty("role", "muted")
        right.addWidget(self.note)
        right.addStretch(1)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        right.addWidget(self.buttons)
        outer.addLayout(right, 1)
        self.name_edit.textChanged.connect(self._refresh)
        self._refresh()

    def _default_name(self) -> str:
        return (lpc_compose.build_of(self.body) or "character").capitalize()

    def layers(self) -> list[str]:
        """The ids of the layers that are chosen, in the order of the form."""
        return [str(c.currentData()) for c in self.combos.values() if c.currentData()]

    def definition(self) -> dict[str, Any]:
        name = self.name_edit.text().strip() or self._default_name()
        if self.existing is not None:
            ident = str(self.existing["id"])
        else:
            taken = {a.id for a in self.catalog.assets} | {
                str(d.get("id")) for d in self.catalog.characters
            }
            ident = lpc_compose.new_id(taken, self.body.pack_id, name)
        return {"id": ident, "name": name, "body": self.body.id, "layers": self.layers()}

    def _refresh(self, *_args: object) -> None:
        parts = [self.body, *(a for a in map(self.catalog.asset, self.layers()) if a is not None)]
        ok = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        try:
            sheet = lpc_compose.render(parts, self.pack_roots)
        except (lpc_compose.CharacterError, OSError, ValueError) as exc:
            self.preview.clear()
            self.note.setText(self.tr("This character cannot be drawn: {0}").format(str(exc)))
            ok.setEnabled(False)
            return
        ok.setEnabled(bool(self.name_edit.text().strip()))
        top = PREVIEW_ROW * lpc.FRAME
        if sheet.height < top + lpc.FRAME:
            top = 0
        frame = sheet.crop((0, top, lpc.FRAME, top + lpc.FRAME))
        image = QImage(
            frame.tobytes("raw", "RGBA"), frame.width, frame.height, QImage.Format.Format_RGBA8888
        ).copy()
        self.preview.setPixmap(
            QPixmap.fromImage(image).scaled(
                self.preview.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
        )
        count = len(self.layers())
        self.note.setText(
            self.tr("The body alone.")
            if count == 0
            else self.tr("The body and {0} layer(s).").format(count)
        )
