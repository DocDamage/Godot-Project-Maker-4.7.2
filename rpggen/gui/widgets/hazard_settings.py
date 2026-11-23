"""Project-owned, individual tile hazard overrides; no damage inferred from artwork."""

from __future__ import annotations

import copy

from PySide6.QtWidgets import QCheckBox, QDoubleSpinBox, QFormLayout, QSpinBox, QWidget

from rpggen.core import catalog as catalog_mod
from rpggen.gui.edits import EditSession


class HazardSettings(QWidget):
    def __init__(self, session: EditSession) -> None:
        super().__init__()
        self.session = session
        self.asset_id = ""
        self.loading = False
        form = QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)
        self.column, self.row = QSpinBox(), QSpinBox()
        self.column.setObjectName("hazardColumn")
        self.row.setObjectName("hazardRow")
        for label, spin in (("Tile column", self.column), ("Tile row", self.row)):
            spin.setRange(0, 4095)
            form.addRow(self.tr(label), spin)
            spin.valueChanged.connect(self.refresh)
        self.enabled = QCheckBox(self.tr("Damages the player"))
        self.enabled.setObjectName("hazardEnabled")
        form.addRow(self.enabled)
        self.damage = QSpinBox()
        self.damage.setObjectName("hazardDamage")
        self.damage.setRange(1, 99999)
        self.cooldown = QDoubleSpinBox()
        self.cooldown.setObjectName("hazardCooldown")
        self.cooldown.setRange(0.05, 3600)
        self.cooldown.setDecimals(2)
        self.cooldown.setSuffix(self.tr(" s"))
        form.addRow(self.tr("Damage per hit"), self.damage)
        form.addRow(self.tr("Time between hits"), self.cooldown)
        self.setToolTip(
            self.tr("Applies only to this tile in this project. Columns and rows start at zero.")
        )
        self.enabled.toggled.connect(self.save)
        self.damage.valueChanged.connect(self.save)
        self.cooldown.valueChanged.connect(self.save)

    def load_asset(self, asset_id: str, facets: dict) -> None:
        if asset_id != self.asset_id:
            self.loading = True
            self.column.setValue(0)
            self.row.setValue(0)
            self.loading = False
        self.asset_id = asset_id
        iso = facets.get("usage") == "iso_tile"
        self.column.setEnabled(not iso)
        self.row.setEnabled(not iso)
        if iso:
            self.column.setValue(0)
            self.row.setValue(0)
        else:
            grid = facets.get("grid") or {}
            cell = grid.get("cell", [16, 16])
            size = facets.get("size", cell)
            margin = grid.get("margin", [0, 0])
            gap = grid.get("separation", [0, 0])
            self.column.setMaximum(
                max(0, (size[0] - margin[0] + gap[0]) // max(1, cell[0] + gap[0]) - 1)
            )
            self.row.setMaximum(
                max(0, (size[1] - margin[1] + gap[1]) // max(1, cell[1] + gap[1]) - 1)
            )
        self.refresh()

    def key(self) -> str:
        return f"{self.column.value()},{self.row.value()}"

    def refresh(self) -> None:
        if self.loading or not self.asset_id:
            return
        asset = self.session.catalog.asset(self.asset_id)
        if asset is None:
            return
        facets = catalog_mod.effective(asset)
        custom = (facets.get("tile_overrides") or {}).get(self.key(), {}).get("custom", {})
        self.loading = True
        self.enabled.setChecked(bool(custom.get("hazard", "hazard" in (facets.get("tags") or []))))
        self.damage.setValue(int(custom.get("hazard_damage", 1)))
        self.cooldown.setValue(float(custom.get("hazard_cooldown", 1.0)))
        self.damage.setEnabled(self.enabled.isChecked())
        self.cooldown.setEnabled(self.enabled.isChecked())
        self.loading = False

    def save(self) -> None:
        if self.loading or not self.asset_id:
            return
        asset = self.session.catalog.asset(self.asset_id)
        if asset is None:
            return
        overrides = copy.deepcopy(catalog_mod.effective(asset).get("tile_overrides") or {})
        custom = overrides.setdefault(self.key(), {}).setdefault("custom", {})
        custom.update(
            hazard=self.enabled.isChecked(),
            hazard_damage=self.damage.value(),
            hazard_cooldown=self.cooldown.value(),
        )
        self.session.set_override(self.asset_id, "tile_overrides", overrides)
        self.refresh()
