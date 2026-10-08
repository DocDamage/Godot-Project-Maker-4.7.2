"""The sections of the Options page. Each one builds its widgets and shows or reads its values;
``rpggen.gui.models.options_model`` decides what they show, the page wires them together."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QCoreApplication, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rpggen.core import config as config_mod
from rpggen.core import options
from rpggen.gui.models.options_model import (
    DEFAULTS_ITEM,
    EXPORT_TARGET_LABELS,
    INPUT_COLUMNS,
    PACK_ART_LABELS,
    SEED_MAX,
    STARTER_COUNTS,
    STARTER_SIZE_NAMES,
    FeatureState,
    StarterState,
)
from rpggen.gui.widgets.binding_table import BindingTable
from rpggen.gui.widgets.collapsible import CollapsibleSection
from rpggen.gui.widgets.map_preview import MapPreviewWidget
from rpggen.gui.widgets.size_editor import SizeEditor, spin


def _tr(text: str) -> str:
    return QCoreApplication.translate("OptionsSections", text)


def reset_button(name: str) -> QPushButton:
    button = QPushButton(_tr("Reset to defaults"))
    button.setObjectName(name)
    button.setToolTip(_tr("Put this section back to the defaults"))
    return button


def _muted(text: str, name: str = "") -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setProperty("muted", True)
    if name:
        label.setObjectName(name)
    return label


class PresetBar(QWidget):
    """The preset combo and the buttons that save and manage presets."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        header = QHBoxLayout(self)
        header.setContentsMargins(6, 4, 6, 0)
        header.addWidget(QLabel(self.tr("Preset")))
        self.combo = QComboBox()
        self.combo.setObjectName("presetCombo")
        self.combo.setToolTip(
            self.tr(
                "Apply the options of a saved preset (packs, name and seed are not part of one)"
            )
        )
        self.combo.setMinimumWidth(180)
        header.addWidget(self.combo)
        self.save_button = QPushButton(self.tr("Save as preset…"))
        self.save_button.setObjectName("savePreset")
        self.save_button.setToolTip(self.tr("Keep the options below for your next project"))
        self.manage_button = QPushButton(self.tr("Manage…"))
        self.manage_button.setObjectName("managePresetsButton")
        self.manage_button.setToolTip(self.tr("Rename or delete saved presets"))
        header.addWidget(self.save_button)
        header.addWidget(self.manage_button)
        header.addStretch(1)

    def fill(self, names: list[str]) -> None:
        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItem(self.tr("Choose a preset…"), None)
        self.combo.addItem(self.tr("Defaults"), DEFAULTS_ITEM)
        for name in names:
            self.combo.addItem(name, name)
        self.combo.blockSignals(False)


class FeatureGroups(QWidget):
    """A group box of check boxes per feature group, each with its sentence and, for a feature
    whose dependencies are off, what it needs."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.boxes: dict[str, QCheckBox] = {}
        self.needs: dict[str, QLabel] = {}
        self.reset = reset_button("resetFeatures")
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
                description = _muted(self.tr(text), f"featureText_{key}")
                description.setContentsMargins(22, 0, 0, 4)
                needs = QLabel()
                needs.setObjectName(f"featureNeeds_{key}")
                needs.setProperty("state", "warning")
                needs.setContentsMargins(22, 0, 0, 2)
                needs.setVisible(False)
                self.boxes[key] = check
                self.needs[key] = needs
                vbox.addWidget(check)
                vbox.addWidget(needs)
                vbox.addWidget(description)
            if group == options.FEATURE_GROUPS[0]:
                vbox.addWidget(self.reset, 0, Qt.AlignmentFlag.AlignRight)
            layout.addWidget(box)

    def values(self) -> dict[str, bool]:
        return {k: b.isChecked() for k, b in self.boxes.items()}

    def set_values(self, values: dict[str, bool]) -> None:
        for key, box in self.boxes.items():
            box.setChecked(values.get(key, False))

    def show_states(self, states: dict[str, FeatureState]) -> None:
        for key, state in states.items():
            box, needs = self.boxes[key], self.needs[key]
            if not state.enabled:
                box.setChecked(False)
            box.setEnabled(state.enabled)
            box.setToolTip(state.tooltip)
            if state.enabled:
                box.setChecked(state.checked)
            needs.setText(state.needs)
            needs.setVisible(bool(state.needs))


class StarterMapBox(QGroupBox):
    """Size, counts and ground set of the generated starter map, and its preview."""

    edited = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setTitle(self.tr("Starter map"))
        self.setObjectName("starterMap")
        layout = QVBoxLayout(self)
        self.note = QLabel()
        self.note.setObjectName("starterNote")
        self.note.setWordWrap(True)
        self.note.setProperty("state", "warning")
        self.note.setVisible(False)
        layout.addWidget(self.note)
        self.size_editor = SizeEditor(
            "starterSize", options.STARTER_SIZE_PRESETS, 24, 96, STARTER_SIZE_NAMES
        )
        self.size_editor.setToolTip(
            self.tr("Width and height of the starter map in tiles (24 to 96)")
        )
        layout.addWidget(QLabel(self.tr("Size in tiles")))
        layout.addWidget(self.size_editor)
        counts = QHBoxLayout()
        self.counts: dict[str, QSpinBox] = {}
        for key, label in STARTER_COUNTS:
            low, high = config_mod.STARTER_MAP_COUNTS[key]
            box = spin(low, high)
            box.setObjectName(f"starter_{key}")
            box.setToolTip(self.tr("{0}: {1} to {2}").format(self.tr(label), low, high))
            self.counts[key] = box
            column = QVBoxLayout()
            column.addWidget(QLabel(self.tr(label)))
            column.addWidget(box)
            counts.addLayout(column)
        layout.addLayout(counts)
        ground_row = QHBoxLayout()
        self.ground_label = QLabel(self.tr("Ground set"))
        self.ground_combo = QComboBox()
        self.ground_combo.setObjectName("starterGround")
        self.ground_combo.setToolTip(self.tr("The tile sheet the starter map is painted with"))
        ground_row.addWidget(self.ground_label)
        ground_row.addWidget(self.ground_combo, 1)
        layout.addLayout(ground_row)
        self.reset = reset_button("resetStarter")
        layout.addWidget(self.reset, 0, Qt.AlignmentFlag.AlignRight)
        self.preview = MapPreviewWidget()
        layout.addWidget(self.preview)
        self.size_editor.width_box.valueChanged.connect(self.edited)
        self.size_editor.height_box.valueChanged.connect(self.edited)
        self.size_editor.combo.currentIndexChanged.connect(self.edited)
        for box in self.counts.values():
            box.valueChanged.connect(self.edited)
        self.ground_combo.currentIndexChanged.connect(self.edited)

    def fill_ground(self, choices: list[tuple[str, str]]) -> None:
        """The ground set combo lists the GROUND tile sheets; hidden when there is one."""
        self.ground_combo.blockSignals(True)
        self.ground_combo.clear()
        self.ground_combo.addItem(self.tr("Automatic (the first ground set)"), "")
        for label, asset_id in choices:
            self.ground_combo.addItem(label, asset_id)
        self.ground_combo.blockSignals(False)
        many = len(choices) > 1
        self.ground_combo.setVisible(many)
        self.ground_label.setVisible(many)

    def load(self, values: dict[str, Any], locked: bool) -> None:
        self.size_editor.set_value((int(values["size"][0]), int(values["size"][1])))
        for key, box in self.counts.items():
            box.setValue(int(values[key]))
        index = self.ground_combo.findData(values.get("ground", ""))
        self.ground_combo.setCurrentIndex(max(0, index))
        if locked:
            self.size_editor.setEnabled(False)

    def values(self) -> dict[str, Any]:
        """The starter map options as the widgets show them."""
        out: dict[str, Any] = {
            "size": list(self.size_editor.value()),
            "ground": self.ground_combo.currentData() or "",
        }
        for key, box in self.counts.items():
            out[key] = box.value()
        return out

    def show_state(self, state: StarterState) -> None:
        for widget in (self.size_editor, self.ground_combo, self.reset, *self.counts.values()):
            widget.setEnabled(state.layout_enabled)
        self.note.setText(state.note)
        self.note.setVisible(state.note_visible)
        if state.note_visible:
            self.preview.set_disabled(state.note)


class ImportedMapsBox(QGroupBox):
    """The Tiled and LDtk maps of the packs: which to build, and which one is the starter."""

    edited = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setTitle(self.tr("Imported maps"))
        self.setObjectName("importedMaps")
        layout = QVBoxLayout(self)
        layout.addWidget(
            _muted(
                self.tr(
                    "Maps found in your packs (Tiled and LDtk files). A checked map is built into "
                    "game/maps/imported."
                )
            )
        )
        self.list = QListWidget()
        self.list.setObjectName("importedList")
        self.list.setMinimumHeight(90)
        self.list.setToolTip(self.tr("Check the maps to build into your project"))
        layout.addWidget(self.list)
        starter_row = QHBoxLayout()
        starter_row.addWidget(QLabel(self.tr("Starter map")))
        self.starter = QComboBox()
        self.starter.setObjectName("importedStarter")
        self.starter.setToolTip(
            self.tr(
                "Use an imported map as the starter map; the layout options above are then skipped"
            )
        )
        starter_row.addWidget(self.starter, 1)
        layout.addLayout(starter_row)
        self.solid_button = QPushButton(self.tr("Solid values…"))
        self.solid_button.setObjectName("solidValuesButton")
        self.solid_button.setToolTip(
            self.tr("Choose which values of the LDtk IntGrid layers block the player")
        )
        layout.addWidget(self.solid_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.note = _muted("", "importedNote")
        layout.addWidget(self.note)
        self.setVisible(False)
        self.list.itemChanged.connect(self.edited)
        self.starter.currentIndexChanged.connect(self.edited)

    def _block(self, on: bool) -> None:
        self.list.blockSignals(on)
        self.starter.blockSignals(on)

    def fill(self, rows: list[tuple[str, str, str]], has_intgrid: bool) -> None:
        """Lists the maps (label, id, source); the box is hidden when the packs have none."""
        self._block(True)
        self.list.clear()
        self.starter.clear()
        self.starter.addItem(self.tr("Generated by the layout options"), "")
        for label, map_id, source in rows:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, map_id)
            item.setToolTip(source)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.list.addItem(item)
            self.starter.addItem(self.tr("Use {0}").format(label), map_id)
        self._block(False)
        self.setVisible(bool(rows))
        self.solid_button.setVisible(has_intgrid)

    def load(self, chosen: dict[str, Any]) -> None:
        self._block(True)
        for row in range(self.list.count()):
            item = self.list.item(row)
            on = item.data(Qt.ItemDataRole.UserRole) in chosen.get("include", [])
            item.setCheckState(Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)
        self.starter.setCurrentIndex(max(0, self.starter.findData(chosen.get("starter", ""))))
        self._block(False)
        self.sync_starter_item()

    def sync_starter_item(self) -> None:
        """The starter map is always built, so its box is checked and cannot be cleared."""
        starter = self.starter.currentData() or ""
        self.list.blockSignals(True)
        for row in range(self.list.count()):
            item = self.list.item(row)
            flags = item.flags()
            if item.data(Qt.ItemDataRole.UserRole) == starter:
                item.setCheckState(Qt.CheckState.Checked)
                item.setFlags(flags & ~Qt.ItemFlag.ItemIsUserCheckable)
                item.setToolTip(self.tr("The starter map is always built"))
            else:
                item.setFlags(flags | Qt.ItemFlag.ItemIsUserCheckable)
        self.list.blockSignals(False)
        self.note.setText(
            self.tr(
                "The starter map is built from the chosen map; it has no villager, chest or enemy."
            )
            if starter
            else ""
        )

    def selection(self) -> tuple[list[str], str]:
        """The checked map ids and the starter map id ("" for the generated one)."""
        include = [
            self.list.item(row).data(Qt.ItemDataRole.UserRole)
            for row in range(self.list.count())
            if self.list.item(row).checkState() == Qt.CheckState.Checked
        ]
        return include, self.starter.currentData() or ""


class ScreenBox(QGroupBox):
    """Game resolution and window size."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setTitle(self.tr("Screen"))
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(self.tr("Game resolution")))
        self.resolution = SizeEditor("resolution", options.RESOLUTION_PRESETS, 160, 3840)
        self.resolution.setToolTip(
            self.tr("How many pixels the game draws (the picture is scaled to the window)")
        )
        layout.addWidget(self.resolution)
        self.hint_label = QLabel()
        self.hint_label.setObjectName("tilesHint")
        layout.addWidget(self.hint_label)
        layout.addWidget(QLabel(self.tr("Window size")))
        self.window_editor = SizeEditor("window", options.WINDOW_PRESETS, 160, 7680)
        self.window_editor.setToolTip(self.tr("The size of the game window"))
        layout.addWidget(self.window_editor)
        self.reset = reset_button("resetScreen")
        layout.addWidget(self.reset, 0, Qt.AlignmentFlag.AlignRight)


class LayersBox(QGroupBox):
    """The map layers, back to front: add, remove, reorder (drag or buttons), reset."""

    edited = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setTitle(self.tr("Map layers"))
        layout = QHBoxLayout(self)
        self.list = QListWidget()
        self.list.setObjectName("layerList")
        self.list.setToolTip(self.tr("Map layers, back to front. Drag to reorder."))
        self.list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.list.setMinimumHeight(110)
        layout.addWidget(self.list, 1)
        self.name = QLineEdit()
        self.name.setObjectName("layerName")
        self.name.setPlaceholderText(self.tr("New layer name"))

        def button(text: str, name: str, tooltip: str) -> QPushButton:
            b = QPushButton(text)
            b.setObjectName(name)
            b.setToolTip(tooltip)
            return b

        self.add_button = button(
            self.tr("Add"), "addLayer", self.tr("Add a layer with the name above")
        )
        self.remove_button = button(
            self.tr("Remove"), "removeLayer", self.tr("Remove the selected layer (not Ground)")
        )
        self.up_button = button(
            self.tr("Move up"), "layerUp", self.tr("Draw the selected layer earlier (further back)")
        )
        self.down_button = button(
            self.tr("Move down"),
            "layerDown",
            self.tr("Draw the selected layer later (further forward)"),
        )
        self.reset = reset_button("resetLayers")
        side = QVBoxLayout()
        for w in (
            self.name,
            self.add_button,
            self.remove_button,
            self.up_button,
            self.down_button,
            self.reset,
        ):
            side.addWidget(w)
        side.addStretch(1)
        layout.addLayout(side)
        self.list.model().rowsMoved.connect(self.edited)
        self.add_button.clicked.connect(self.add)
        self.remove_button.clicked.connect(self.remove)
        self.up_button.clicked.connect(lambda: self.move_row(-1))
        self.down_button.clicked.connect(lambda: self.move_row(1))
        self.reset.clicked.connect(self._reset)
        self.list.currentRowChanged.connect(lambda _r: self.update_buttons())

    def fill(self, layers: list[str]) -> None:
        self.list.clear()
        self.list.addItems(layers)
        self.list.setCurrentRow(0)
        self.update_buttons()

    def layers(self) -> list[str]:
        items = (self.list.item(i) for i in range(self.list.count()))
        return [item.text() for item in items if item is not None]

    def update_buttons(self) -> None:
        item = self.list.currentItem()
        row = self.list.currentRow()
        self.remove_button.setEnabled(item is not None and item.text() != "Ground")
        self.up_button.setEnabled(row > 0)
        self.down_button.setEnabled(0 <= row < self.list.count() - 1)

    def add(self) -> None:
        old = self.layers()
        new = options.add_layer(old, self.name.text())
        if new != old:
            self.fill(new)
            self.list.setCurrentRow(len(new) - 1)
            self.name.clear()
            self.edited.emit()

    def remove(self) -> None:
        item = self.list.currentItem()
        if item is None:
            return
        old = self.layers()
        new = options.remove_layer(old, item.text())
        if new != old:
            self.fill(new)
            self.edited.emit()

    def move_row(self, delta: int) -> None:
        row = self.list.currentRow()
        target = row + delta
        if row < 0 or not 0 <= target < self.list.count():
            return
        item = self.list.takeItem(row)
        self.list.insertItem(target, item)
        self.list.setCurrentRow(target)
        self.edited.emit()

    def _reset(self) -> None:
        self.fill(list(config_mod.DEFAULT_MAP_LAYERS))
        self.edited.emit()


class VersionControlBox(QGroupBox):
    """The git check box and where the pack art goes."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setTitle(self.tr("Version control"))
        self.setObjectName("versionControl")
        layout = QVBoxLayout(self)
        self.git_box = QCheckBox()
        self.git_box.setObjectName("gitBox")
        layout.addWidget(self.git_box)
        self.pack_art_radios: dict[str, QRadioButton] = {}
        group = QButtonGroup(self)
        for choice, label in PACK_ART_LABELS.items():
            radio = QRadioButton(self.tr(label))
            radio.setObjectName(f"packArt_{choice}")
            self.pack_art_radios[choice] = radio
            group.addButton(radio)
            layout.addWidget(radio)
        layout.addWidget(
            _muted(
                self.tr(
                    "Most pack licences do not allow the art to be public: if you will push this "
                    "project to a public site, leave the pack art out."
                ),
                "packArtNote",
            )
        )

    def show_git(self, text: str, available: bool, tooltip: str, checked: bool) -> None:
        self.git_box.blockSignals(True)
        self.git_box.setText(text)
        self.git_box.setEnabled(available)
        self.git_box.setToolTip(tooltip)
        self.git_box.setChecked(checked)
        self.git_box.blockSignals(False)


class ExportTargetsBox(QGroupBox):
    """One check box per platform that gets an export preset (T12.52)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setTitle(self.tr("Export targets"))
        self.setObjectName("exportTargets")
        layout = QVBoxLayout(self)
        self.boxes: dict[str, QCheckBox] = {}
        for key, label in EXPORT_TARGET_LABELS.items():
            box = QCheckBox(self.tr(label))
            box.setObjectName(f"exportTarget_{key}")
            self.boxes[key] = box
            layout.addWidget(box)
        layout.addWidget(
            _muted(
                self.tr(
                    "Each target gets an export preset. The export check tests the ones whose "
                    "export templates are installed."
                ),
                "exportTargetsNote",
            )
        )

    def set_values(self, chosen: list[str]) -> None:
        for key, box in self.boxes.items():
            box.blockSignals(True)
            box.setChecked(key in chosen)
            box.blockSignals(False)


class AdvancedOptions(CollapsibleSection):
    """The seed and the input bindings."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(_tr("Advanced"), parent)
        self.setObjectName("advanced")
        body = QVBoxLayout(self.body)
        body.setContentsMargins(0, 0, 0, 0)
        seed_row = QHBoxLayout()
        seed_row.addWidget(QLabel(self.tr("Seed")))
        self.seed_box = spin(0, SEED_MAX)
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

    def fill_input(self, rows: list[tuple[str, list[str]]]) -> None:
        table = self.input_table
        table.blockSignals(True)
        table.setRowCount(0)
        for action, cells in rows:
            row = table.rowCount()
            table.insertRow(row)
            name = QTableWidgetItem(action)
            name.setFlags(name.flags() & ~Qt.ItemFlag.ItemIsEditable)
            table.setItem(row, 0, name)
            for col, text in enumerate(cells, start=1):
                table.setItem(row, col, QTableWidgetItem(text))
        table.blockSignals(False)

    def input_rows(self) -> list[tuple[str, list[str]]]:
        def cell(row: int, col: int) -> str:
            item = self.input_table.item(row, col)
            return item.text() if item is not None else ""

        return [
            (cell(row, 0), [cell(row, col) for col in range(1, len(INPUT_COLUMNS))])
            for row in range(self.input_table.rowCount())
        ]
