"""The audit page's "Terrain" tab: review terrain proposals (T8.06c) and accept or reject them."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from rpggen.core import catalog as catalog_mod
from rpggen.core.terrain import blob
from rpggen.gui.edits import EditSession
from rpggen.gui.widgets.asset_grid import PathResolver
from rpggen.gui.widgets.image_view import ImageView

BIT_COLOR = QColor(0, 220, 120, 190)
# peering key -> (x, y) position inside the 3x3 cell: sides on the edges, corners in the corners
BIT_POSITIONS = {
    "top_left_corner": (0, 0),
    "top_side": (1, 0),
    "top_right_corner": (2, 0),
    "left_side": (0, 1),
    "right_side": (2, 1),
    "bottom_left_corner": (0, 2),
    "bottom_side": (1, 2),
    "bottom_right_corner": (2, 2),
}


class TerrainTab(QWidget):
    """Lists the assets with a ``terrain_proposal`` and shows the proposed peering bitmask over
    the sheet. Accept moves it into the asset's overrides, Reject hides it (both undoable)."""

    changed = Signal()

    def __init__(self, session: EditSession, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.session = session
        self.resolver: PathResolver = lambda asset: None
        self.setObjectName("terrainTab")
        layout = QHBoxLayout(self)
        left = QVBoxLayout()
        self.list = QListWidget()
        self.list.setObjectName("terrainList")
        left.addWidget(self.list)
        self.info = QLabel(self.tr("No terrain proposals."))
        self.info.setObjectName("terrainInfo")
        self.info.setWordWrap(True)
        left.addWidget(self.info)
        buttons = QHBoxLayout()
        self.accept_button = QPushButton(self.tr("Accept"))
        self.accept_button.setObjectName("terrainAccept")
        self.reject_button = QPushButton(self.tr("Reject"))
        self.reject_button.setObjectName("terrainReject")
        buttons.addWidget(self.accept_button)
        buttons.addWidget(self.reject_button)
        left.addLayout(buttons)
        layout.addLayout(left, 1)
        self.view = ImageView("terrainView")
        layout.addWidget(self.view, 3)
        self.list.currentItemChanged.connect(lambda *_: self._show_current())
        session.changed.connect(lambda _ids: self.refresh())
        self.accept_button.clicked.connect(self.accept_current)
        self.reject_button.clicked.connect(self.reject_current)
        self._set_buttons(False)

    # ------------------------------------------------------------------ model

    def proposal_ids(self) -> list[str]:
        return [a.id for a in self.session.catalog.assets if blob.has_proposal(a)]

    def refresh(self) -> None:
        """Rebuild the list from the catalog, keeping the selection when it still exists."""
        current = self.current_id()
        self.list.blockSignals(True)
        self.list.clear()
        for asset_id in self.proposal_ids():
            asset = self.session.catalog.asset(asset_id)
            assert asset is not None
            proposal = catalog_mod.effective(asset)["terrain_proposal"]
            item = QListWidgetItem(f"{asset_id}  ({proposal['confidence']:.0%})")
            item.setData(Qt.ItemDataRole.UserRole, asset_id)
            self.list.addItem(item)
        self.list.blockSignals(False)
        row = next(
            (i for i in range(self.list.count()) if self._id_at(i) == current),
            0 if self.list.count() else -1,
        )
        self.list.setCurrentRow(row)
        self._show_current()

    def _id_at(self, row: int) -> str:
        return str(self.list.item(row).data(Qt.ItemDataRole.UserRole))

    def current_id(self) -> str | None:
        item = self.list.currentItem()
        return str(item.data(Qt.ItemDataRole.UserRole)) if item else None

    def _set_buttons(self, enabled: bool) -> None:
        self.accept_button.setEnabled(enabled)
        self.reject_button.setEnabled(enabled)

    # ------------------------------------------------------------------ view

    def _show_current(self) -> None:
        asset_id = self.current_id()
        asset = self.session.catalog.asset(asset_id) if asset_id else None
        self.view.set_image(None)
        if asset is None or not blob.has_proposal(asset):
            self.info.setText(self.tr("No terrain proposals."))
            self._set_buttons(False)
            return
        eff = catalog_mod.effective(asset)
        proposal = eff["terrain_proposal"]
        self.info.setText(
            self.tr(
                "Layout {layout}, confidence {confidence}, {count} tiles. Review the bitmask, "
                "then accept or reject."
            ).format(
                layout=proposal["layout"],
                confidence=f"{proposal['confidence']:.0%}",
                count=len(proposal["tile_overrides"]),
            )
        )
        self._set_buttons(True)
        path = self.resolver(asset)
        self.view.set_image(path, None)
        grid = eff.get("grid") or {}
        if self.view.image_size[0] and grid.get("cell"):
            self._draw_bitmask(grid["cell"], proposal["tile_overrides"])

    def _draw_bitmask(self, cell: list[int], tile_overrides: dict) -> None:
        scene = self.view.scene()
        cw, ch = cell
        pen = QPen(Qt.PenStyle.NoPen)
        brush = QBrush(BIT_COLOR)
        for key, entry in tile_overrides.items():
            col, row = (int(v) for v in key.split(","))
            peering = entry.get("terrain", {}).get("peering", {})
            for name, (px, py) in BIT_POSITIONS.items():
                if peering.get(name, -1) < 0:
                    continue
                w, h = cw / 3, ch / 3
                item = scene.addRect(col * cw + px * w, row * ch + py * h, w, h, pen, brush)
                self.view.grid_items.append(item)

    # ------------------------------------------------------------------ actions

    def accept_current(self) -> bool:
        asset_id = self.current_id()
        if asset_id is None:
            return False
        done = self.session.apply(
            "Accept terrain", lambda c: blob.accept_in_catalog(c, asset_id), [asset_id]
        )
        self.changed.emit()
        return done

    def reject_current(self) -> bool:
        asset_id = self.current_id()
        if asset_id is None:
            return False
        done = self.session.apply(
            "Reject terrain", lambda c: blob.reject_in_catalog(c, asset_id), [asset_id]
        )
        self.changed.emit()
        return done
