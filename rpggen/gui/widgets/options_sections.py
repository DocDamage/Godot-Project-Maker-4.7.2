"""The sections of the Options page. Each one builds its widgets and shows or reads its values;
``rpggen.gui.models.options_model`` decides what they show, the page wires them together."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QCoreApplication, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rpggen.core import config as config_mod
from rpggen.core import (
    map_preview,
    options,
    room_plan,
    stage_plan,
    track_plan,
    wave_plan,
    world_plan,
)
from rpggen.gui import theme
from rpggen.gui.models.options_model import (
    ABILITY_LABELS,
    EXPORT_TARGET_LABELS,
    INPUT_COLUMNS,
    PACK_ART_LABELS,
    SEED_MAX,
    STARTER_COUNTS,
    STARTER_SIZE_NAMES,
    FeatureState,
    StarterState,
)
from rpggen.gui.widgets.areas_table import AreasTable, WorldPreview
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
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(QLabel(self.tr("Preset")))
        self.combo = QComboBox()
        self.combo.setObjectName("presetCombo")
        self.combo.setToolTip(
            self.tr(
                "Apply the options of a saved preset (packs, name and seed are not part of one)"
            )
        )
        self.combo.setMinimumWidth(160)
        header.addWidget(self.combo)
        self.save_button = QPushButton(self.tr("Save as preset…"))
        self.save_button.setObjectName("savePreset")
        self.save_button.setToolTip(self.tr("Keep the options below for your next project"))
        self.manage_button = QPushButton(self.tr("Manage…"))
        self.manage_button.setObjectName("managePresetsButton")
        self.manage_button.setToolTip(self.tr("Rename or delete saved presets"))
        header.addWidget(self.save_button)
        header.addWidget(self.manage_button)

    def fill(
        self, builtin: list[tuple[str, str]], user: list[tuple[str, str]] | None = None
    ) -> None:
        """The built-in presets first, then (after a separator) the user's: each ``(label,
        data)``, the data being what ``OptionsModel.apply_preset`` takes."""
        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItem(self.tr("Choose a preset…"), None)
        for label, data in builtin:
            self.combo.addItem(label, data)
        if user:
            self.combo.insertSeparator(self.combo.count())
            for label, data in user:
                self.combo.addItem(label, data)
        self.combo.blockSignals(False)


class FeatureGroups(QWidget):
    """A group box of check boxes per feature group, each with its sentence and, for a feature
    whose dependencies are off, what it needs."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.grid = QGridLayout(self)  # one card per group, side by side when there is room
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(theme.px("space_12"))
        self.groups: list[QGroupBox] = []
        self.columns = 0
        self.boxes: dict[str, QCheckBox] = {}
        self.needs: dict[str, QLabel] = {}
        self.descriptions: dict[str, QLabel] = {}
        self.hidden: set[str] = set()  # features this kind of game does not have
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
                description.setProperty("role", "caption")
                description.setContentsMargins(26, 0, 0, 4)
                needs = QLabel()
                needs.setObjectName(f"featureNeeds_{key}")
                needs.setProperty("state", "warning")
                needs.setContentsMargins(26, 0, 0, 2)
                needs.setVisible(False)
                self.boxes[key] = check
                self.needs[key] = needs
                self.descriptions[key] = description
                vbox.addWidget(check)
                vbox.addWidget(needs)
                vbox.addWidget(description)
            vbox.addStretch(1)
            self.groups.append(box)
        self.set_columns(1)

    def set_columns(self, columns: int) -> None:
        """Lay the group cards out in one column or in two (T15.14)."""
        if columns == self.columns:
            return
        self.columns = columns
        for box in self.groups:
            self.grid.removeWidget(box)
        for i, box in enumerate(self.groups):
            self.grid.addWidget(box, i // columns, i % columns)
        for column in range(2):
            self.grid.setColumnStretch(column, 1 if column < columns else 0)

    def set_hidden(self, keys: set[str]) -> None:
        """Features the chosen kind of game does not have (a metroidvania has no pathfinding):
        their check box, sentence and note are not shown."""
        self.hidden = set(keys)
        for key, box in self.boxes.items():
            shown = key not in self.hidden
            box.setVisible(shown)
            self.descriptions[key].setVisible(shown)
            if not shown:
                self.needs[key].setVisible(False)

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
            needs.setVisible(bool(state.needs) and key not in self.hidden)


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
        # a world of several areas (T13.20): the table, and the world as one tile per area
        self.areas = AreasTable()
        layout.addWidget(self.areas)
        self.world = WorldPreview()
        self.world.setVisible(False)
        layout.addWidget(self.world)
        self.reroll_area = QPushButton(self.tr("Rearrange this area"))
        self.reroll_area.setObjectName("rerollArea")
        self.reroll_area.setToolTip(
            self.tr("Another arrangement of the chosen area (before the first generation only)")
        )
        self.reroll_area.setVisible(False)
        layout.addWidget(self.reroll_area, 0, Qt.AlignmentFlag.AlignLeft)
        self.areas.edited.connect(self.edited)
        self.reroll_area.clicked.connect(self.reroll_chosen_area)
        self.world.areaChosen.connect(lambda _id: self._update_reroll())
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

    def load(
        self, values: dict[str, Any], locked: bool, world_names: set[str] | None = None
    ) -> None:
        """``world_names``: the names of the areas the project's world was built from (their
        rows are then fixed; None or empty while the project has no world yet)."""
        self.size_editor.set_value((int(values["size"][0]), int(values["size"][1])))
        for key, box in self.counts.items():
            box.setValue(int(values[key]))
        index = self.ground_combo.findData(values.get("ground", ""))
        self.ground_combo.setCurrentIndex(max(0, index))
        if locked:
            self.size_editor.setEnabled(False)
        self.areas.load(values.get("areas"), world_names)

    def values(self) -> dict[str, Any]:
        """The starter map options as the widgets show them (``areas`` only for a world)."""
        out: dict[str, Any] = {
            "size": list(self.size_editor.value()),
            "ground": self.ground_combo.currentData() or "",
        }
        for key, box in self.counts.items():
            out[key] = box.value()
        areas = self.areas.areas()
        if areas:
            out["areas"] = areas
        return out

    def show_world(self, plan: dict[str, Any] | None) -> None:
        """The planned world under the table (None hides it: no world, or a table with a
        problem)."""
        self.world.set_plan(plan)
        self.world.setVisible(plan is not None)
        self._update_reroll()

    def _update_reroll(self) -> None:
        chosen = self.world.chosen
        can = (
            self.world.plan is not None
            and not self.areas.locked_names
            and chosen not in ("", world_plan.VILLAGE_ID)
        )
        self.reroll_area.setVisible(self.world.plan is not None)
        self.reroll_area.setEnabled(can)

    def reroll_chosen_area(self) -> bool:
        """Another arrangement of the area chosen in the world preview (one undo step of the
        table). False for the village, and once the world exists."""
        plan = self.world.plan
        area = world_plan.area_of(plan, self.world.chosen) if plan else None
        if area is None or area["id"] == world_plan.VILLAGE_ID or self.areas.locked_names:
            return False
        for row, values in enumerate(self.areas.rows()):
            if world_plan.slug(values["name"]) == world_plan.slug(area["name"]):
                return self.areas.set_value(row, "reroll", int(values.get("reroll", 0)) + 1)
        return False

    def show_state(self, state: StarterState) -> None:
        for widget in (self.size_editor, self.ground_combo, self.reset, *self.counts.values()):
            widget.setEnabled(state.layout_enabled)
        self.note.setText(state.note)
        self.note.setVisible(state.note_visible)
        if state.note_visible:
            self.preview.set_disabled(state.note)


class StarterWorldBox(QGroupBox):
    """The starter world of a metroidvania (T14.10): how many rooms, how large, which abilities,
    how many enemies and pickups, the side-view preview of the plan, and the rooms added to a
    world that exists. The number of rooms can never be below what the abilities need."""

    edited = Signal()
    PREVIEW_HEIGHT = 150

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setTitle(self.tr("Starter world"))
        self.setObjectName("starterWorld")
        self._loading = False
        self.plan: dict[str, Any] | None = None
        layout = QVBoxLayout(self)
        self.note = QLabel()
        self.note.setObjectName("worldNote")
        self.note.setWordWrap(True)
        self.note.setProperty("state", "warning")
        self.note.setVisible(False)
        layout.addWidget(self.note)

        numbers = QHBoxLayout()
        self.rooms = spin(room_plan.MIN_ROOMS, room_plan.MAX_ROOMS)
        self.rooms.setObjectName("world_rooms")
        (low_w, high_w), (low_h, high_h) = room_plan.SIZE_RANGE
        self.room_width = spin(low_w, high_w)
        self.room_width.setObjectName("world_room_width")
        self.room_width.setToolTip(
            self.tr("Width of a room in tiles ({0} to {1})").format(low_w, high_w)
        )
        self.room_height = spin(low_h, high_h)
        self.room_height.setObjectName("world_room_height")
        self.room_height.setToolTip(
            self.tr("Height of a room in tiles ({0} to {1})").format(low_h, high_h)
        )
        self.enemies = spin(*room_plan.ENEMY_RANGE)
        self.enemies.setObjectName("world_enemies")
        self.enemies.setToolTip(self.tr("Enemies in a room that has enemies"))
        self.pickups = spin(*room_plan.PICKUP_RANGE)
        self.pickups.setObjectName("world_pickups")
        self.pickups.setToolTip(self.tr("Potions and coins in the whole world"))
        for label, box in (
            ("Rooms", self.rooms),
            ("Room width", self.room_width),
            ("Room height", self.room_height),
            ("Enemies", self.enemies),
            ("Pickups", self.pickups),
        ):
            column = QVBoxLayout()
            column.addWidget(QLabel(self.tr(label)))
            column.addWidget(box)
            numbers.addLayout(column)
        layout.addLayout(numbers)

        layout.addWidget(QLabel(self.tr("Abilities (found in this order)")))
        from rpggen.gui.widgets.flow_layout import FlowLayout

        ability_box = QWidget()
        ability_flow = FlowLayout(ability_box)
        ability_flow.setContentsMargins(0, 0, 0, 0)
        self.abilities: dict[str, QCheckBox] = {}
        for key in room_plan.ABILITIES:
            check = QCheckBox(self.tr(ABILITY_LABELS[key]))
            check.setObjectName(f"world_ability_{key}")
            self.abilities[key] = check
            ability_flow.addWidget(check)
        layout.addWidget(ability_box)
        self.bound = _muted("", "worldBound")
        layout.addWidget(self.bound)
        self.reset = reset_button("resetWorld")
        layout.addWidget(self.reset, 0, Qt.AlignmentFlag.AlignRight)

        self.preview = QLabel()
        self.preview.setObjectName("worldPreview")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(self.PREVIEW_HEIGHT)
        self.preview.setAccessibleName(self.tr("The planned rooms, seen from the side"))
        layout.addWidget(self.preview)
        self.summary = _muted("", "worldSummary")
        layout.addWidget(self.summary)

        layout.addWidget(QLabel(self.tr("Added rooms")))
        self.added = QTableWidget(0, 2)
        self.added.setObjectName("addedRooms")
        self.added.setHorizontalHeaderLabels([self.tr("Name"), self.tr("Beside the room")])
        self.added.horizontalHeader().setStretchLastSection(True)
        self.added.verticalHeader().setVisible(False)
        self.added.setMinimumHeight(84)
        self.added.setMaximumHeight(140)
        self.added.setToolTip(
            self.tr('A room with this name is built beside the room you name ("Room 6")')
        )
        layout.addWidget(self.added)
        buttons = QHBoxLayout()
        self.add_room = QPushButton(self.tr("Add a room"))
        self.add_room.setObjectName("addRoom")
        self.remove_room = QPushButton(self.tr("Remove"))
        self.remove_room.setObjectName("removeRoom")
        buttons.addWidget(self.add_room)
        buttons.addWidget(self.remove_room)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        for box in (self.rooms, self.room_width, self.room_height, self.enemies, self.pickups):
            box.valueChanged.connect(self._changed)
        for check in self.abilities.values():
            check.toggled.connect(self._on_ability)
        self.added.itemChanged.connect(self._changed)
        self.added.itemSelectionChanged.connect(self._update_buttons)
        self.add_room.clicked.connect(self.add_row)
        self.remove_room.clicked.connect(self.remove_row)
        self._locked_rows = 0
        self._update_bound()
        self._update_buttons()

    # ------------------------------------------------------------------ values

    def chosen_abilities(self) -> list[str]:
        return [key for key, check in self.abilities.items() if check.isChecked()]

    def values(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "rooms": self.rooms.value(),
            "room_size": [self.room_width.value(), self.room_height.value()],
            "abilities": self.chosen_abilities(),
            "enemies": self.enemies.value(),
            "pickups": self.pickups.value(),
        }
        rows = self.added_rows()
        if rows:
            out["added_rooms"] = rows
        return out

    def added_rows(self) -> list[dict[str, str]]:
        rows = []
        for row in range(self.added.rowCount()):
            name = self.added.item(row, 0)
            join = self.added.item(row, 1)
            text = name.text().strip() if name else ""
            if text:
                rows.append({"name": text, "join": join.text().strip() if join else ""})
        return rows

    def load(self, values: dict[str, Any], locked_rows: int = 0) -> None:
        """``locked_rows``: how many of the added rooms are built already (their rows stay)."""
        self._loading = True
        try:
            chosen = list(values.get("abilities", []))
            for key, check in self.abilities.items():
                check.setChecked(key in chosen)
            self._update_bound()
            self.rooms.setValue(int(values["rooms"]))
            self.room_width.setValue(int(values["room_size"][0]))
            self.room_height.setValue(int(values["room_size"][1]))
            self.enemies.setValue(int(values["enemies"]))
            self.pickups.setValue(int(values["pickups"]))
            self.added.setRowCount(0)
            for row in values.get("added_rooms", []) or []:
                self._append(str(row.get("name", "")), str(row.get("join", "")))
            self._locked_rows = min(locked_rows, self.added.rowCount())
            for row in range(self._locked_rows):
                for col in range(2):
                    item = self.added.item(row, col)
                    if item is not None:
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        finally:
            self._loading = False
        self._update_buttons()

    # ------------------------------------------------------------------ the bound

    def _update_bound(self) -> None:
        """rooms >= abilities + 3, live: the spin box cannot go below it."""
        need = room_plan.min_rooms(self.chosen_abilities())
        self.rooms.setMinimum(need)
        count = len(self.chosen_abilities())
        self.rooms.setToolTip(
            self.tr("Rooms of the world ({0} to {1})").format(need, room_plan.MAX_ROOMS)
        )
        self.bound.setText(
            self.tr("{0} abilities need at least {1} rooms.").format(count, need)
            if count != 1
            else self.tr("1 ability needs at least {0} rooms.").format(need)
        )

    def _on_ability(self, *_args: object) -> None:
        self._update_bound()
        self._changed()

    def _changed(self, *_args: object) -> None:
        if not self._loading:
            self.edited.emit()

    # ------------------------------------------------------------------ added rooms

    def _append(self, name: str, join: str) -> None:
        row = self.added.rowCount()
        self.added.blockSignals(True)
        self.added.insertRow(row)
        self.added.setItem(row, 0, QTableWidgetItem(name))
        self.added.setItem(row, 1, QTableWidgetItem(join))
        self.added.blockSignals(False)

    def add_row(self, name: str = "", join: str = "") -> bool:
        """A new row (named "Room N" beside the last room when nothing is given)."""
        if self.added.rowCount() >= room_plan.MAX_ADDED:
            return False
        if not isinstance(name, str) or not name:
            taken = {row["name"] for row in self.added_rows()}
            number = self.rooms.value() + self.added.rowCount() + 1
            while f"Room {number}" in taken:
                number += 1
            name = f"Room {number}"
        if not join:
            last = (self.plan or {}).get("list") or []
            join = str(last[-1]["name"]) if last else f"Room {self.rooms.value()}"
        self._append(name, join)
        self._update_buttons()
        self._changed()
        return True

    def remove_row(self) -> bool:
        """Removes the chosen row (the last one when none is chosen); a built room stays."""
        row = self.added.currentRow()
        if row < 0:
            row = self.added.rowCount() - 1
        if row < self._locked_rows or row < 0:
            return False
        self.added.removeRow(row)
        self._update_buttons()
        self._changed()
        return True

    def _update_buttons(self) -> None:
        self.add_room.setEnabled(self.added.rowCount() < room_plan.MAX_ADDED)
        self.remove_room.setEnabled(self.added.rowCount() > self._locked_rows)

    # ------------------------------------------------------------------ preview and state

    def show_plan(self, rooms: dict[str, Any] | None, error: str = "") -> None:
        """The plan as the side-view picture (one cell per room), or why there is none."""
        self.plan = rooms
        if rooms is None:
            self.preview.setPixmap(QPixmap())
            self.preview.setText(error or self.tr("No preview"))
            self.summary.setText("")
            return
        picture = map_preview.render_world(rooms, scale=2).convert("RGBA")
        image = QImage(
            picture.tobytes(), picture.width, picture.height, QImage.Format.Format_RGBA8888
        ).copy()
        pixmap = QPixmap.fromImage(image)
        room = max(40, self.preview.width() - 8)
        if pixmap.width() > room or pixmap.height() > self.PREVIEW_HEIGHT:
            pixmap = pixmap.scaled(
                room,
                self.PREVIEW_HEIGHT,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
        self.preview.setText("")
        self.preview.setPixmap(pixmap)
        self.summary.setText(room_plan.summary(rooms))

    def show_state(self, state: StarterState) -> None:
        for widget in (
            self.rooms,
            self.room_width,
            self.room_height,
            self.enemies,
            self.pickups,
            self.reset,
            *self.abilities.values(),
        ):
            widget.setEnabled(state.layout_enabled)
        self.note.setText(state.note)
        self.note.setVisible(state.note_visible)


# ----------------------------------------------------------------------- the arcade kinds (T16.16)

Rgb = tuple[int, int, int]
# a field of an arcade box: ("spin", key, label, tooltip, (low, high)), ("combo", key, label,
# tooltip, ((value, label), ...)) or ("check", key, label, tooltip, None)
Field = tuple[str, str, str, str, Any]
DIFFICULTY_CHOICES = (("easy", "Easy"), ("normal", "Normal"), ("hard", "Hard"))
LENGTH_CHOICES = (("short", "Short"), ("medium", "Medium"), ("long", "Long"))


class LegendDot(QWidget):
    """A dot of a picture's own colour, for its legend (painted: no style sheet has a data
    colour)."""

    def __init__(self, colour: QColor, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.colour = colour
        self.setFixedSize(10, 10)

    def paintEvent(self, event) -> None:  # noqa: ANN001, N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QColor(0, 0, 0))
        painter.setBrush(self.colour)
        painter.drawEllipse(self.rect().adjusted(0, 0, -1, -1))
        painter.end()


class ArcadeBox(QGroupBox):
    """What the three arcade kinds share on the Options page: the kind's options as spin boxes,
    combos and check boxes, a preview drawn from the plan with a legend of what its marks are,
    the plan in words, and the table of the stages (or tracks) added to a game that exists."""

    edited = Signal()
    PREVIEW_HEIGHT = 150
    PREFIX = ""  # of the widgets' object names: "shmup_stages"
    KIND = ""
    FIELDS: tuple[Field, ...] = ()
    ADDED_KEY = "added_stages"
    ADDED_NOUN = "Stage"  # a new row is "Stage 4"
    COUNT_KEY = "stages"
    LEGEND: tuple[tuple[str, str, Rgb], ...] = ()  # (key, name, colour)
    MAX_ADDED = 8

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from rpggen.gui.widgets.flow_layout import FlowLayout

        self._loading = False
        self._locked_rows = 0
        self.plan: dict[str, Any] | None = None
        self._pixmap = QPixmap()
        layout = QVBoxLayout(self)
        self.note = QLabel()
        self.note.setObjectName(f"{self.PREFIX}Note")
        self.note.setWordWrap(True)
        self.note.setProperty("state", "warning")
        self.note.setVisible(False)
        layout.addWidget(self.note)

        self.spins: dict[str, QSpinBox] = {}
        self.combos: dict[str, QComboBox] = {}
        self.checks: dict[str, QCheckBox] = {}
        number_box = QWidget()
        numbers = FlowLayout(number_box, spacing=theme.px("space_12"))
        check_box = QWidget()
        checks = FlowLayout(check_box, spacing=theme.px("space_12"))
        for kind, key, label, tooltip, extra in self.FIELDS:
            name = f"{self.PREFIX}_{key}"
            if kind == "check":
                check = QCheckBox(self.tr(label))
                check.setObjectName(name)
                check.setToolTip(self.tr(tooltip))
                check.toggled.connect(self._changed)
                self.checks[key] = check
                checks.addWidget(check)
                continue
            widget: QWidget
            if kind == "spin":
                low, high = extra
                box = spin(low, high)
                box.setToolTip(self.tr("{0} ({1} to {2})").format(self.tr(tooltip), low, high))
                box.valueChanged.connect(self._changed)
                self.spins[key] = box
                widget = box
            else:
                combo = QComboBox()
                for value, text in extra:
                    combo.addItem(self.tr(text), value)
                combo.setToolTip(self.tr(tooltip))
                combo.currentIndexChanged.connect(self._changed)
                self.combos[key] = combo
                widget = combo
            widget.setObjectName(name)
            holder = QWidget()
            column = QVBoxLayout(holder)
            column.setContentsMargins(0, 0, 0, 0)
            column.setSpacing(2)
            column.addWidget(QLabel(self.tr(label)))
            column.addWidget(widget)
            numbers.addWidget(holder)
        layout.addWidget(number_box)
        layout.addWidget(check_box)
        self.reset = reset_button(f"reset_{self.PREFIX}")
        layout.addWidget(self.reset, 0, Qt.AlignmentFlag.AlignRight)

        self.preview = QLabel()
        self.preview.setObjectName(f"{self.PREFIX}Preview")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(self.PREVIEW_HEIGHT)
        self.preview.setWordWrap(True)
        layout.addWidget(self.preview)
        self.legend_box = QWidget()
        self.legend_box.setObjectName(f"{self.PREFIX}Legend")
        legend = FlowLayout(self.legend_box, spacing=10)
        self.legend_labels: dict[str, QLabel] = {}
        self.legend_items: dict[str, QWidget] = {}
        for key, text, (r, g, b) in self.LEGEND:
            item = QWidget()
            row = QHBoxLayout(item)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(4)
            dot = LegendDot(QColor(r, g, b))  # the mark's colour, from the picture's table
            label = QLabel(self.tr(text))
            label.setObjectName(f"{self.PREFIX}Legend_{key}")
            row.addWidget(dot)
            row.addWidget(label)
            legend.addWidget(item)
            self.legend_labels[key] = label
            self.legend_items[key] = item
        layout.addWidget(self.legend_box)
        self.summary = _muted("", f"{self.PREFIX}Summary")
        layout.addWidget(self.summary)

        self.added_label = QLabel()
        layout.addWidget(self.added_label)
        self.added = QTableWidget(0, 1)
        self.added.setObjectName(f"{self.PREFIX}Added")
        self.added.setHorizontalHeaderLabels([self.tr("Name")])
        self.added.horizontalHeader().setStretchLastSection(True)
        self.added.verticalHeader().setVisible(False)
        self.added.setMinimumHeight(84)
        self.added.setMaximumHeight(140)
        layout.addWidget(self.added)
        buttons = QHBoxLayout()
        self.add_button = QPushButton()
        self.add_button.setObjectName(f"{self.PREFIX}Add")
        self.remove_button = QPushButton(self.tr("Remove"))
        self.remove_button.setObjectName(f"{self.PREFIX}Remove")
        buttons.addWidget(self.add_button)
        buttons.addWidget(self.remove_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self.added.itemChanged.connect(self._changed)
        self.added.itemSelectionChanged.connect(self._update_buttons)
        self.add_button.clicked.connect(self.add_row)
        self.remove_button.clicked.connect(self.remove_row)
        self._update_buttons()

    # ------------------------------------------------------------------ values

    def values(self) -> dict[str, Any]:
        out: dict[str, Any] = {key: box.value() for key, box in self.spins.items()}
        out.update({key: combo.currentData() for key, combo in self.combos.items()})
        out.update({key: check.isChecked() for key, check in self.checks.items()})
        out[self.ADDED_KEY] = self.added_rows()
        return out

    def added_rows(self) -> list[dict[str, str]]:
        rows = []
        for row in range(self.added.rowCount()):
            item = self.added.item(row, 0)
            text = item.text().strip() if item else ""
            if text:
                rows.append({"name": text})
        return rows

    def load(self, values: dict[str, Any], locked_rows: int = 0) -> None:
        """``locked_rows``: how many of the added rows the game already has (they stay)."""
        self._loading = True
        try:
            for key, box in self.spins.items():
                box.setValue(int(values[key]))
            for key, combo in self.combos.items():
                combo.setCurrentIndex(max(0, combo.findData(values[key])))
            for key, check in self.checks.items():
                check.setChecked(bool(values[key]))
            self.added.setRowCount(0)
            for row in values.get(self.ADDED_KEY, []) or []:
                self._append(str(row.get("name", "")))
            self._locked_rows = min(locked_rows, self.added.rowCount())
            for row in range(self._locked_rows):
                item = self.added.item(row, 0)
                if item is not None:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.sync()
        finally:
            self._loading = False
        self._update_buttons()

    def sync(self) -> None:
        """What one option does to another (a kind's own rule); nothing here."""

    def _changed(self, *_args: object) -> None:
        if self._loading:
            return
        self._loading = True  # a rule may move another widget: one signal for the lot
        try:
            self.sync()
        finally:
            self._loading = False
        self.edited.emit()

    # ------------------------------------------------------------------ added rows

    def _append(self, name: str) -> None:
        row = self.added.rowCount()
        self.added.blockSignals(True)
        self.added.insertRow(row)
        self.added.setItem(row, 0, QTableWidgetItem(name))
        self.added.blockSignals(False)

    def add_row(self, name: str = "") -> bool:
        """A new row (named "Stage N" after the last when nothing is given)."""
        if self.added.rowCount() >= self.MAX_ADDED:
            return False
        if not isinstance(name, str) or not name:
            taken = {row["name"] for row in self.added_rows()}
            number = self.spins[self.COUNT_KEY].value() + self.added.rowCount() + 1
            while f"{self.ADDED_NOUN} {number}" in taken:
                number += 1
            name = f"{self.ADDED_NOUN} {number}"
        self._append(name)
        self._update_buttons()
        self._changed()
        return True

    def remove_row(self) -> bool:
        """Removes the chosen row (the last one when none is chosen); one that is built stays."""
        row = self.added.currentRow()
        if row < 0:
            row = self.added.rowCount() - 1
        if row < self._locked_rows or row < 0:
            return False
        self.added.removeRow(row)
        self._update_buttons()
        self._changed()
        return True

    def _update_buttons(self) -> None:
        self.add_button.setEnabled(self.added.rowCount() < self.MAX_ADDED)
        self.remove_button.setEnabled(self.added.rowCount() > self._locked_rows)

    # ------------------------------------------------------------------ preview and state

    def picture(self, stages: dict[str, Any]):  # noqa: ANN201 - a PIL image
        raise NotImplementedError

    def words(self, stages: dict[str, Any]) -> str:
        raise NotImplementedError

    def show_plan(self, stages: dict[str, Any] | None, error: str = "") -> None:
        """The plan as its picture, or why there is none."""
        self.plan = stages
        if stages is None:
            self._pixmap = QPixmap()
            self.preview.setPixmap(QPixmap())
            self.preview.setText(error or self.tr("No preview"))
            self.summary.setText("")
            return
        picture = self.picture(stages).convert("RGBA")
        image = QImage(
            picture.tobytes(), picture.width, picture.height, QImage.Format.Format_RGBA8888
        ).copy()
        self._pixmap = QPixmap.fromImage(image)
        self.preview.setText("")
        self._fit()
        self.summary.setText(self.words(stages))

    def _fit(self) -> None:
        if self._pixmap.isNull():
            return
        room = max(40, self.preview.width() - 8)
        pixmap = self._pixmap
        if pixmap.width() > room or pixmap.height() > self.PREVIEW_HEIGHT:
            pixmap = pixmap.scaled(
                room,
                self.PREVIEW_HEIGHT,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
        self.preview.setPixmap(pixmap)

    def resizeEvent(self, event) -> None:  # noqa: ANN001, N802 - Qt override
        super().resizeEvent(event)
        self._fit()

    def show_state(self, state: StarterState) -> None:
        for widget in (*self.spins.values(), *self.combos.values(), *self.checks.values()):
            widget.setEnabled(state.layout_enabled)
        self.reset.setEnabled(state.layout_enabled)
        self.note.setText(state.note)
        self.note.setVisible(state.note_visible)
        if state.layout_enabled:
            self._loading = True
            try:
                self.sync()  # a rule's own disabled widget stays disabled
            finally:
                self._loading = False


class ShmupBox(ArcadeBox):
    """The stages of a shoot 'em up (T16.06) and its wave chart."""

    PREFIX = "shmup"
    KIND = "shmup"
    FIELDS = (
        (
            "combo",
            "orientation",
            "Scrolls",
            "The way the stages scroll: up the screen or to the right",
            (("vertical", "Up (vertical)"), ("horizontal", "Right (horizontal)")),
        ),
        ("spin", "stages", "Stages", "Stages of the run", wave_plan.STAGE_RANGE),
        ("combo", "length", "Length", "How long a stage is", LENGTH_CHOICES),
        ("spin", "lives", "Lives", "Ships at the start of a run", wave_plan.LIVES_RANGE),
        ("spin", "bombs", "Bombs", "Bombs of every ship", wave_plan.BOMBS_RANGE),
        (
            "combo",
            "difficulty",
            "Difficulty",
            "How fast and how many the enemy's bullets are",
            DIFFICULTY_CHOICES,
        ),
        ("check", "auto_fire", "Auto-fire", "The ship fires while the button is held", None),
    )
    LEGEND = (
        ("popcorn", "formation", map_preview.WAVE_COLORS["popcorn"]),
        ("turret", "turrets", map_preview.WAVE_COLORS["turret"]),
        ("asteroid", "asteroids", map_preview.WAVE_COLORS["asteroid"]),
        ("carrier", "power-up carrier", map_preview.WAVE_COLORS["carrier"]),
        ("boss", "boss", map_preview.WAVE_BOSS),
    )
    MAX_ADDED = wave_plan.MAX_ADDED

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setTitle(self.tr("Stages"))
        self.setObjectName("shmupBox")
        self.added_label.setText(self.tr("Added stages"))
        self.add_button.setText(self.tr("Add a stage"))
        self.added.setToolTip(self.tr("A stage with this name is planned after the last one"))
        self.preview.setAccessibleName(
            self.tr("The waves of every stage: a column a stage, the boss at the top")
        )

    def picture(self, stages: dict[str, Any]):  # noqa: ANN201
        return map_preview.render_waves(stages, scale=2)

    def words(self, stages: dict[str, Any]) -> str:
        return wave_plan.summary(stages)


class RunAndGunBox(ArcadeBox):
    """The stages of a run and gun (T16.10), the grapple (T16.11) and its stage strip."""

    PREFIX = "gun"
    KIND = "run_and_gun"
    PREVIEW_HEIGHT = 170
    FIELDS = (
        ("spin", "stages", "Stages", "Stages of the run", stage_plan.STAGE_RANGE),
        ("combo", "length", "Length", "How long a stage is", LENGTH_CHOICES),
        ("spin", "lives", "Lives", "Soldiers at the start of a run", stage_plan.LIVES_RANGE),
        ("spin", "health", "Health", "Hits a soldier takes", stage_plan.HEALTH_RANGE),
        (
            "combo",
            "difficulty",
            "Difficulty",
            "How fast and how many the enemy's bullets are",
            DIFFICULTY_CHOICES,
        ),
        ("check", "keep_weapon", "Keep the weapon", "A weapon survives the soldier's death", None),
        (
            "check",
            "left_edge_kills",
            "The left edge kills",
            "The screen never scrolls back: what it leaves behind is lost",
            None,
        ),
        ("check", "grapple", "Grapple arm", "An arm that swings and hoists the soldier", None),
        ("check", "jump", "Jump", "Off only with the grapple: the arm is the way up", None),
    )
    LEGEND = (
        ("start", "start", map_preview.STRIP_MARKERS["start"]),
        ("enemy", "enemies", map_preview.STRIP_MARKERS["enemy"]),
        ("pickup", "weapon", map_preview.STRIP_MARKERS["pickup"]),
        ("boss", "boss arena", map_preview.STRIP_MARKERS["boss"]),
        ("grapple", "grapple point", map_preview.STRIP_MARKERS["grapple"]),
    )
    MAX_ADDED = stage_plan.MAX_ADDED

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setTitle(self.tr("Stages"))
        self.setObjectName("runAndGunBox")
        self.added_label.setText(self.tr("Added stages"))
        self.add_button.setText(self.tr("Add a stage"))
        self.added.setToolTip(self.tr("A stage with this name is planned after the last one"))
        self.preview.setAccessibleName(
            self.tr("Every stage seen from the side: its chunks, its enemies and the boss arena")
        )
        self.sync()

    def sync(self) -> None:
        """A soldier without the arm jumps: the box cannot be cleared then."""
        grapple, jump = self.checks["grapple"], self.checks["jump"]
        if not grapple.isChecked():
            jump.setChecked(True)
        jump.setEnabled(grapple.isChecked() and grapple.isEnabled())

    def picture(self, stages: dict[str, Any]):  # noqa: ANN201
        return map_preview.render_stage_strip(stages, scale=2)

    def words(self, stages: dict[str, Any]) -> str:
        return stage_plan.summary(stages)

    def show_plan(self, stages: dict[str, Any] | None, error: str = "") -> None:
        super().show_plan(stages, error)
        # the points the arm holds on to are drawn for a soldier that does not jump
        self.legend_items["grapple"].setVisible(bool(stages) and not stages.get("jump", True))


class RacingBox(ArcadeBox):
    """The tracks of a racing game (T16.13 to T16.15) and its loops."""

    PREFIX = "race"
    KIND = "racing"
    ADDED_KEY = "added_tracks"
    ADDED_NOUN = "Track"
    COUNT_KEY = "tracks"
    FIELDS = (
        ("spin", "tracks", "Tracks", "Tracks of the championship", track_plan.TRACK_RANGE),
        ("spin", "laps", "Laps", "Laps of every race", track_plan.LAP_RANGE),
        (
            "combo",
            "track_size",
            "Track size",
            "How much ground a track covers",
            (("small", "Small"), ("medium", "Medium"), ("large", "Large")),
        ),
        ("combo", "difficulty", "Difficulty", "How many turns and hazards", DIFFICULTY_CHOICES),
        (
            "combo",
            "steering",
            "Steering",
            "Relative: left and right turn the car. Absolute: the car heads where you point",
            (("relative", "Relative"), ("absolute", "Absolute")),
        ),
        (
            "combo",
            "camera",
            "Camera",
            "Follow the car, or show the whole track",
            (("follow", "Follows the car"), ("fixed", "The whole track")),
        ),
        ("spin", "rivals", "Rivals", "Cars you race against", track_plan.RIVALS),
        ("check", "rubber_band", "Rubber-banding", "Rivals far behind catch up a little", None),
        ("check", "elimination", "Elimination", "Who is last twice is out", None),
    )
    LEGEND = (
        ("start", "start", map_preview.TRACK_CAR),
        ("checkpoint", "checkpoint", map_preview.TRACK_CHECKPOINT),
        ("pickup", "pickup", map_preview.TRACK_PICKUP),
        ("boost", "boost arrow", map_preview.TRACK_COLORS["b"]),
        ("oil", "oil", map_preview.TRACK_COLORS["o"]),
        ("dirt", "dirt", map_preview.TRACK_COLORS["d"]),
    )
    MAX_ADDED = track_plan.MAX_ADDED

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setTitle(self.tr("Tracks"))
        self.setObjectName("racingBox")
        self.added_label.setText(self.tr("Added tracks"))
        self.add_button.setText(self.tr("Add a track"))
        self.added.setToolTip(self.tr("A track with this name is planned after the last one"))
        self.preview.setAccessibleName(
            self.tr("Every track from above: the loop, its checkpoints and its pickups")
        )

    def picture(self, stages: dict[str, Any]):  # noqa: ANN201
        return map_preview.render_tracks(stages, scale=3)

    def words(self, stages: dict[str, Any]) -> str:
        return track_plan.summary(stages)


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

    fixed = False

    def set_fixed(self, fixed: bool) -> None:
        """The layers of a metroidvania's rooms are what the rooms are built from: they are
        shown, back to front, and cannot be changed."""
        self.fixed = fixed
        self.list.setDragDropMode(
            QAbstractItemView.DragDropMode.NoDragDrop
            if fixed
            else QAbstractItemView.DragDropMode.InternalMove
        )
        self.list.setToolTip(
            self.tr("The layers of every room, back to front.")
            if fixed
            else self.tr("Map layers, back to front. Drag to reorder.")
        )
        for widget in (self.name, self.add_button, self.reset):
            widget.setEnabled(not fixed)
        self.update_buttons()

    def update_buttons(self) -> None:
        item = self.list.currentItem()
        row = self.list.currentRow()
        free = not self.fixed
        self.remove_button.setEnabled(free and item is not None and item.text() != "Ground")
        self.up_button.setEnabled(free and row > 0)
        self.down_button.setEnabled(free and 0 <= row < self.list.count() - 1)

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
        # a card whose heading row is the header that opens it (T15.14)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        pad = theme.px("space_12")
        self.layout().setContentsMargins(pad, pad, pad, pad)  # type: ignore[union-attr]
        body = QVBoxLayout(self.body)
        body.setContentsMargins(theme.px("space_4"), theme.px("space_8"), 0, 0)
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
        self.repair_box = QCheckBox(self.tr("Repair generated maps after a build"))
        self.repair_box.setObjectName("repairWorld")
        self.repair_box.setToolTip(
            self.tr(
                "When a door leads nowhere or a map cannot be reached, rpggen mends the maps it "
                "made and nobody changed (they are backed up first). A map you changed is only "
                "mended when you ask on the Results page."
            )
        )
        body.addWidget(self.repair_box)
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
