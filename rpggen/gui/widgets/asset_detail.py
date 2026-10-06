"""The audit page's detail panel: a zoomable preview and the editable facets of one asset."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QPen, QPixmap, QWheelEvent
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from rpggen.core import catalog as catalog_mod
from rpggen.gui.edits import EditSession
from rpggen.gui.widgets.asset_grid import STATUS_COLORS, PathResolver

USAGES = ["tiles", "sprite", "object", "ui", "portrait", "background", "audio", "font"]
ROLES = [
    "GROUND",
    "WALL",
    "CLIFF",
    "WATER",
    "ROAD",
    "AUTOTILE",
    "DECORATION",
    "BUILDING",
    "INTERIOR",
    "PLAYER",
    "NPC",
    "ENEMY",
    "BOSS",
    "WEAPON",
    "ITEM",
    "EFFECT",
    "PROJECTILE",
    "UI",
    "PORTRAIT",
    "BACKGROUND",
    "AUDIO_MUSIC",
    "AUDIO_SFX",
    "FONT",
    "NONE",
]
COLLISION_PROFILES = [
    "NONE",
    "FULL",
    "BOTTOM_HALF",
    "BOTTOM_EDGE",
    "TOP_EDGE",
    "LEFT_EDGE",
    "RIGHT_EDGE",
    "ALPHA_POLYGON",
]
COLLISION_USAGES = {"tiles", "object"}
GRID_USAGES = {"tiles", "sprite"}
ALT_BUTTONS = 3
NEW_TILESET = "New…"
UNCHANGED = "— detected —"


class ImagePreview(QGraphicsView):
    """Nearest-neighbor image view; Ctrl+wheel zooms; optionally overlays a grid."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("assetPreview")
        self.setScene(QGraphicsScene(self))
        self.setBackgroundBrush(QColor(60, 60, 60))
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.zoom = 1.0
        self._pixmap_item = None
        self.grid_items: list = []

    def set_image(self, path: Path | None, grid: dict | None = None) -> None:
        scene = self.scene()
        scene.clear()
        self.grid_items = []
        self._pixmap_item = None
        if path is None or not Path(path).exists():
            return
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return
        self._pixmap_item = scene.addPixmap(pixmap)  # SmoothTransformation stays off
        scene.setSceneRect(self._pixmap_item.boundingRect())
        if grid:
            self.draw_grid(grid, pixmap.width(), pixmap.height())
        self.fit()

    def draw_grid(self, grid: dict, width: int, height: int) -> None:
        pen = QPen(QColor(255, 255, 255, 140))
        pen.setCosmetic(True)
        cw, ch = grid["cell"]
        mx, my = grid.get("margin", [0, 0])
        sx, sy = grid.get("separation", [0, 0])
        scene = self.scene()
        x = mx
        while x <= width:
            self.grid_items.append(scene.addLine(x, 0, x, height, pen))
            x += cw + sx if sx else cw
        y = my
        while y <= height:
            self.grid_items.append(scene.addLine(0, y, width, y, pen))
            y += ch + sy if sy else ch

    def fit(self) -> None:
        if self._pixmap_item is None:
            return
        self.resetTransform()
        rect = self._pixmap_item.boundingRect()
        if rect.width() <= 0 or rect.height() <= 0:
            return
        view = self.viewport().size()
        scale = min(max(view.width(), 64) / rect.width(), max(view.height(), 64) / rect.height())
        scale = max(1.0, float(int(scale))) if scale >= 1 else scale
        self.zoom = scale
        self.scale(scale, scale)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.25 if event.angleDelta().y() > 0 else 0.8
            self.zoom *= factor
            self.scale(factor, factor)
            event.accept()
        else:
            super().wheelEvent(event)


class AssetDetail(QWidget):
    """Edits one asset through the ``EditSession`` (never mutates the catalog itself)."""

    gridEditRequested = Signal(str)  # noqa: N815
    animationsRequested = Signal(str)  # noqa: N815
    cutObjectsRequested = Signal(str)  # noqa: N815

    def __init__(self, session: EditSession, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("assetDetail")
        self.session = session
        self.resolver: PathResolver = lambda asset: None
        self.asset_id: str | None = None
        self._loading = False

        layout = QVBoxLayout(self)
        self.preview = ImagePreview()
        self.preview.setMinimumHeight(180)
        layout.addWidget(self.preview, 2)

        form = QFormLayout()
        layout.addLayout(form)
        self.path_label = QLabel()
        self.path_label.setObjectName("pathLabel")
        self.path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.show_folder_button = QPushButton(self.tr("Show in folder"))
        self.show_folder_button.setObjectName("showFolderButton")
        row = QHBoxLayout()
        row.addWidget(self.path_label, 1)
        row.addWidget(self.show_folder_button)
        form.addRow(self.tr("Path"), row)
        self.pack_label = QLabel()
        self.pack_label.setObjectName("packLabel")
        form.addRow(self.tr("Pack"), self.pack_label)

        self.usage_combo = self._combo("usageCombo", USAGES)
        form.addRow(self.tr("Usage"), self.usage_combo)
        self.role_combo = self._combo("roleCombo", ROLES)
        self.alt_row = QHBoxLayout()
        self.alt_buttons: list[QPushButton] = []
        for i in range(ALT_BUTTONS):
            button = QPushButton()
            button.setObjectName(f"altRoleButton{i}")
            button.setVisible(False)
            button.clicked.connect(lambda _=False, b=button: self._pick_alt(b))
            self.alt_row.addWidget(button)
            self.alt_buttons.append(button)
        role_box = QVBoxLayout()
        role_box.addWidget(self.role_combo)
        role_box.addLayout(self.alt_row)
        form.addRow(self.tr("Role"), role_box)

        self.confidence_bar = QProgressBar()
        self.confidence_bar.setObjectName("confidenceBar")
        self.confidence_bar.setRange(0, 100)
        self.status_badge = QLabel()
        self.status_badge.setObjectName("statusBadge")
        row = QHBoxLayout()
        row.addWidget(self.confidence_bar, 1)
        row.addWidget(self.status_badge)
        form.addRow(self.tr("Confidence"), row)

        self.collision_combo = QComboBox()
        self.collision_combo.setObjectName("collisionCombo")
        self.collision_combo.addItem(self.tr(UNCHANGED), None)
        for name in COLLISION_PROFILES:
            self.collision_combo.addItem(name, name)
        self.collision_label = QLabel(self.tr("Collision"))
        form.addRow(self.collision_label, self.collision_combo)
        self.tileset_combo = QComboBox()
        self.tileset_combo.setObjectName("tilesetCombo")
        self.tileset_label = QLabel(self.tr("Tileset"))
        form.addRow(self.tileset_label, self.tileset_combo)
        self.tags_edit = QLineEdit()
        self.tags_edit.setObjectName("tagsEdit")
        form.addRow(self.tr("Tags"), self.tags_edit)

        buttons = QHBoxLayout()
        self.confirm_button = QPushButton(self.tr("Confirm"))
        self.confirm_button.setObjectName("confirmButton")
        self.exclude_button = QPushButton(self.tr("Exclude"))
        self.exclude_button.setObjectName("excludeButton")
        self.grid_button = QPushButton(self.tr("Edit grid…"))
        self.grid_button.setObjectName("editGridButton")
        self.anim_button = QPushButton(self.tr("Animations…"))
        self.anim_button.setObjectName("animationsButton")
        self.cut_button = QPushButton(self.tr("Cut objects…"))
        self.cut_button.setObjectName("cutObjectsButton")
        for b in (
            self.confirm_button,
            self.exclude_button,
            self.grid_button,
            self.anim_button,
            self.cut_button,
        ):
            buttons.addWidget(b)
        layout.addLayout(buttons)

        self.usage_combo.activated.connect(self._on_usage)
        self.role_combo.activated.connect(self._on_role)
        self.collision_combo.activated.connect(self._on_collision)
        self.tileset_combo.activated.connect(self._on_tileset)
        self.tags_edit.editingFinished.connect(self._on_tags)
        self.confirm_button.clicked.connect(self._on_confirm)
        self.exclude_button.clicked.connect(self._on_exclude)
        self.show_folder_button.clicked.connect(self._show_folder)
        self.grid_button.clicked.connect(lambda: self._emit(self.gridEditRequested))
        self.anim_button.clicked.connect(lambda: self._emit(self.animationsRequested))
        self.cut_button.clicked.connect(lambda: self._emit(self.cutObjectsRequested))
        self.session.changed.connect(self._on_session_changed)
        self.setEnabled(False)

    @staticmethod
    def _combo(name: str, items: list[str]) -> QComboBox:
        combo = QComboBox()
        combo.setObjectName(name)
        for item in items:
            combo.addItem(item, item)
        return combo

    # ------------------------------------------------------------------ showing an asset

    def asset(self) -> catalog_mod.Asset | None:
        return self.session.catalog.asset(self.asset_id) if self.asset_id else None

    def set_asset(self, asset_id: str | None) -> None:
        previous = self.asset_id
        self.asset_id = asset_id
        self.setEnabled(asset_id is not None)
        self.reload(reload_image=previous != asset_id)

    def _on_session_changed(self, ids: list[str]) -> None:
        if self.asset_id and (not ids or self.asset_id in ids):
            self.reload(reload_image=True)

    def reload(self, reload_image: bool = True) -> None:
        asset = self.asset()
        self._loading = True
        try:
            if asset is None:
                self.path_label.setText("")
                self.pack_label.setText("")
                self.status_badge.setText("")
                self.confidence_bar.setValue(0)
                self.preview.set_image(None)
                return
            eff = catalog_mod.effective(asset)
            self.path_label.setText(asset.path)
            self.pack_label.setText(asset.pack_id)
            self._select(self.usage_combo, eff.get("usage"))
            self._select(self.role_combo, eff.get("role"))
            self._fill_alternatives(eff)
            self.confidence_bar.setValue(round(asset.confidence * 100))
            self.status_badge.setText(asset.status)
            color = STATUS_COLORS.get(asset.status, STATUS_COLORS["UNUSED"])
            self.status_badge.setStyleSheet(f"color: {color}; font-weight: bold;")
            usage = eff.get("usage")
            show_collision = usage in COLLISION_USAGES
            self.collision_combo.setVisible(show_collision)
            self.collision_label.setVisible(show_collision)
            profile = (asset.overrides.get("collision") or {}).get("profile")
            self.collision_combo.setCurrentIndex(max(0, self.collision_combo.findData(profile)))
            self._fill_tilesets(eff.get("tileset"), usage == "tiles")
            self.tags_edit.setText(", ".join(eff.get("tags") or []))
            self.grid_button.setEnabled(usage in GRID_USAGES)
            self.anim_button.setEnabled(usage == "sprite")
            self.cut_button.setEnabled(usage in ("tiles", "object", "sprite", "ui"))
            if reload_image:
                grid = eff.get("grid") if usage in GRID_USAGES else None
                self.preview.set_image(self.resolver(asset), grid)
        finally:
            self._loading = False

    @staticmethod
    def _select(combo: QComboBox, value: object) -> None:
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else -1)

    def _fill_alternatives(self, eff: dict) -> None:
        current = eff.get("role")
        alts = [(r, c) for r, c in (eff.get("roles_alt") or []) if r != current][:ALT_BUTTONS]
        for i, button in enumerate(self.alt_buttons):
            if i < len(alts):
                role, conf = alts[i]
                button.setText(f"{role} {round(conf * 100)}%")
                button.setProperty("role_value", role)
                button.setVisible(True)
            else:
                button.setVisible(False)

    def _fill_tilesets(self, current: str | None, visible: bool) -> None:
        self.tileset_combo.clear()
        names = [t.name for t in self.session.catalog.tilesets]
        if current and current not in names:
            names.append(current)
        for name in names:
            self.tileset_combo.addItem(name, name)
        self.tileset_combo.addItem(self.tr(NEW_TILESET), None)
        self._select(self.tileset_combo, current)
        self.tileset_combo.setVisible(visible)
        self.tileset_label.setVisible(visible)

    # ------------------------------------------------------------------ edits

    def _edit(self, key: str, value: object) -> None:
        if self._loading or self.asset_id is None:
            return
        self.session.set_override(self.asset_id, key, value)

    def _on_usage(self) -> None:
        self._edit("usage", self.usage_combo.currentData())

    def _on_role(self) -> None:
        self._edit("role", self.role_combo.currentData())

    def _pick_alt(self, button: QPushButton) -> None:
        self._edit("role", button.property("role_value"))

    def _on_collision(self) -> None:
        if self._loading or self.asset_id is None:
            return
        profile = self.collision_combo.currentData()
        if profile is None:
            self.session.clear_override(self.asset_id, "collision")
        else:
            self._edit("collision", {"profile": profile})

    def _on_tileset(self) -> None:
        if self._loading or self.asset_id is None:
            return
        name = self.tileset_combo.currentData()
        if name is None:  # "New…"
            text, ok = QInputDialog.getText(self, self.tr("New tileset"), self.tr("Tileset name"))
            if not ok or not text.strip():
                self.reload(reload_image=False)
                return
            name = text.strip()
        self._edit("tileset", name)

    def _on_tags(self) -> None:
        if self._loading or self.asset_id is None:
            return
        tags = [t.strip() for t in self.tags_edit.text().split(",") if t.strip()]
        asset = self.asset()
        if asset is not None and tags != (catalog_mod.effective(asset).get("tags") or []):
            self._edit("tags", tags)

    def _on_confirm(self) -> None:
        if self.asset_id:
            self.session.confirm([self.asset_id])

    def _on_exclude(self) -> None:
        self._edit("role", "NONE")

    def _show_folder(self) -> None:
        asset = self.asset()
        path = self.resolver(asset) if asset else None
        if path is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).parent)))

    def _emit(self, signal) -> None:  # noqa: ANN001
        if self.asset_id:
            signal.emit(self.asset_id)
