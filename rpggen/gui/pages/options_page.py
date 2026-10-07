"""Page 5: features, resolution, window size, map layers and advanced settings."""

from __future__ import annotations

import copy
import dataclasses
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rpggen.core import config as config_mod
from rpggen.core import options, vcs
from rpggen.errors import Issue
from rpggen.gui.pages.base import WizardPage, form_error
from rpggen.gui.state import WizardState

FEATURE_LABELS = {
    "tilesets": "Tilesets",
    "collision": "Collision",
    "terrain": "Terrain",
    "animations": "Animations",
    "demo": "Demo scene",
    "editor_tools": "Editor tools",
    "save": "Save / load",
    "dialogue": "Dialogue",
    "combat": "Combat",
    "navigation": "Navigation",
    "debug_tools": "Debug tools",
}
INPUT_COLUMNS = ("Action", "Keys", "Mouse buttons", "Joy buttons")
SEED_MAX = 2**31 - 1
LAYER_MESSAGES = {
    options.LAYER_GROUND_REQUIRED: "The Ground layer is required.",
    options.LAYER_EMPTY: "Layer names cannot be empty.",
    options.LAYER_DUPLICATE: "Layer names must be unique.",
}


def _spin(low: int, high: int) -> QSpinBox:
    box = QSpinBox()
    box.setRange(low, high)
    return box


class SizeEditor(QWidget):
    """A preset combo plus width / height spin boxes that are enabled for Custom."""

    def __init__(self, name: str, presets: list[tuple[int, int]], low: int, high: int) -> None:
        super().__init__()
        self.presets = presets
        self.combo = QComboBox()
        self.combo.setObjectName(f"{name}Combo")
        for w, h in presets:
            self.combo.addItem(f"{w} × {h}", (w, h))
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

    def value(self) -> tuple[int, int]:
        return (self.width_box.value(), self.height_box.value())

    def set_value(self, value: tuple[int, int]) -> None:
        self.width_box.setValue(value[0])
        self.height_box.setValue(value[1])
        index = options.preset_index(self.presets, value)
        self.combo.setCurrentIndex(index)
        self._on_combo(index)


class OptionsPage(WizardPage):
    title = "Options"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.state: WizardState | None = None
        self.draft: config_mod.GeneratorConfig | None = None
        self.input_map: dict[str, dict[str, Any]] = {}
        self._collected_input: dict[str, dict[str, Any]] = {}
        self._input_errors: list[str] = []
        self._loading = False
        self._demo_wish = True
        layout = QVBoxLayout(self)

        features_box = QGroupBox(self.tr("Features"))
        features_layout = QVBoxLayout(features_box)
        self.feature_boxes: dict[str, QCheckBox] = {}
        for key in config_mod.FEATURE_KEYS:
            box = QCheckBox(self.tr(FEATURE_LABELS.get(key, key)))
            box.setObjectName(f"feature_{key}")
            self.feature_boxes[key] = box
            features_layout.addWidget(box)
            box.toggled.connect(lambda checked, k=key: self._on_feature(k, checked))
        layout.addWidget(features_box)

        screen = QGroupBox(self.tr("Screen"))
        screen_layout = QVBoxLayout(screen)
        screen_layout.addWidget(QLabel(self.tr("Game resolution")))
        self.resolution = SizeEditor("resolution", options.RESOLUTION_PRESETS, 160, 3840)
        screen_layout.addWidget(self.resolution)
        self.hint_label = QLabel()
        self.hint_label.setObjectName("tilesHint")
        screen_layout.addWidget(self.hint_label)
        screen_layout.addWidget(QLabel(self.tr("Window size")))
        self.window_editor = SizeEditor("window", options.WINDOW_PRESETS, 160, 7680)
        screen_layout.addWidget(self.window_editor)
        layout.addWidget(screen)
        for editor in (self.resolution, self.window_editor):
            editor.width_box.valueChanged.connect(self._on_edited)
            editor.height_box.valueChanged.connect(self._on_edited)

        layers_box = QGroupBox(self.tr("Map layers"))
        layers_layout = QHBoxLayout(layers_box)
        self.layer_list = QListWidget()
        self.layer_list.setObjectName("layerList")
        self.layer_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.layer_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.layer_list.model().rowsMoved.connect(self._on_edited)
        layers_layout.addWidget(self.layer_list, 1)
        side = QVBoxLayout()
        self.layer_name = QLineEdit()
        self.layer_name.setObjectName("layerName")
        self.layer_name.setPlaceholderText(self.tr("New layer name"))
        self.add_layer_button = QPushButton(self.tr("Add"))
        self.add_layer_button.setObjectName("addLayer")
        self.remove_layer_button = QPushButton(self.tr("Remove"))
        self.remove_layer_button.setObjectName("removeLayer")
        self.up_button = QPushButton(self.tr("Move up"))
        self.up_button.setObjectName("layerUp")
        self.down_button = QPushButton(self.tr("Move down"))
        self.down_button.setObjectName("layerDown")
        for w in (
            self.layer_name,
            self.add_layer_button,
            self.remove_layer_button,
            self.up_button,
            self.down_button,
        ):
            side.addWidget(w)
        side.addStretch(1)
        layers_layout.addLayout(side)
        layout.addWidget(layers_box)
        self.add_layer_button.clicked.connect(self.add_layer)
        self.remove_layer_button.clicked.connect(self.remove_layer)
        self.up_button.clicked.connect(lambda: self.move_layer(-1))
        self.down_button.clicked.connect(lambda: self.move_layer(1))
        self.layer_list.currentRowChanged.connect(lambda _r: self._update_layer_buttons())

        self.git_box = QCheckBox()
        self.git_box.setObjectName("gitBox")
        self.git_box.toggled.connect(self._on_git)
        layout.addWidget(self.git_box)

        self.advanced = QGroupBox(self.tr("Advanced"))
        self.advanced.setObjectName("advanced")
        self.advanced.setCheckable(True)
        self.advanced.setChecked(False)
        adv = QVBoxLayout(self.advanced)
        self.advanced_body = QWidget()
        body = QVBoxLayout(self.advanced_body)
        body.setContentsMargins(0, 0, 0, 0)
        seed_row = QHBoxLayout()
        seed_row.addWidget(QLabel(self.tr("Seed")))
        self.seed_box = _spin(0, SEED_MAX)
        self.seed_box.setObjectName("seed")
        seed_row.addWidget(self.seed_box)
        seed_row.addStretch(1)
        body.addLayout(seed_row)
        self.input_table = QTableWidget(0, len(INPUT_COLUMNS))
        self.input_table.setObjectName("inputTable")
        self.input_table.setHorizontalHeaderLabels([self.tr(c) for c in INPUT_COLUMNS])
        header = self.input_table.horizontalHeader()
        if header is not None:
            header.setStretchLastSection(True)
        body.addWidget(self.input_table)
        adv.addWidget(self.advanced_body)
        self.advanced_body.setVisible(False)
        self.advanced.toggled.connect(self.advanced_body.setVisible)
        layout.addWidget(self.advanced)
        self.seed_box.valueChanged.connect(self._on_edited)
        self.input_table.itemChanged.connect(self._on_input_edited)

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

    def enter(self, state: WizardState) -> None:
        self.state = state
        self._refresh_git_box(state)
        cfg = state.config
        if cfg is None:
            self.draft = None
            return
        self.draft = dataclasses.replace(
            cfg,
            map_layers=list(cfg.map_layers),
            features=dict(cfg.features),
            input=copy.deepcopy(cfg.input),
        )
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
        finally:
            self._loading = False
        self._update_dependencies()
        self._update_hint()
        self.changed.emit()

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
        """A feature whose dependencies are off is unchecked and disabled with a tooltip; it
        returns to the user's choice once they are on again."""
        was = self._loading
        self._loading = True
        try:
            current = {k: b.isChecked() for k, b in self.feature_boxes.items()}
            for key in options.FEATURE_DEPS:
                box = self.feature_boxes[key]
                missing = options.missing_deps(current, key)
                if missing:
                    box.setChecked(False)
                    box.setEnabled(False)
                    names = ", ".join(self.tr(FEATURE_LABELS.get(m, m)) for m in missing)
                    box.setToolTip(self.tr("Requires: {0}").format(names))
                else:
                    box.setEnabled(True)
                    box.setToolTip("")
                    box.setChecked(self._demo_wish)
        finally:
            self._loading = was

    # ------------------------------------------------------------------ screen

    def _update_hint(self) -> None:
        tile = self.draft.base_tile_size if self.draft else 16
        self.hint_label.setText(options.tiles_hint(self.resolution.value(), tile))

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
        self._collect_input()
        if not self._input_errors:
            self.draft.input = self._collected_input

    def _on_edited(self, *_args: object) -> None:
        if self._loading or self.draft is None:
            return
        self._update_hint()
        self._update_layer_buttons()
        self.changed.emit()

    # ------------------------------------------------------------------ wizard hooks

    def validate(self, state: WizardState) -> list[Issue]:
        if self.draft is None:
            return []
        self._collect()
        layer_problems = [
            self.tr(LAYER_MESSAGES[m]) for m in options.layer_issues(self.draft.map_layers)
        ]
        problems = [*layer_problems, *self._input_errors, *options.config_errors(self.draft)]
        return [form_error(p) for p in problems]
