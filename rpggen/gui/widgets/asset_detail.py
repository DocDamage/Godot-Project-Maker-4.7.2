"""The audit page's detail panel: a zoomable preview and the editable facets of one asset."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from rpggen.core import audio_info, explain, labels
from rpggen.core import catalog as catalog_mod
from rpggen.gui.edits import EditSession
from rpggen.gui.widgets import audio_preview
from rpggen.gui.widgets.asset_grid import STATUS_COLORS, PathResolver
from rpggen.gui.widgets.flow_layout import FlowLayout
from rpggen.gui.widgets.image_view import ImageView

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


def add_labeled(combo: QComboBox, value: str | None, kind: str, text: str | None = None) -> None:
    """Adds an item that shows the friendly name of a role or usage (``kind``) and keeps the raw
    value as its data; the description is the item's tooltip."""
    if text is None:
        text = labels.role_label(value or "") if kind == "role" else labels.usage_label(value or "")
    help_text = labels.role_help(value or "") if kind == "role" else labels.usage_help(value or "")
    combo.addItem(text, value)
    if help_text:
        combo.setItemData(combo.count() - 1, help_text, Qt.ItemDataRole.ToolTipRole)


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
        self.preview = ImageView("assetPreview")
        self.preview.setMinimumHeight(180)
        layout.addWidget(self.preview, 2)
        # audio files have no picture: a Play button and what is known about the file instead
        self.audio_box = QWidget()
        self.audio_box.setObjectName("audioBox")
        audio_row = QHBoxLayout(self.audio_box)
        audio_row.setContentsMargins(0, 0, 0, 0)
        self.play_button = QPushButton(self.tr("Play"))
        self.play_button.setObjectName("playButton")
        self.play_button.setToolTip(self.tr("Play or stop the sound (Space)"))
        self.audio_info_label = QLabel()
        self.audio_info_label.setObjectName("audioInfoLabel")
        audio_row.addWidget(self.play_button)
        audio_row.addWidget(self.audio_info_label, 1)
        layout.addWidget(self.audio_box)
        self.audio_box.setVisible(False)
        self.play_button.clicked.connect(self.toggle_playback)
        self._space = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        self._space.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._space.activated.connect(self.toggle_playback)

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

        self.usage_combo = self._combo("usageCombo", USAGES, "usage")
        self.usage_combo.setToolTip(
            self.tr("How the file is used: as tiles, a character, an object...")
        )
        form.addRow(self.tr("Usage"), self.usage_combo)
        self.role_combo = self._combo("roleCombo", ROLES, "role")
        self.role_combo.setToolTip(
            self.tr("What the file is in the game. Changing it confirms the asset.")
        )
        self.alt_row = FlowLayout()
        self.alt_buttons: list[QPushButton] = []
        for i in range(ALT_BUTTONS):
            button = QPushButton()
            button.setObjectName(f"altRoleButton{i}")
            button.setToolTip(self.tr("Another role the detection considered: click to use it"))
            button.setVisible(False)
            button.clicked.connect(lambda _=False, b=button: self._pick_alt(b))
            self.alt_row.addWidget(button)
            self.alt_buttons.append(button)
        self.role_help = QLabel()
        self.role_help.setObjectName("roleHelp")
        self.role_help.setWordWrap(True)
        self.role_help.setProperty("muted", True)
        self.why_label = QLabel()
        self.why_label.setObjectName("whyLabel")
        self.why_label.setWordWrap(True)
        self.why_label.setProperty("muted", True)
        role_box = QVBoxLayout()
        role_box.addWidget(self.role_combo)
        role_box.addWidget(self.role_help)
        role_box.addLayout(self.alt_row)
        role_box.addWidget(self.why_label)
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
        self.collision_combo.setToolTip(self.tr("The shape that blocks movement"))
        self.collision_combo.addItem(self.tr(UNCHANGED), None)
        for name in COLLISION_PROFILES:
            self.collision_combo.addItem(name, name)
        self.collision_label = QLabel(self.tr("Collision"))
        form.addRow(self.collision_label, self.collision_combo)
        self.tileset_combo = QComboBox()
        self.tileset_combo.setObjectName("tilesetCombo")
        self.tileset_combo.setToolTip(self.tr("The TileSet this sheet is added to"))
        self.tileset_label = QLabel(self.tr("Tileset"))
        form.addRow(self.tileset_label, self.tileset_combo)
        self.tags_edit = QLineEdit()
        self.tags_edit.setObjectName("tagsEdit")
        form.addRow(self.tr("Tags"), self.tags_edit)

        buttons = FlowLayout()  # wraps when the panel is narrow
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
    def _combo(name: str, items: list[str], kind: str) -> QComboBox:
        combo = QComboBox()
        combo.setObjectName(name)
        for item in items:
            add_labeled(combo, item, kind)
        return combo

    # ------------------------------------------------------------------ showing an asset

    def asset(self) -> catalog_mod.Asset | None:
        return self.session.catalog.asset(self.asset_id) if self.asset_id else None

    def set_asset(self, asset_id: str | None) -> None:
        previous = self.asset_id
        self.asset_id = asset_id
        if previous != asset_id:
            audio_preview.stop()
            self.play_button.setText(self.tr("Play"))
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
                self.role_help.setText("")
                self.why_label.setText("")
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
            self.role_help.setText(labels.role_help(str(eff.get("role", ""))))
            self.why_label.setText(self.tr("Why: ") + explain.why(asset))
            self._fill_alternatives(eff)
            self.confidence_bar.setValue(round(asset.confidence * 100))
            self.status_badge.setText(asset.status)
            color = STATUS_COLORS.get(asset.status, STATUS_COLORS["UNUSED"])
            self.status_badge.setStyleSheet(f"color: {color}; font-weight: bold;")
            usage = eff.get("usage")
            self._show_media_kind(asset, eff)
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
                if asset.kind == "image":
                    grid = eff.get("grid") if usage in GRID_USAGES else None
                    self.preview.set_image(self.resolver(asset), grid)
                else:
                    self.preview.set_image(None)
        finally:
            self._loading = False

    def _show_media_kind(self, asset: catalog_mod.Asset, eff: dict) -> None:
        """Audio and fonts hide the (empty) picture; audio gets Play, its length and its type."""
        is_image = asset.kind == "image"
        self.preview.setVisible(is_image)
        is_audio = asset.kind == "audio"
        self.audio_box.setVisible(is_audio)
        if not is_audio:
            return
        audio = eff.get("audio") or {}
        seconds = audio.get("duration_s")
        kind = {"music": self.tr("music"), "sfx": self.tr("sound effect")}.get(
            str(audio.get("type")), self.tr("audio")
        )
        suffix = asset.path.rsplit(".", 1)[-1].upper() if "." in asset.path else ""
        parts = [audio_info.format_duration(seconds), kind] + ([suffix] if suffix else [])
        self.audio_info_label.setText(" · ".join(parts))
        self.play_button.setVisible(audio_preview.available())

    def toggle_playback(self) -> None:
        """Play the selected sound, or stop it when it is already playing."""
        asset = self.asset()
        if asset is None or asset.kind != "audio" or not audio_preview.available():
            return
        if audio_preview.is_playing():
            audio_preview.stop()
            self.play_button.setText(self.tr("Play"))
            return
        path = self.resolver(asset)
        if path is not None and audio_preview.play(Path(path)):
            self.play_button.setText(self.tr("Stop"))

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
                button.setText(f"{labels.role_label(role)} {round(conf * 100)}%")
                button.setToolTip(labels.role_help(role))
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
