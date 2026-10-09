"""The audit page's detail panel: a zoomable preview and the editable facets of one asset."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QKeySequence, QPixmap, QShortcut, QTransform
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from rpggen.core import anim_edit, audio_info, explain, labels
from rpggen.core import catalog as catalog_mod
from rpggen.gui import workers
from rpggen.gui.edits import EditSession
from rpggen.gui.widgets import audio_preview, image_view
from rpggen.gui.widgets.anim_preview import AnimPlayer
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
    # side view (T14.02): a platform to jump through from below, and a tile to climb. Only a
    # metroidvania reads them; a top-down map has no gravity and treats both as NONE.
    "ONE_WAY",
    "LADDER",
]
COLLISION_USAGES = {"tiles", "object"}
GRID_USAGES = {"tiles", "sprite"}
ALT_BUTTONS = 3
NEW_TILESET = "New…"
UNCHANGED = "— detected —"


def _peaks_job(path: Path, columns: int, *, callbacks: object) -> object:
    """Worker function: the peaks of a long track (``callbacks`` is not used)."""
    return audio_info.peaks(path, columns)


def frame_size_of(eff: dict[str, Any]) -> tuple[int, int] | None:
    """The size of one animation frame: the ``frame`` facet, else the grid's cell."""
    frame = eff.get("frame") or (eff.get("grid") or {}).get("cell")
    return (int(frame[0]), int(frame[1])) if frame else None


def overlay_marks(
    eff: dict[str, Any], size: tuple[int, int], anim_name: str | None = None, frame: int = -1
) -> list[image_view.Mark]:
    """What is drawn over an asset's picture besides its grid, by usage (T13.03): the footprint
    and origin of an object; for a sprite, the frames of the chosen animation in which the
    attack hits (``active_frames``) and the frame the transport is on."""
    usage = eff.get("usage")
    width, height = size
    marks: list[image_view.Mark] = []
    if usage == "object" and width and height:
        footprint = eff.get("footprint")
        if not footprint:  # the default: the bottom 30% at full width (02_SCHEMAS)
            top = round(height * 0.7)
            footprint = [0, top, width, height - top]
        x, y, w, h = footprint
        marks.append((image_view.MARK_FOOTPRINT, x, y, w, h))
        origin = eff.get("origin")
        if origin:
            marks.append((image_view.MARK_ORIGIN, origin[0], origin[1], 0, 0))
    elif usage == "sprite" and anim_name:
        anim = (eff.get("animations") or {}).get(anim_name)
        frame_size = frame_size_of(eff)
        if anim and anim.get("frames") and frame_size:
            count = len(anim["frames"])
            for index in anim.get("active_frames") or []:
                if 0 <= index < count:
                    rect = anim_edit.frame_rect(anim, index, frame_size, eff.get("grid"))
                    marks.append((image_view.MARK_ACTIVE, *rect))
            if 0 <= frame < count and not anim.get("source"):
                rect = anim_edit.frame_rect(anim, frame, frame_size, eff.get("grid"))
                marks.append((image_view.MARK_CURRENT, *rect))
    return marks


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
        # review mode (T13.01) shows the picture large beside the panel and turns this one off
        self.show_preview = True
        # ... and lends its own view, which then gets the picture, the marks and the playback
        self.extra_view: ImageView | None = None
        self._sheets: dict[Path, QPixmap] = {}
        self.player = AnimPlayer(self.current_animation, self)
        self.player.frameChanged.connect(lambda _index: self._on_frame())
        self.player.finished.connect(self.stop_animation)

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
        # ... and its waveform with the play head; music also gets the loop row (T13.17)
        self.waveform = audio_preview.WaveformView()
        self.waveform.setVisible(False)
        layout.addWidget(self.waveform)
        self.loop_box = QWidget()
        self.loop_box.setObjectName("loopBox")
        loop_row = QHBoxLayout(self.loop_box)
        loop_row.setContentsMargins(0, 0, 0, 0)
        loop_label = QLabel(self.tr("Loop"))
        loop_label.setToolTip(
            self.tr(
                "Where the track jumps back to and from when it repeats, in milliseconds. "
                "Drag the markers on the waveform or type the numbers. "
                "Only WAV files use the end point: OGG and MP3 play to their end."
            )
        )
        self.loop_start_spin = QSpinBox()
        self.loop_start_spin.setObjectName("loopStart")
        self.loop_start_spin.setAccessibleName(self.tr("Loop start in milliseconds"))
        self.loop_end_spin = QSpinBox()
        self.loop_end_spin.setObjectName("loopEnd")
        self.loop_end_spin.setAccessibleName(self.tr("Loop end in milliseconds"))
        for spin in (self.loop_start_spin, self.loop_end_spin):
            spin.setSuffix(" ms")
            spin.setSingleStep(50)
            spin.setKeyboardTracking(False)
            spin.setToolTip(loop_label.toolTip())
        self.loop_guess_button = QPushButton(self.tr("Guess"))
        self.loop_guess_button.setObjectName("loopGuess")
        self.loop_guess_button.setToolTip(
            self.tr("Look for the longest stretch after which the track goes on as before")
        )
        self.loop_clear_button = QPushButton(self.tr("Whole track"))
        self.loop_clear_button.setObjectName("loopClear")
        self.loop_clear_button.setToolTip(self.tr("Loop the whole track again"))
        self.loop_note = QLabel()
        self.loop_note.setObjectName("loopNote")
        for widget in (
            loop_label,
            self.loop_start_spin,
            self.loop_end_spin,
            self.loop_guess_button,
            self.loop_clear_button,
        ):
            loop_row.addWidget(widget)
        loop_row.addWidget(self.loop_note, 1)
        layout.addWidget(self.loop_box)
        self.loop_box.setVisible(False)
        self.loop_start_spin.valueChanged.connect(lambda _v: self._on_loop_spins())
        self.loop_end_spin.valueChanged.connect(lambda _v: self._on_loop_spins())
        self.loop_guess_button.clicked.connect(self.guess_loop)
        self.loop_clear_button.clicked.connect(self.clear_loop)
        self.waveform.loopChanged.connect(self.set_loop)
        self._peaks: dict[str, list[tuple[float, float]] | None] = {}
        self._peak_worker: workers.Worker | None = None
        self._head_timer = QTimer(self)
        self._head_timer.setInterval(40)
        self._head_timer.timeout.connect(self._move_head)
        # a sprite with animations: which one, play / pause and the frame (T13.03)
        self.anim_box = QWidget()
        self.anim_box.setObjectName("animBox")
        anim_row = QHBoxLayout(self.anim_box)
        anim_row.setContentsMargins(0, 0, 0, 0)
        self.anim_combo = QComboBox()
        self.anim_combo.setObjectName("animCombo")
        self.anim_combo.setToolTip(self.tr("The animation shown over the sheet and played"))
        self.anim_combo.setAccessibleName(self.tr("Animation"))
        self.anim_play_button = QPushButton(self.tr("Play"))
        self.anim_play_button.setObjectName("animPlayButton")
        self.anim_play_button.setCheckable(True)
        self.anim_play_button.setToolTip(self.tr("Play the animation in the preview"))
        self.anim_frame_label = QLabel()
        self.anim_frame_label.setObjectName("animFrameLabel")
        anim_row.addWidget(self.anim_combo, 1)
        anim_row.addWidget(self.anim_play_button)
        anim_row.addWidget(self.anim_frame_label)
        layout.addWidget(self.anim_box)
        self.anim_box.setVisible(False)
        self.anim_combo.activated.connect(self._on_anim_chosen)
        self.anim_play_button.toggled.connect(self._on_anim_play)
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
            self.stop_animation()
            self.player.index = 0
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
                self.anim_box.setVisible(False)
                for view in self.views():
                    view.set_image(None)
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
            self._fill_animations(eff)
            if reload_image and not self.player.playing:
                self.render_picture()
        finally:
            self._loading = False

    # ------------------------------------------------------------------ the picture (T13.03)

    def views(self) -> list[ImageView]:
        """Where the picture goes: the panel's own view, and the large one in review mode."""
        own = [self.preview] if self.show_preview else []
        return own + ([self.extra_view] if self.extra_view is not None else [])

    def render_picture(self) -> None:
        """The whole picture with what its usage draws over it: the tile grid, the frame boxes,
        the footprint and origin, the frames where the attack hits. Read from the effective
        facets, so it follows every edit."""
        asset = self.asset()
        if asset is None or asset.kind != "image":
            for view in self.views():
                view.set_image(None)
            return
        eff = catalog_mod.effective(asset)
        grid = eff.get("grid") if eff.get("usage") in GRID_USAGES else None
        path = self.resolver(asset)
        for view in self.views():
            view.set_image(path, grid)
            marks = overlay_marks(eff, view.image_size, self.animation_name(), self.player.index)
            view.draw_marks(marks)

    def animation_name(self) -> str | None:
        name = self.anim_combo.currentData() if self.anim_box.isVisibleTo(self) else None
        return str(name) if name else None

    def current_animation(self) -> dict[str, Any] | None:
        asset = self.asset()
        name = self.anim_combo.currentData()
        if asset is None or not name:
            return None
        animations = catalog_mod.effective(asset).get("animations") or {}
        found = animations.get(name)
        return found if isinstance(found, dict) else None

    def _fill_animations(self, eff: dict[str, Any]) -> None:
        """The transport shows for a sprite that has animations; the combo lists them grouped
        by action with the directions in order, as the dialog's tree does."""
        animations = eff.get("animations") or {}
        names = [n for n in animations if (animations[n] or {}).get("frames")]
        show = eff.get("usage") == "sprite" and bool(names)
        self.anim_box.setVisible(show)
        if not show:
            self.stop_animation()
            self.anim_combo.clear()
            return
        ordered = [name for _action, group in anim_edit.groups(names) for name in group]
        current = [self.anim_combo.itemData(i) for i in range(self.anim_combo.count())]
        if current != ordered:
            keep = self.anim_combo.currentData()
            self.anim_combo.blockSignals(True)
            self.anim_combo.clear()
            for name in ordered:
                self.anim_combo.addItem(name, name)
            self.anim_combo.setCurrentIndex(max(0, self.anim_combo.findData(keep)))
            self.anim_combo.blockSignals(False)
        self._show_frame_number()

    def _show_frame_number(self) -> None:
        count = self.player.count()
        self.player.index = self.player.index % count if count else 0
        self.anim_frame_label.setText(
            self.tr("Frame {0} of {1}").format(self.player.index + 1, count) if count else ""
        )

    def _on_anim_chosen(self) -> None:
        self.player.restart()
        self._on_frame()

    def _on_anim_play(self, checked: bool) -> None:
        self.anim_play_button.setText(self.tr("Pause") if checked else self.tr("Play"))
        self.player.set_playing(checked)
        self._on_frame()

    def stop_animation(self) -> None:
        """Playback ends when the asset changes, the panel is hidden or the page is left."""
        if self.player.playing or self.anim_play_button.isChecked():
            self.anim_play_button.setChecked(False)
        self.player.set_playing(False)

    def hideEvent(self, event) -> None:  # noqa: ANN001, N802
        self.stop_animation()
        super().hideEvent(event)

    def frame_pixmap(self, index: int) -> QPixmap | None:
        """Frame ``index`` of the chosen animation, cut from its sheet (mirrored if it says so)."""
        asset = self.asset()
        anim = self.current_animation()
        if asset is None or not anim or not anim.get("frames"):
            return None
        eff = catalog_mod.effective(asset)
        frame_size = frame_size_of(eff)
        source = anim.get("source")
        path = self.resolver(dataclasses.replace(asset, path=source) if source else asset)
        if frame_size is None or path is None:
            return None
        path = Path(path)
        if path not in self._sheets:
            self._sheets = {path: QPixmap(str(path))}  # one sheet at a time is enough
        sheet = self._sheets[path]
        if sheet.isNull():
            return None
        x, y, w, h = anim_edit.frame_rect(anim, index, frame_size, eff.get("grid"))
        cut = sheet.copy(x, y, w, h)
        return cut.transformed(QTransform().scale(-1, 1)) if anim.get("flip_h") else cut

    def _on_frame(self) -> None:
        """While playing the views show the frame alone; paused, the sheet with the frame
        marked on it."""
        self._show_frame_number()
        if not self.player.playing:
            self.render_picture()
            return
        pixmap = self.frame_pixmap(self.player.index)
        for view in self.views():
            view.set_pixmap(pixmap)

    def _show_media_kind(self, asset: catalog_mod.Asset, eff: dict) -> None:
        """Audio and fonts hide the (empty) picture; audio gets Play, its length and its type."""
        is_image = asset.kind == "image"
        self.preview.setVisible(is_image and self.show_preview)
        if not is_image:
            self.anim_box.setVisible(False)
        is_audio = asset.kind == "audio"
        self.audio_box.setVisible(is_audio)
        self.waveform.setVisible(is_audio)
        if not is_audio:
            self.loop_box.setVisible(False)
            return
        self._show_waveform(asset, eff)
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
            self._head_timer.stop()
            self.waveform.set_head(None)
            return
        path = self.resolver(asset)
        if path is not None and audio_preview.play(Path(path)):
            self.play_button.setText(self.tr("Stop"))
            self._head_timer.start()

    def _move_head(self) -> None:
        if not audio_preview.is_playing():
            self._head_timer.stop()
            self.waveform.set_head(None)
            self.play_button.setText(self.tr("Play"))
            return
        self.waveform.set_head(audio_preview.position_ms())

    # ------------------------------------------------------------------ waveform and loop (T13.17)

    SYNC_PEAK_BYTES = 4 * 1024 * 1024  # larger files are decoded off the UI thread
    PEAK_COLUMNS = 480

    def _show_waveform(self, asset: catalog_mod.Asset, eff: dict) -> None:
        audio = eff.get("audio") or {}
        seconds = audio.get("duration_s")
        duration_ms = round(float(seconds) * 1000) if isinstance(seconds, (int, float)) else 0
        path = self.resolver(asset)
        key = str(path) if path is not None else ""
        if key and key not in self._peaks:
            self._load_peaks(Path(key), asset.id)
        self.waveform.set_sound(self._peaks.get(key), duration_ms)
        is_music = audio.get("type") == "music"
        self.loop_box.setVisible(is_music)
        start, end = audio.get("loop_start_ms"), audio.get("loop_end_ms")
        self.waveform.set_loop(
            start if isinstance(start, int) else None,
            end if isinstance(end, int) else None,
            markers=is_music and duration_ms > 0,
        )
        shown_start, shown_end = self.waveform.loop()
        was_loading, self._loading = self._loading, True
        for spin, value in ((self.loop_start_spin, shown_start), (self.loop_end_spin, shown_end)):
            spin.setRange(0, max(0, duration_ms))
            spin.setValue(value)
            spin.setEnabled(duration_ms > 0)
        self._loading = was_loading
        self.loop_guess_button.setEnabled(duration_ms > 0)
        self.loop_clear_button.setEnabled(isinstance(start, int) or isinstance(end, int))
        self.loop_note.setText("")

    def _load_peaks(self, path: Path, asset_id: str) -> None:
        key = str(path)
        try:
            small = path.stat().st_size <= self.SYNC_PEAK_BYTES
        except OSError:
            self._peaks[key] = None
            return
        if small:
            self._peaks[key] = audio_info.peaks(path, self.PEAK_COLUMNS)
            return
        self._peaks[key] = None  # a flat bar until the worker is back
        worker = workers.Worker(_peaks_job, path, self.PEAK_COLUMNS)

        def done(found: object) -> None:
            self._peaks[key] = found if isinstance(found, list) else None
            try:
                if self.asset_id == asset_id:
                    self.waveform.set_sound(self._peaks[key], self.waveform.duration_ms)
            except RuntimeError:  # the panel is gone
                pass

        worker.signals.finished.connect(done)
        self._peak_worker = worker
        worker.start()

    def loop_points(self) -> tuple[int | None, int | None]:
        """The asset's loop points as the catalog has them (None: not set)."""
        asset = self.asset()
        audio = (catalog_mod.effective(asset).get("audio") or {}) if asset is not None else {}
        start, end = audio.get("loop_start_ms"), audio.get("loop_end_ms")
        return (start if isinstance(start, int) else None, end if isinstance(end, int) else None)

    def set_loop(self, start_ms: int, end_ms: int) -> bool:
        """Store both loop points (one undo step). False when they are no loop."""
        asset = self.asset()
        if asset is None or asset.kind != "audio" or end_ms <= start_ms or start_ms < 0:
            self.reload(reload_image=False)
            return False
        if (start_ms, end_ms) == self.loop_points():
            return True
        audio = dict(asset.overrides.get("audio") or {})
        audio.update({"loop_start_ms": int(start_ms), "loop_end_ms": int(end_ms)})
        return self.session.set_overrides([asset.id], {"audio": audio}, "Set the loop points")

    def clear_loop(self) -> bool:
        """Back to looping the whole track (one undo step)."""
        asset = self.asset()
        if asset is None or self.loop_points() == (None, None):
            return False
        audio = dict(asset.overrides.get("audio") or {})
        audio.pop("loop_start_ms", None)
        audio.pop("loop_end_ms", None)
        detected = asset.detected.get("audio") or {}
        for point in ("loop_start_ms", "loop_end_ms"):  # a profile may have set one
            if point in detected:
                audio[point] = None
        if not audio:  # nothing else was overridden: the detected facts apply again
            return self.session.clear_override(asset.id, "audio")
        return self.session.set_overrides([asset.id], {"audio": audio}, "Loop the whole track")

    def guess_loop(self) -> bool:
        asset = self.asset()
        path = self.resolver(asset) if asset is not None else None
        found = audio_info.guess_loop(Path(path)) if path is not None else None
        if found is None:
            self.loop_note.setText(self.tr("No loop found"))
            return False
        return self.set_loop(*found)

    def _on_loop_spins(self) -> None:
        if self._loading:
            return
        start, end = self.loop_start_spin.value(), self.loop_end_spin.value()
        if end <= start:
            self.loop_note.setText(self.tr("The end must be after the start"))
            return
        self.set_loop(start, end)

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
