"""Page 5: features, presets, starter map, resolution, window size, map layers and advanced
settings."""

from __future__ import annotations

import copy
import dataclasses
import random
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QBoxLayout,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rpggen.core import app_settings, options, preflight, vcs
from rpggen.core import config as config_mod
from rpggen.errors import Issue
from rpggen.gui.pages.base import WizardPage, form_error
from rpggen.gui.state import WizardState
from rpggen.gui.widgets.binding_table import BindingTable
from rpggen.gui.widgets.collapsible import CollapsibleSection
from rpggen.gui.widgets.map_preview import MapPreviewWidget
from rpggen.gui.widgets.options_summary import OptionsSummary

INPUT_COLUMNS = ("Action", "Keys", "Mouse buttons", "Joy buttons")
SEED_MAX = 2**31 - 1
WIDE_WIDTH = 1100  # at this width and more the options use two columns
SUMMARY_SIDE_WIDTH = 1200  # at this width and more the summary has a column of its own
LAYER_MESSAGES = {
    options.LAYER_GROUND_REQUIRED: "The Ground layer is required.",
    options.LAYER_EMPTY: "Layer names cannot be empty.",
    options.LAYER_DUPLICATE: "Layer names must be unique.",
}
DEFAULTS_ITEM = "__defaults__"
STARTER_COUNTS = (
    ("buildings", "Buildings"),
    ("npcs", "Villagers"),
    ("enemies", "Enemies"),
    ("chests", "Chests"),
    ("decorations", "Decorations"),
    ("ground_patches", "Ground patches"),
)
STARTER_SIZE_NAMES = {(32, 20): "Small", (40, 24): "Medium", (64, 40): "Large"}
EXISTING_MAP_TEXT = (
    "The starter map already exists and is yours; these options apply to new projects."
)

# kept for tests and callers that name the labels
FEATURE_LABELS = {key: info[1] for key, info in options.FEATURE_INFO.items()}


def _spin(low: int, high: int) -> QSpinBox:
    box = QSpinBox()
    box.setRange(low, high)
    return box


PACK_ART_LABELS = {
    "commit": "Commit the pack art with the project",
    "lfs": "Use Git LFS for the pack art",
    "ignore": "Leave the pack art out of git",
}


class SizeEditor(QWidget):
    """A preset combo plus width / height spin boxes that are enabled for Custom."""

    def __init__(
        self,
        name: str,
        presets: list[tuple[int, int]],
        low: int,
        high: int,
        names: dict[tuple[int, int], str] | None = None,
    ) -> None:
        super().__init__()
        self.presets = presets
        self._labels: list[str] = []
        self.combo = QComboBox()
        self.combo.setObjectName(f"{name}Combo")
        for w, h in presets:
            label = f"{w} × {h}"
            if names and (w, h) in names:
                label = f"{self.tr(names[(w, h)])} {label}"
            self._labels.append(label)
            self.combo.addItem(label, (w, h))
        self.combo.addItem(self.tr("Custom"), None)
        self.width_box = _spin(low, high)
        self.width_box.setObjectName(f"{name}Width")
        self.height_box = _spin(low, high)
        self.height_box.setObjectName(f"{name}Height")
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.combo)
        row.addWidget(self.width_box)
        row.addWidget(QLabel("×"))
        row.addWidget(self.height_box)
        row.addStretch(1)
        self.combo.currentIndexChanged.connect(self._on_combo)

    def _on_combo(self, _index: int) -> None:
        value = self.combo.currentData()
        custom = value is None
        self.width_box.setEnabled(custom)
        self.height_box.setEnabled(custom)
        if value is not None:
            self.width_box.setValue(value[0])
            self.height_box.setValue(value[1])

    def mark_suggested(self, preset: tuple[int, int] | None) -> None:
        """Adds "(suggested)" to the label of ``preset`` (and takes it off the others)."""
        for index, (label, item) in enumerate(zip(self._labels, self.presets, strict=True)):
            suffix = " " + self.tr("(suggested)") if item == preset else ""
            self.combo.setItemText(index, label + suffix)

    def value(self) -> tuple[int, int]:
        return (self.width_box.value(), self.height_box.value())

    def set_value(self, value: tuple[int, int]) -> None:
        self.width_box.setValue(value[0])
        self.height_box.setValue(value[1])
        index = options.preset_index(self.presets, value)
        self.combo.setCurrentIndex(index)
        self._on_combo(index)


class ManagePresetsDialog(QDialog):
    """Rename and delete the saved presets."""

    def __init__(self, names: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("managePresets")
        self.setWindowTitle(self.tr("Manage presets"))
        self.resize(360, 300)
        self.renames: dict[str, str] = {}  # old name -> new name
        self.deleted: list[str] = []
        layout = QVBoxLayout(self)
        self.list = QListWidget()
        self.list.setObjectName("presetList")
        self.list.addItems(names)
        layout.addWidget(self.list)
        row = QHBoxLayout()
        self.rename_button = QPushButton(self.tr("Rename…"))
        self.rename_button.setObjectName("renamePreset")
        self.delete_button = QPushButton(self.tr("Delete"))
        self.delete_button.setObjectName("deletePreset")
        row.addWidget(self.rename_button)
        row.addWidget(self.delete_button)
        row.addStretch(1)
        layout.addLayout(row)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.rename_button.clicked.connect(self.rename_current)
        self.delete_button.clicked.connect(self.delete_current)

    def ask_name(self, current: str) -> str | None:  # overridden by tests
        text, ok = QInputDialog.getText(
            self, self.tr("Rename preset"), self.tr("New name"), text=current
        )
        return text.strip() if ok and text.strip() else None

    def rename_current(self) -> None:
        item = self.list.currentItem()
        if item is None:
            return
        new = self.ask_name(item.text())
        names = [self.list.item(i).text() for i in range(self.list.count())]
        if new is None or new == item.text() or new in names or new == self.tr("Defaults"):
            return
        self.renames[item.text()] = new
        item.setText(new)

    def delete_current(self) -> None:
        row = self.list.currentRow()
        if row < 0:
            return
        self.deleted.append(self.list.takeItem(row).text())


class OptionsPage(WizardPage):
    title = "Options"
    help_anchor = "3. Using a pack you bought"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.state: WizardState | None = None
        self.draft: config_mod.GeneratorConfig | None = None
        self.input_map: dict[str, dict[str, Any]] = {}
        self._collected_input: dict[str, dict[str, Any]] = {}
        self._input_errors: list[str] = []
        self._loading = False
        self._demo_wish = True
        self._starter_locked = False
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # ---------------------------------------------------------------- presets header
        header = QHBoxLayout()
        header.setContentsMargins(6, 4, 6, 0)
        header.addWidget(QLabel(self.tr("Preset")))
        self.preset_combo = QComboBox()
        self.preset_combo.setObjectName("presetCombo")
        self.preset_combo.setToolTip(
            self.tr(
                "Apply the options of a saved preset (packs, name and seed are not part of one)"
            )
        )
        self.preset_combo.setMinimumWidth(180)
        header.addWidget(self.preset_combo)
        self.save_preset_button = QPushButton(self.tr("Save as preset…"))
        self.save_preset_button.setObjectName("savePreset")
        self.save_preset_button.setToolTip(self.tr("Keep the options below for your next project"))
        self.manage_presets_button = QPushButton(self.tr("Manage…"))
        self.manage_presets_button.setObjectName("managePresetsButton")
        self.manage_presets_button.setToolTip(self.tr("Rename or delete saved presets"))
        header.addWidget(self.save_preset_button)
        header.addWidget(self.manage_presets_button)
        header.addStretch(1)
        outer.addLayout(header)

        scroll = QScrollArea()
        scroll.setObjectName("optionsScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        self.columns = QBoxLayout(QBoxLayout.Direction.TopToBottom, content)
        self.left = QWidget()
        self.right = QWidget()
        left = QVBoxLayout(self.left)
        right = QVBoxLayout(self.right)
        left.setContentsMargins(0, 0, 0, 0)
        right.setContentsMargins(0, 0, 0, 0)
        self.columns.addWidget(self.left, 1)
        self.columns.addWidget(self.right, 1)
        scroll.setWidget(content)
        # the summary card: on top, or in a right-hand column at SUMMARY_SIDE_WIDTH and more
        self.summary = OptionsSummary()
        outer.addWidget(self.summary)
        body = QHBoxLayout()
        body.addWidget(scroll, 1)
        self.side = QWidget()
        self.side.setObjectName("summarySide")
        self.side_layout = QVBoxLayout(self.side)
        self.side_layout.setContentsMargins(0, 0, 6, 0)
        self.side_layout.addStretch(1)
        self.side.setFixedWidth(300)
        self.side.setVisible(False)
        body.addWidget(self.side)
        outer.addLayout(body, 1)
        self._summary_outer = outer
        self._summary_on_side = False
        self._pack_bytes_key: tuple | None = None
        self._pack_bytes = 0

        # ---------------------------------------------------------------- features
        self.feature_boxes: dict[str, QCheckBox] = {}
        self.feature_needs: dict[str, QLabel] = {}
        self.features_reset = self._reset_button("resetFeatures", self._reset_features)
        for group in options.FEATURE_GROUPS:
            box = QGroupBox(self.tr(group))
            box.setObjectName(f"group_{group.replace(' ', '_')}")
            vbox = QVBoxLayout(box)
            for key in options.features_in_group(group):
                _g, label, text = options.FEATURE_INFO[key]
                check = QCheckBox(self.tr(label))
                check.setObjectName(f"feature_{key}")
                check.setTristate(False)
                check.setToolTip(self.tr(text))
                description = QLabel(self.tr(text))
                description.setObjectName(f"featureText_{key}")
                description.setWordWrap(True)
                description.setProperty("muted", True)
                description.setContentsMargins(22, 0, 0, 4)
                needs = QLabel()
                needs.setObjectName(f"featureNeeds_{key}")
                needs.setProperty("state", "warning")
                needs.setContentsMargins(22, 0, 0, 2)
                needs.setVisible(False)
                self.feature_boxes[key] = check
                self.feature_needs[key] = needs
                vbox.addWidget(check)
                vbox.addWidget(needs)
                vbox.addWidget(description)
                check.toggled.connect(lambda checked, k=key: self._on_feature(k, checked))
            if group == options.FEATURE_GROUPS[0]:
                vbox.addWidget(self.features_reset, 0, Qt.AlignmentFlag.AlignRight)
            left.addWidget(box)

        # ---------------------------------------------------------------- starter map
        self.starter_box = QGroupBox(self.tr("Starter map"))
        self.starter_box.setObjectName("starterMap")
        starter = QVBoxLayout(self.starter_box)
        self.starter_note = QLabel()
        self.starter_note.setObjectName("starterNote")
        self.starter_note.setWordWrap(True)
        self.starter_note.setProperty("state", "warning")
        self.starter_note.setVisible(False)
        starter.addWidget(self.starter_note)
        self.starter_size = SizeEditor(
            "starterSize", options.STARTER_SIZE_PRESETS, 24, 96, STARTER_SIZE_NAMES
        )
        self.starter_size.setToolTip(
            self.tr("Width and height of the starter map in tiles (24 to 96)")
        )
        starter.addWidget(QLabel(self.tr("Size in tiles")))
        starter.addWidget(self.starter_size)
        counts = QHBoxLayout()
        self.starter_counts: dict[str, QSpinBox] = {}
        for key, label in STARTER_COUNTS:
            low, high = config_mod.STARTER_MAP_COUNTS[key]
            spin = _spin(low, high)
            spin.setObjectName(f"starter_{key}")
            spin.setToolTip(self.tr("{0}: {1} to {2}").format(self.tr(label), low, high))
            self.starter_counts[key] = spin
            column = QVBoxLayout()
            column.addWidget(QLabel(self.tr(label)))
            column.addWidget(spin)
            counts.addLayout(column)
        starter.addLayout(counts)
        ground_row = QHBoxLayout()
        self.ground_label = QLabel(self.tr("Ground set"))
        self.ground_combo = QComboBox()
        self.ground_combo.setObjectName("starterGround")
        self.ground_combo.setToolTip(self.tr("The tile sheet the starter map is painted with"))
        ground_row.addWidget(self.ground_label)
        ground_row.addWidget(self.ground_combo, 1)
        starter.addLayout(ground_row)
        self.starter_reset = self._reset_button("resetStarter", self._reset_starter)
        starter.addWidget(self.starter_reset, 0, Qt.AlignmentFlag.AlignRight)
        self.preview = MapPreviewWidget()
        starter.addWidget(self.preview)
        self.preview.rerollRequested.connect(self.reroll)
        left.addWidget(self.starter_box)
        left.addStretch(1)
        self.starter_size.width_box.valueChanged.connect(self._on_starter_edited)
        self.starter_size.height_box.valueChanged.connect(self._on_starter_edited)
        self.starter_size.combo.currentIndexChanged.connect(self._on_starter_edited)
        for spin in self.starter_counts.values():
            spin.valueChanged.connect(self._on_starter_edited)
        self.ground_combo.currentIndexChanged.connect(self._on_starter_edited)

        # ---------------------------------------------------------------- screen
        screen = QGroupBox(self.tr("Screen"))
        screen_layout = QVBoxLayout(screen)
        screen_layout.addWidget(QLabel(self.tr("Game resolution")))
        self.resolution = SizeEditor("resolution", options.RESOLUTION_PRESETS, 160, 3840)
        self.resolution.setToolTip(
            self.tr("How many pixels the game draws (the picture is scaled to the window)")
        )
        screen_layout.addWidget(self.resolution)
        self.hint_label = QLabel()
        self.hint_label.setObjectName("tilesHint")
        screen_layout.addWidget(self.hint_label)
        screen_layout.addWidget(QLabel(self.tr("Window size")))
        self.window_editor = SizeEditor("window", options.WINDOW_PRESETS, 160, 7680)
        self.window_editor.setToolTip(self.tr("The size of the game window"))
        screen_layout.addWidget(self.window_editor)
        self.screen_reset = self._reset_button("resetScreen", self._reset_screen)
        screen_layout.addWidget(self.screen_reset, 0, Qt.AlignmentFlag.AlignRight)
        right.addWidget(screen)
        for editor in (self.resolution, self.window_editor):
            editor.width_box.valueChanged.connect(self._on_edited)
            editor.height_box.valueChanged.connect(self._on_edited)

        # ---------------------------------------------------------------- layers
        layers_box = QGroupBox(self.tr("Map layers"))
        layers_layout = QHBoxLayout(layers_box)
        self.layer_list = QListWidget()
        self.layer_list.setObjectName("layerList")
        self.layer_list.setToolTip(self.tr("Map layers, back to front. Drag to reorder."))
        self.layer_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.layer_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.layer_list.setMinimumHeight(110)
        self.layer_list.model().rowsMoved.connect(self._on_edited)
        layers_layout.addWidget(self.layer_list, 1)
        side = QVBoxLayout()
        self.layer_name = QLineEdit()
        self.layer_name.setObjectName("layerName")
        self.layer_name.setPlaceholderText(self.tr("New layer name"))
        self.add_layer_button = QPushButton(self.tr("Add"))
        self.add_layer_button.setObjectName("addLayer")
        self.add_layer_button.setToolTip(self.tr("Add a layer with the name above"))
        self.remove_layer_button = QPushButton(self.tr("Remove"))
        self.remove_layer_button.setObjectName("removeLayer")
        self.remove_layer_button.setToolTip(self.tr("Remove the selected layer (not Ground)"))
        self.up_button = QPushButton(self.tr("Move up"))
        self.up_button.setObjectName("layerUp")
        self.up_button.setToolTip(self.tr("Draw the selected layer earlier (further back)"))
        self.down_button = QPushButton(self.tr("Move down"))
        self.down_button.setObjectName("layerDown")
        self.down_button.setToolTip(self.tr("Draw the selected layer later (further forward)"))
        self.layers_reset = self._reset_button("resetLayers", self._reset_layers)
        for w in (
            self.layer_name,
            self.add_layer_button,
            self.remove_layer_button,
            self.up_button,
            self.down_button,
            self.layers_reset,
        ):
            side.addWidget(w)
        side.addStretch(1)
        layers_layout.addLayout(side)
        right.addWidget(layers_box)
        self.add_layer_button.clicked.connect(self.add_layer)
        self.remove_layer_button.clicked.connect(self.remove_layer)
        self.up_button.clicked.connect(lambda: self.move_layer(-1))
        self.down_button.clicked.connect(lambda: self.move_layer(1))
        self.layer_list.currentRowChanged.connect(lambda _r: self._update_layer_buttons())

        git_group = QGroupBox(self.tr("Version control"))
        git_group.setObjectName("versionControl")
        git_layout = QVBoxLayout(git_group)
        self.git_box = QCheckBox()
        self.git_box.setObjectName("gitBox")
        self.git_box.toggled.connect(self._on_git)
        git_layout.addWidget(self.git_box)
        self.pack_art_radios: dict[str, QRadioButton] = {}
        pack_art_group = QButtonGroup(git_group)
        for choice, label in PACK_ART_LABELS.items():
            radio = QRadioButton(self.tr(label))
            radio.setObjectName(f"packArt_{choice}")
            self.pack_art_radios[choice] = radio
            pack_art_group.addButton(radio)
            git_layout.addWidget(radio)
            radio.toggled.connect(lambda on, c=choice: on and self._on_pack_art(c))
        licence_note = QLabel(
            self.tr(
                "Most pack licences do not allow the art to be public: if you will push this "
                "project to a public site, leave the pack art out."
            )
        )
        licence_note.setObjectName("packArtNote")
        licence_note.setWordWrap(True)
        licence_note.setProperty("muted", True)
        git_layout.addWidget(licence_note)
        right.addWidget(git_group)

        # ---------------------------------------------------------------- advanced
        self.advanced = CollapsibleSection(self.tr("Advanced"))
        self.advanced.setObjectName("advanced")
        self.advanced_body = self.advanced.body
        body = QVBoxLayout(self.advanced_body)
        body.setContentsMargins(0, 0, 0, 0)
        seed_row = QHBoxLayout()
        seed_row.addWidget(QLabel(self.tr("Seed")))
        self.seed_box = _spin(0, SEED_MAX)
        self.seed_box.setObjectName("seed")
        self.seed_box.setToolTip(
            self.tr("The number every random choice of the generator starts from")
        )
        seed_row.addWidget(self.seed_box)
        seed_row.addStretch(1)
        body.addLayout(seed_row)
        body.addWidget(
            QLabel(self.tr("Input: double-click a Keys or Mouse cell and press the key"))
        )
        self.input_table = BindingTable(len(INPUT_COLUMNS))
        self.input_table.setObjectName("inputTable")
        self.input_table.setToolTip(
            self.tr("Keys, mouse buttons and gamepad buttons of each action")
        )
        self.input_table.setHorizontalHeaderLabels([self.tr(c) for c in INPUT_COLUMNS])
        self.input_table.setMinimumHeight(180)
        header_view = self.input_table.horizontalHeader()
        if header_view is not None:
            header_view.setStretchLastSection(True)
        body.addWidget(self.input_table)
        right.addWidget(self.advanced)
        right.addStretch(1)
        self.seed_box.valueChanged.connect(self._on_seed_edited)
        self.input_table.itemChanged.connect(self._on_input_edited)

        self.preset_combo.activated.connect(self._on_preset_chosen)
        self.save_preset_button.clicked.connect(self.save_preset)
        self.manage_presets_button.clicked.connect(self.manage_presets)
        self._wide: bool | None = None
        self._apply_columns(False)

    def _reset_button(self, name: str, slot) -> QPushButton:  # noqa: ANN001
        button = QPushButton(self.tr("Reset to defaults"))
        button.setObjectName(name)
        button.setToolTip(self.tr("Put this section back to the defaults"))
        button.clicked.connect(slot)
        return button

    # ------------------------------------------------------------------ layout

    def _apply_columns(self, wide: bool) -> None:
        if wide == self._wide:
            return
        self._wide = wide
        self.columns.setDirection(
            QBoxLayout.Direction.LeftToRight if wide else QBoxLayout.Direction.TopToBottom
        )

    def resizeEvent(self, event) -> None:  # noqa: ANN001, N802
        super().resizeEvent(event)
        self._apply_columns(self.width() >= WIDE_WIDTH)
        self._place_summary(self.width() >= SUMMARY_SIDE_WIDTH)

    def _place_summary(self, side: bool) -> None:
        """Move the summary card between the top of the page and the right-hand column."""
        if side == self._summary_on_side:
            return
        self._summary_on_side = side
        if side:
            self._summary_outer.removeWidget(self.summary)
            self.side_layout.insertWidget(0, self.summary)
        else:
            self.side_layout.removeWidget(self.summary)
            self._summary_outer.insertWidget(1, self.summary)
        self.side.setVisible(side)
        self.summary.show()

    @property
    def summary_on_side(self) -> bool:
        return self._summary_on_side

    def refresh_summary(self) -> None:
        """Re-draw the summary from the options as they are now (it updates live)."""
        if self.draft is None:
            return
        wanted = {k: b.isChecked() for k, b in self.feature_boxes.items()}
        summary = options.summarize(
            self.draft.archetype,
            wanted,
            self.draft.starter_map_options(),
            self.draft.base_tile_size,
            self.resolution.value(),
        )
        settings = app_settings.get()
        assets = len(self.state.catalog.assets) if self.state and self.state.catalog else 0
        seconds = options.estimate_generation_seconds(
            settings.phase_timings, settings.timing_assets, assets
        )
        pack_bytes = self._pack_size()
        self.summary.set_summary(
            summary, seconds, options.estimate_project_bytes(pack_bytes) if pack_bytes else None
        )

    def _pack_size(self) -> int:
        """The bytes of the packs (an archive counts as its unpacked size when it is a zip),
        read once per set of packs."""
        sources = tuple(str(p) for p in (self.state.pack_sources if self.state else []))
        if sources != self._pack_bytes_key:
            self._pack_bytes_key = sources
            self._pack_bytes = sum(preflight.pack_stats(Path(s))[2] or 0 for s in sources)
        return self._pack_bytes

    @property
    def two_columns(self) -> bool:
        return bool(self._wide)

    # ------------------------------------------------------------------ loading

    def _refresh_git_box(self, state: WizardState) -> None:
        """New project: "Initialize git repository" (on by default). Regeneration: "Commit
        regeneration" (off by default). Disabled without git."""
        available = vcs.git_available()
        regenerating = state.regenerating
        self.git_box.blockSignals(True)
        self.git_box.setText(
            self.tr("Commit regeneration") if regenerating else self.tr("Initialize git repository")
        )
        self.git_box.setEnabled(available)
        self.git_box.setToolTip("" if available else self.tr("git was not found on this computer"))
        want = state.git_commit if state.git_commit is not None else not regenerating
        self.git_box.setChecked(bool(want) and available)
        self.git_box.blockSignals(False)

    def _on_git(self, checked: bool) -> None:
        if self.state is not None:
            self.state.git_commit = checked

    def _on_pack_art(self, choice: str) -> None:
        if self._loading or self.draft is None:
            return
        if choice == config_mod.GIT_DEFAULTS["pack_art"]:
            self.draft.git.pop("pack_art", None)
        else:
            self.draft.git["pack_art"] = choice
        self.changed.emit()

    def enter(self, state: WizardState) -> None:
        self.state = state
        self._refresh_git_box(state)
        self._fill_presets()
        cfg = state.config
        if cfg is None:
            self.draft = None
            return
        self.draft = dataclasses.replace(
            cfg,
            map_layers=list(cfg.map_layers),
            features=dict(cfg.features),
            input=copy.deepcopy(cfg.input),
            validation=dict(cfg.validation),
            starter_map=copy.deepcopy(cfg.starter_map),
            git=dict(cfg.git),
        )
        self._fill_ground_choices()
        self._lock_starter_if_it_exists()
        self._load_draft()
        self.changed.emit()

    def _load_draft(self) -> None:
        """Shows the draft in the widgets."""
        assert self.draft is not None
        self._loading = True
        try:
            self._demo_wish = self.draft.features.get("demo", True)
            for key, box in self.feature_boxes.items():
                box.setChecked(self.draft.features.get(key, False))
            self.resolution.set_value(self.draft.resolution)
            self.window_editor.set_value(self.draft.window_size)
            self.seed_box.setValue(min(self.draft.seed, SEED_MAX))
            self._fill_layers(self.draft.map_layers)
            self.input_map = copy.deepcopy(self.draft.input)
            self._fill_input_table()
            self._load_starter(self.draft.starter_map_options())
            self.pack_art_radios[self.draft.pack_art].setChecked(True)
        finally:
            self._loading = False
        self._update_dependencies()
        self._update_hint()
        self._schedule_preview()
        self.refresh_summary()

    def leave(self, state: WizardState) -> bool | None:
        cfg = state.config
        if cfg is None or self.draft is None:
            return None
        self._collect()
        cfg.features = dict(self.draft.features)
        cfg.resolution = self.draft.resolution
        cfg.window_size = self.draft.window_size
        cfg.map_layers = list(self.draft.map_layers)
        cfg.seed = self.draft.seed
        cfg.input = copy.deepcopy(self.draft.input)
        cfg.validation = dict(self.draft.validation)
        cfg.git = dict(self.draft.git)
        if not self._starter_locked:
            cfg.starter_map = copy.deepcopy(self.draft.starter_map)
        return None

    # ------------------------------------------------------------------ features

    def _on_feature(self, key: str, checked: bool) -> None:
        if self._loading:
            return
        if key == "demo":
            self._demo_wish = checked
        self._update_dependencies()
        self._on_edited()

    def _update_dependencies(self) -> None:
        """A feature whose dependencies are off is unchecked and disabled and says what it needs
        in plain sight; it returns to the user's choice once they are on again."""
        was = self._loading
        self._loading = True
        try:
            current = {k: b.isChecked() for k, b in self.feature_boxes.items()}
            for key in options.FEATURE_DEPS:
                box = self.feature_boxes[key]
                needs = self.feature_needs[key]
                missing = options.missing_deps(current, key)
                if missing:
                    box.setChecked(False)
                    box.setEnabled(False)
                    names = ", ".join(self.tr(options.feature_label(m)) for m in missing)
                    box.setToolTip(self.tr("Requires: {0}").format(names))
                    needs.setText(self.tr("Needs: {0}").format(names))
                    needs.setVisible(True)
                else:
                    box.setEnabled(True)
                    box.setToolTip(self.tr(options.FEATURE_INFO[key][2]))
                    box.setChecked(self._demo_wish)
                    needs.setVisible(False)
        finally:
            self._loading = was

    def _reset_features(self) -> None:
        defaults = config_mod.default_features()
        self._loading = True
        try:
            self._demo_wish = defaults.get("demo", True)
            for key, box in self.feature_boxes.items():
                box.setChecked(defaults.get(key, False))
        finally:
            self._loading = False
        self._update_dependencies()
        self._on_edited()

    # ------------------------------------------------------------------ screen

    def _update_hint(self) -> None:
        tile = self.draft.base_tile_size if self.draft else 16
        self.hint_label.setText(options.tiles_hint(self.resolution.value(), tile))
        self.resolution.mark_suggested(options.suggested_preset(options.RESOLUTION_PRESETS, tile))

    def _reset_screen(self) -> None:
        self.resolution.set_value(config_mod.GeneratorConfig("x", []).resolution)
        self.window_editor.set_value(config_mod.GeneratorConfig("x", []).window_size)
        self._on_edited()

    # ------------------------------------------------------------------ starter map

    def _fill_ground_choices(self) -> None:
        """The ground set combo lists the tile sheets that are GROUND; hidden when there is one."""
        from rpggen.core import catalog as catalog_mod

        self.ground_combo.blockSignals(True)
        self.ground_combo.clear()
        self.ground_combo.addItem(self.tr("Automatic (the first ground set)"), "")
        catalog = self.state.catalog if self.state else None
        sheets = []
        if catalog is not None:
            sheets = [
                a
                for a in sorted(catalog.assets, key=lambda a: a.id)
                if a.status not in ("UNUSED", "MISSING")
                and catalog_mod.effective(a).get("role") == "GROUND"
                and catalog_mod.effective(a).get("usage") == "tiles"
            ]
        for asset in sheets:
            self.ground_combo.addItem(
                f"{asset.path.rsplit('/', 1)[-1]} · {asset.pack_id}", asset.id
            )
        self.ground_combo.blockSignals(False)
        many = len(sheets) > 1
        self.ground_combo.setVisible(many)
        self.ground_label.setVisible(many)

    def _starter_exists(self) -> bool:
        state = self.state
        if state is None or not state.regenerating or state.target is None:
            return False
        return (state.target / "game" / "maps" / "starter_map.tscn").is_file()

    def _lock_starter_if_it_exists(self) -> None:
        """An existing starter map is the user's: its options are shown but cannot change."""
        locked = self._starter_exists()
        self._starter_locked = locked
        for widget in (
            self.starter_size,
            self.ground_combo,
            self.starter_reset,
            *self.starter_counts.values(),
        ):
            widget.setEnabled(not locked)
        self.starter_note.setText(self.tr(EXISTING_MAP_TEXT))
        self.starter_note.setVisible(locked)
        if locked:
            self.preview.set_disabled(self.tr(EXISTING_MAP_TEXT))

    def _load_starter(self, values: dict[str, Any]) -> None:
        self.starter_size.set_value((int(values["size"][0]), int(values["size"][1])))
        for key, spin in self.starter_counts.items():
            spin.setValue(int(values[key]))
        index = self.ground_combo.findData(values.get("ground", ""))
        self.ground_combo.setCurrentIndex(max(0, index))
        if self._starter_locked:
            self.starter_size.setEnabled(False)

    def starter_values(self) -> dict[str, Any]:
        """The starter map options as the widgets show them."""
        values: dict[str, Any] = {
            "size": list(self.starter_size.value()),
            "ground": self.ground_combo.currentData() or "",
        }
        for key, spin in self.starter_counts.items():
            values[key] = spin.value()
        return values

    def _on_starter_edited(self, *_args: object) -> None:
        if self._loading or self.draft is None:
            return
        self._collect_starter()
        self._schedule_preview()
        self.refresh_summary()
        self.changed.emit()

    def _collect_starter(self) -> None:
        """Stores only what differs from the defaults of the archetype."""
        if self.draft is None or self._starter_locked:
            return
        defaults = config_mod.starter_map_defaults(self.draft.archetype)
        values = self.starter_values()
        self.draft.starter_map = {k: v for k, v in values.items() if v != defaults[k]}

    def _reset_starter(self) -> None:
        if self.draft is None:
            return
        self._loading = True
        try:
            self._load_starter(config_mod.starter_map_defaults(self.draft.archetype))
        finally:
            self._loading = False
        self._on_starter_edited()

    def _schedule_preview(self) -> None:
        if self._starter_locked or self.draft is None or self.state is None:
            return
        catalog = self.state.catalog
        if catalog is None:
            return
        from rpggen.gui.pages.audit_page import make_resolver

        options_now = {
            **config_mod.starter_map_defaults(self.draft.archetype),
            **self.starter_values(),
        }
        self.preview.request(
            catalog,
            make_resolver(self.state),
            options_now,
            self.draft.seed,
            self.draft.archetype,
            options_now["ground"],
            "",
        )

    def reroll(self) -> None:
        """A new seed (shown under Advanced) gives another arrangement."""
        self.seed_box.setValue(random.randint(0, SEED_MAX))

    def _on_seed_edited(self, *_args: object) -> None:
        if self._loading or self.draft is None:
            return
        self.draft.seed = self.seed_box.value()
        self._schedule_preview()
        self._on_edited()

    # ------------------------------------------------------------------ layers

    def _fill_layers(self, layers: list[str]) -> None:
        self.layer_list.clear()
        self.layer_list.addItems(layers)
        self.layer_list.setCurrentRow(0)
        self._update_layer_buttons()

    def layers(self) -> list[str]:
        items = (self.layer_list.item(i) for i in range(self.layer_list.count()))
        return [item.text() for item in items if item is not None]

    def _update_layer_buttons(self) -> None:
        item = self.layer_list.currentItem()
        row = self.layer_list.currentRow()
        self.remove_layer_button.setEnabled(item is not None and item.text() != "Ground")
        self.up_button.setEnabled(row > 0)
        self.down_button.setEnabled(0 <= row < self.layer_list.count() - 1)

    def add_layer(self) -> None:
        old = self.layers()
        new = options.add_layer(old, self.layer_name.text())
        if new != old:
            self._fill_layers(new)
            self.layer_list.setCurrentRow(len(new) - 1)
            self.layer_name.clear()
            self._on_edited()

    def remove_layer(self) -> None:
        item = self.layer_list.currentItem()
        if item is None:
            return
        old = self.layers()
        new = options.remove_layer(old, item.text())
        if new != old:
            self._fill_layers(new)
            self._on_edited()

    def move_layer(self, delta: int) -> None:
        row = self.layer_list.currentRow()
        target = row + delta
        if row < 0 or not 0 <= target < self.layer_list.count():
            return
        item = self.layer_list.takeItem(row)
        self.layer_list.insertItem(target, item)
        self.layer_list.setCurrentRow(target)
        self._on_edited()

    def _reset_layers(self) -> None:
        self._fill_layers(list(config_mod.DEFAULT_MAP_LAYERS))
        self._on_edited()

    # ------------------------------------------------------------------ input map

    def _fill_input_table(self) -> None:
        self.input_table.blockSignals(True)
        self.input_table.setRowCount(0)
        for action, bindings in self.input_map.items():
            row = self.input_table.rowCount()
            self.input_table.insertRow(row)
            name = QTableWidgetItem(action)
            name.setFlags(name.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.input_table.setItem(row, 0, name)
            for col, (field, _kind) in enumerate(options.BINDING_FIELDS, start=1):
                text = options.format_list(bindings.get(field, []))
                self.input_table.setItem(row, col, QTableWidgetItem(text))
        self.input_table.blockSignals(False)

    def _on_input_edited(self, _item: QTableWidgetItem) -> None:
        if not self._loading:
            self._on_edited()

    def _cell(self, row: int, col: int) -> str:
        item = self.input_table.item(row, col)
        return item.text() if item is not None else ""

    def _collect_input(self) -> None:
        self._input_errors = []
        result: dict[str, dict[str, Any]] = {}
        for row in range(self.input_table.rowCount()):
            action = self._cell(row, 0)
            bindings = copy.deepcopy(self.input_map.get(action, {}))
            for col, (field, _kind) in enumerate(options.BINDING_FIELDS, start=1):
                try:
                    bindings = options.apply_binding_text(bindings, field, self._cell(row, col))
                except ValueError:
                    self._input_errors.append(
                        self.tr("{0}: {1} must be whole numbers separated by commas.").format(
                            action, self.tr(INPUT_COLUMNS[col])
                        )
                    )
            result[action] = bindings
        self._collected_input = result

    # ------------------------------------------------------------------ presets

    def _fill_presets(self) -> None:
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        self.preset_combo.addItem(self.tr("Choose a preset…"), None)
        self.preset_combo.addItem(self.tr("Defaults"), DEFAULTS_ITEM)
        for name in sorted(app_settings.get().option_presets):
            self.preset_combo.addItem(name, name)
        self.preset_combo.blockSignals(False)

    def apply_preset_named(self, name: str) -> bool:
        """Applies a saved preset (or the defaults) to the page; False when it does not fit."""
        if self.draft is None:
            return False
        saved = app_settings.get().option_presets
        preset = (
            options.default_preset(self.draft.archetype)
            if name == DEFAULTS_ITEM
            else saved.get(name)
        )
        if preset is None:
            return False
        try:
            self._collect()
            new = options.apply_preset(self.draft, preset)
        except ValueError as exc:
            self.show_message(
                self.tr("Preset"), self.tr("The preset does not fit: {0}").format(exc)
            )
            return False
        keep_seed = self.draft.seed  # a preset never changes the seed
        self.draft = dataclasses.replace(new, seed=keep_seed)
        if self._starter_locked:  # the starter map is the user's: only the other options change
            self.draft.starter_map = {}
        self._load_draft()
        self.changed.emit()
        return True

    def _on_preset_chosen(self, index: int) -> None:
        name = self.preset_combo.itemData(index)
        if name is not None:
            self.apply_preset_named(name)
        self.preset_combo.setCurrentIndex(0)

    def ask_preset_name(self) -> str | None:  # overridden by tests
        text, ok = QInputDialog.getText(
            self, self.tr("Save as preset"), self.tr("Name of the preset")
        )
        return text.strip() if ok and text.strip() else None

    def show_message(self, title: str, text: str) -> None:  # overridden by tests
        QMessageBox.warning(self, title, text)

    def save_preset(self) -> str | None:
        if self.draft is None:
            return None
        name = self.ask_preset_name()
        if name is None or name == self.tr("Defaults"):
            return None
        self._collect()
        preset = options.to_preset(self.draft)
        app_settings.store().update(lambda settings: settings.option_presets.update({name: preset}))
        self._fill_presets()
        return name

    def manage_presets(self) -> None:
        dialog = ManagePresetsDialog(sorted(app_settings.get().option_presets), self)
        self.run_dialog(dialog)

        def apply(settings: app_settings.AppSettings) -> None:
            for old, new in dialog.renames.items():
                if old in settings.option_presets:
                    settings.option_presets[new] = settings.option_presets.pop(old)
            for name in dialog.deleted:
                settings.option_presets.pop(name, None)

        app_settings.store().update(apply)
        self._fill_presets()

    def run_dialog(self, dialog) -> bool:  # noqa: ANN001 - overridden by tests
        return bool(dialog.exec())

    # ------------------------------------------------------------------ collecting

    def _collect(self) -> None:
        if self.draft is None:
            return
        self.draft.features = options.effective_features(
            {k: b.isChecked() for k, b in self.feature_boxes.items()}
        )
        self.draft.resolution = self.resolution.value()
        self.draft.window_size = self.window_editor.value()
        self.draft.map_layers = self.layers()
        self.draft.seed = self.seed_box.value()
        self._collect_starter()
        self._collect_input()
        if not self._input_errors:
            self.draft.input = self._collected_input

    def _on_edited(self, *_args: object) -> None:
        if self._loading or self.draft is None:
            return
        self._update_hint()
        self._update_layer_buttons()
        self.refresh_summary()
        self.changed.emit()

    # ------------------------------------------------------------------ wizard hooks

    def status(self, state: WizardState) -> tuple[str, int]:
        return ("ok", 0) if state.config is not None else ("none", 0)

    def validate(self, state: WizardState) -> list[Issue]:
        if self.draft is None:
            return []
        self._collect()
        layer_problems = [
            self.tr(LAYER_MESSAGES[m]) for m in options.layer_issues(self.draft.map_layers)
        ]
        problems = [*layer_problems, *self._input_errors, *options.config_errors(self.draft)]
        return [form_error(p) for p in problems]
