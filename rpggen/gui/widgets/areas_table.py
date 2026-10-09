"""The *Areas* of the Starter map box (T13.20): the table of a world's areas and its preview.

``AreasTable`` edits ``starter_map.areas`` (add, remove, reorder; name, biome, size, enemies,
chests) with an undo of its own. Once the project has its world, the rows it was built from are
shown but cannot be changed; a new row may still be added and says which area it is joined to.
``WorldPreview`` draws the planned world as one tile per area with the doors between them; a click
chooses an area, which is then drawn cell by cell.
"""

from __future__ import annotations

import copy
from typing import Any

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QKeySequence, QMouseEvent, QPainter, QPaintEvent, QPen, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rpggen.core import world_plan

BIOME_LABELS = {
    "village": "Village",
    "field": "Field",
    "forest": "Forest",
    "cave": "Cave",
    "shore": "Shore",
}
BIOME_COLORS = {
    "village": "#c9a96a",
    "field": "#8fbf6a",
    "forest": "#3f7d45",
    "cave": "#7b7b86",
    "shore": "#5f9fc9",
}
WORLD_EXISTS_TEXT = (
    "This project has its world already; add areas in Godot or delete "
    "game/maps/<area>.tscn to rebuild it."
)
COLUMNS = ("Name", "Biome", "Width", "Height", "Enemies", "Chests", "Joined to")
NAME, BIOME, WIDTH, HEIGHT, ENEMIES, CHESTS, JOIN = range(7)


class AreasTable(QWidget):
    """``starter_map.areas`` as a table. ``areas()`` is None while the box *Make a world of
    several areas* is off: the project then gets today's starter map and field."""

    edited = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("areasTable")
        self.locked_names: set[str] = set()  # the rows the existing world was built from
        self._rows: list[dict[str, Any]] = []
        self._history: list[tuple[bool, list[dict[str, Any]]]] = []
        self._loading = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.enable_box = QCheckBox(self.tr("Make a world of several areas"))
        self.enable_box.setObjectName("areasEnabled")
        self.enable_box.setToolTip(
            self.tr(
                "Off: the starter map and one field, as before. On: one map per row, joined by "
                "doors, with a key before the gate that closes the first cave."
            )
        )
        layout.addWidget(self.enable_box)
        self.note = QLabel(self.tr(WORLD_EXISTS_TEXT))
        self.note.setObjectName("areasNote")
        self.note.setWordWrap(True)
        self.note.setProperty("state", "warning")
        self.note.setVisible(False)
        layout.addWidget(self.note)
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setObjectName("areasRows")
        self.table.setHorizontalHeaderLabels([self.tr(c) for c in COLUMNS])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(NAME, QHeaderView.ResizeMode.Stretch)
        header.setMinimumSectionSize(40)
        for column, width in ((BIOME, 92), (WIDTH, 62), (HEIGHT, 62), (ENEMIES, 64), (CHESTS, 62)):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(column, width)
        header.setSectionResizeMode(JOIN, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(JOIN, 92)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setMinimumHeight(150)
        layout.addWidget(self.table)
        buttons = QHBoxLayout()
        self.add_button = self._button("areasAdd", self.tr("Add"), self.tr("Add an area"))
        self.remove_button = self._button(
            "areasRemove", self.tr("Remove"), self.tr("Remove the selected area")
        )
        self.up_button = self._button("areasUp", self.tr("Up"), self.tr("Move the area up"))
        self.down_button = self._button("areasDown", self.tr("Down"), self.tr("Move the area down"))
        self.undo_button = self._button(
            "areasUndo", self.tr("Undo"), self.tr("Take back the last change to the table (Ctrl+Z)")
        )
        for button in (
            self.add_button,
            self.remove_button,
            self.up_button,
            self.down_button,
            self.undo_button,
        ):
            buttons.addWidget(button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self.error = QLabel()
        self.error.setObjectName("areasError")
        self.error.setProperty("role", "error")
        self.error.setWordWrap(True)
        self.error.setVisible(False)
        layout.addWidget(self.error)
        shortcut = QShortcut(QKeySequence.StandardKey.Undo, self.table)
        shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        shortcut.activated.connect(self.undo)
        self.enable_box.toggled.connect(self._on_enabled)
        self.add_button.clicked.connect(lambda: self.add_row())
        self.remove_button.clicked.connect(lambda: self.remove_row(self.table.currentRow()))
        self.up_button.clicked.connect(lambda: self.move_row(self.table.currentRow(), -1))
        self.down_button.clicked.connect(lambda: self.move_row(self.table.currentRow(), 1))
        self.undo_button.clicked.connect(self.undo)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.currentCellChanged.connect(lambda *_a: self._update_buttons())
        self._rebuild()

    def _button(self, name: str, text: str, tip: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName(name)
        button.setToolTip(tip)
        return button

    # ------------------------------------------------------------------ data

    def load(
        self, areas: list[dict[str, Any]] | None, locked_names: set[str] | None = None
    ) -> None:
        """Show a table (None: the box is off). ``locked_names`` are the names of the areas the
        project's world was built from: those rows cannot be changed any more."""
        self.locked_names = {world_plan.slug(n) for n in (locked_names or set())}
        self._rows = copy.deepcopy(areas) if areas else []
        self._history.clear()
        self._loading = True
        self.enable_box.setChecked(bool(areas))
        self._loading = False
        self._rebuild()

    def enabled(self) -> bool:
        return self.enable_box.isChecked()

    def rows(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self._rows)

    def areas(self) -> list[dict[str, Any]] | None:
        """What the config stores: the rows, or None when the world is off or the table is
        not valid (``problem()`` says why)."""
        if not self.enabled() or self.problem():
            return None
        return world_plan.normalized(self._rows)

    def problem(self) -> str:
        if not self.enabled():
            return ""
        try:
            world_plan.normalized(self._rows)
        except world_plan.WorldPlanError as exc:
            return str(exc)
        return ""

    def is_locked(self, row: int) -> bool:
        return 0 <= row < len(self._rows) and (
            world_plan.slug(str(self._rows[row].get("name", ""))) in self.locked_names
        )

    # ------------------------------------------------------------------ changes (undoable)

    def _remember(self) -> None:
        self._history.append((self.enabled(), copy.deepcopy(self._rows)))

    def _changed(self) -> None:
        self._rebuild()
        self.edited.emit()

    def undo(self) -> bool:
        """Take back the last change to the table (rows, cells, the box)."""
        if not self._history:
            return False
        enabled, rows = self._history.pop()
        self._rows = rows
        self._loading = True
        self.enable_box.setChecked(enabled)
        self._loading = False
        self._changed()
        return True

    def _on_enabled(self, on: bool) -> None:
        if self._loading:
            return
        self._history.append((not on, copy.deepcopy(self._rows)))
        if on and not self._rows:
            self._rows = world_plan.default_areas()
        self._changed()

    def add_row(self, name: str = "") -> int:
        """A new area at the end; returns its row."""
        self._remember()
        taken = {world_plan.slug(str(r.get("name", ""))) for r in self._rows}
        if not name:
            n = len(self._rows) + 1
            while world_plan.slug(f"Area {n}") in taken:
                n += 1
            name = f"Area {n}"
        row: dict[str, Any] = {
            "name": name,
            "biome": "field",
            "size": list(world_plan.DEFAULT_SIZE),
            "enemies": 2,
            "chests": 1,
        }
        if self.locked_names and self._rows:  # the world exists: the new area hangs on one
            row["join"] = str(self._rows[0]["name"])
        self._rows.append(row)
        self._changed()
        self.table.selectRow(len(self._rows) - 1)
        return len(self._rows) - 1

    def remove_row(self, row: int) -> bool:
        if not 0 <= row < len(self._rows) or self.is_locked(row):
            return False
        self._remember()
        del self._rows[row]
        self._changed()
        return True

    def move_row(self, row: int, by: int) -> bool:
        to = row + by
        if not (0 <= row < len(self._rows) and 0 <= to < len(self._rows)) or self.locked_names:
            return False  # the order of a world that exists means nothing any more
        self._remember()
        self._rows.insert(to, self._rows.pop(row))
        self._changed()
        self.table.selectRow(to)
        return True

    def set_value(self, row: int, key: str, value: Any) -> bool:
        """One cell: ``name``, ``biome``, ``width``, ``height``, ``enemies``, ``chests``,
        ``join`` or ``reroll``."""
        if not 0 <= row < len(self._rows) or self.is_locked(row):
            return False
        area = self._rows[row]
        size = list(area.get("size", world_plan.DEFAULT_SIZE))
        old = {"width": size[0], "height": size[1]}.get(key, area.get(key))
        if old == value:
            return False
        self._remember()
        if key == "width":
            area["size"] = [int(value), size[1]]
        elif key == "height":
            area["size"] = [size[0], int(value)]
        elif key == "join" and not value:
            area.pop("join", None)
        else:
            area[key] = value
        self._changed()
        return True

    # ------------------------------------------------------------------ the widgets

    def _update_buttons(self) -> None:
        on = self.enabled()
        row = self.table.currentRow()
        movable = on and not self.locked_names
        self.table.setEnabled(on)
        self.add_button.setEnabled(on and len(self._rows) < world_plan.MAX_AREAS)
        self.remove_button.setEnabled(on and 0 <= row < len(self._rows) and not self.is_locked(row))
        self.up_button.setEnabled(movable and row > 0)
        self.down_button.setEnabled(movable and 0 <= row < len(self._rows) - 1)
        self.undo_button.setEnabled(bool(self._history))

    def _rebuild(self) -> None:
        self._loading = True
        keep = self.table.currentRow()
        self.table.setRowCount(len(self._rows))
        names = [str(r.get("name", "")) for r in self._rows]
        for at, area in enumerate(self._rows):
            locked = self.is_locked(at)
            item = QTableWidgetItem(str(area.get("name", "")))
            if locked:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(at, NAME, item)
            biome = QComboBox()
            for key in world_plan.BIOMES:
                biome.addItem(self.tr(BIOME_LABELS[key]), key)
            biome.setCurrentIndex(max(0, biome.findData(area.get("biome", "field"))))
            biome.setEnabled(not locked)
            biome.currentIndexChanged.connect(
                lambda _i, r=at, w=biome: self.set_value(r, "biome", w.currentData())
            )
            self.table.setCellWidget(at, BIOME, biome)
            size = area.get("size", list(world_plan.DEFAULT_SIZE))
            village = area.get("biome") == "village"
            cells = (
                (WIDTH, "width", size[0], world_plan.MIN_SIZE, world_plan.MAX_SIZE),
                (HEIGHT, "height", size[1], world_plan.MIN_SIZE, world_plan.MAX_SIZE),
                (ENEMIES, "enemies", area.get("enemies", 2), 0, 12),
                (CHESTS, "chests", area.get("chests", 1), 0, 12),
            )
            for column, key, value, low, high in cells:
                box = QSpinBox()
                box.setRange(low, high)
                box.setValue(int(value))
                box.setKeyboardTracking(False)
                # the village is the starter map: its size and counts are set above the table
                box.setEnabled(not locked and not village)
                box.setToolTip(
                    self.tr("The village is the starter map: its options above decide this")
                    if village
                    else ""
                )
                box.valueChanged.connect(lambda v, r=at, k=key: self.set_value(r, k, int(v)))
                self.table.setCellWidget(at, column, box)
            join = QComboBox()
            join.addItem(self.tr("(any)"), "")
            for name in names:
                if name != area.get("name"):
                    join.addItem(name, name)
            join.setCurrentIndex(max(0, join.findData(area.get("join", ""))))
            join.setEnabled(not locked and bool(self.locked_names))
            join.setToolTip(self.tr("For an area added to a world that exists: its neighbour"))
            join.currentIndexChanged.connect(
                lambda _i, r=at, w=join: self.set_value(r, "join", w.currentData())
            )
            self.table.setCellWidget(at, JOIN, join)
        if 0 <= keep < len(self._rows):
            self.table.selectRow(keep)
        self._loading = False
        self.note.setVisible(bool(self.locked_names) and self.enabled())
        # "Joined to" only means something for an area added to a world that exists
        self.table.setColumnHidden(JOIN, not self.locked_names)
        problem = self.problem()
        self.error.setText(problem)
        self.error.setVisible(bool(problem))
        self._update_buttons()

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._loading or item.column() != NAME:
            return
        if not self.set_value(item.row(), "name", item.text().strip()):
            self._rebuild()  # put the old text back


class WorldPreview(QWidget):
    """The planned world: one tile per area where the plan puts it, with a mark for every door
    pair. A click chooses an area (``areaChosen``); the chosen area is drawn cell by cell in the
    lower half (doors, chests, enemies, decorations, water). ``plan`` is a world plan."""

    areaChosen = Signal(str)  # noqa: N815
    TILE = QSize(92, 56)
    GAP = 14

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("worldPreview")
        self.plan: dict[str, Any] | None = None
        self.chosen = ""
        self.setMinimumHeight(260)
        self.setToolTip(self.tr("Click an area to see what stands in it"))

    def set_plan(self, plan: dict[str, Any] | None) -> None:
        self.plan = plan
        ids = [a["id"] for a in plan["areas"]] if plan else []
        if self.chosen not in ids:
            self.chosen = ids[1] if len(ids) > 1 else (ids[0] if ids else "")
        self.update()

    def tiles(self) -> dict[str, QRect]:
        """The rectangle of every area's tile, by area id."""
        if not self.plan:
            return {}
        cells = {k: (v[0], v[1]) for k, v in self.plan["grid"].items()}
        low_x = min(c[0] for c in cells.values())
        low_y = min(c[1] for c in cells.values())
        pitch_x, pitch_y = self.TILE.width() + self.GAP, self.TILE.height() + self.GAP
        return {
            area_id: QRect(
                self.GAP + (cx - low_x) * pitch_x,
                self.GAP + (cy - low_y) * pitch_y,
                self.TILE.width(),
                self.TILE.height(),
            )
            for area_id, (cx, cy) in cells.items()
        }

    def area_at(self, pos: QPoint) -> str:
        return next((k for k, rect in self.tiles().items() if rect.contains(pos)), "")

    def choose(self, area_id: str) -> None:
        if self.plan and area_id and area_id != self.chosen:
            self.chosen = area_id
            self.update()
            self.areaChosen.emit(area_id)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self.choose(self.area_at(event.position().toPoint()))
        super().mousePressEvent(event)

    def door_marks(self) -> list[QPoint]:
        """The middle of the shared edge of every two areas that a door pair joins."""
        if not self.plan:
            return []
        tiles = self.tiles()
        seen: set[tuple[str, str]] = set()
        marks = []
        for area in self.plan["areas"]:
            for door in area["doors"]:
                pair = (min(area["id"], door["to"]), max(area["id"], door["to"]))
                if pair in seen or door["to"] not in tiles:
                    continue
                seen.add(pair)
                a, b = tiles[area["id"]].center(), tiles[door["to"]].center()
                marks.append(QPoint((a.x() + b.x()) // 2, (a.y() + b.y()) // 2))
        return marks

    def detail_rect(self) -> QRect:
        tiles = self.tiles()
        top = max((r.bottom() for r in tiles.values()), default=0) + self.GAP
        return QRect(self.GAP, top, self.width() - 2 * self.GAP, max(0, self.height() - top - 4))

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        palette = self.palette()
        painter.fillRect(self.rect(), palette.base())
        if not self.plan:
            painter.end()
            return
        locked = (self.plan.get("key") or {}).get("opens")
        for area in self.plan["areas"]:
            rect = self.tiles()[area["id"]]
            painter.fillRect(rect, QColor(BIOME_COLORS[area["biome"]]))
            pen = QPen(palette.highlight().color() if area["id"] == self.chosen else QColor("#222"))
            pen.setWidth(3 if area["id"] == self.chosen else 1)
            painter.setPen(pen)
            painter.drawRect(rect)
            painter.setPen(QColor("#111"))
            label = area["name"] + (" 🔒" if area["id"] == locked else "")
            painter.drawText(
                rect.adjusted(3, 2, -3, -2),
                Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                label,
            )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#e6c765"))
        for mark in self.door_marks():
            painter.drawEllipse(mark, 5, 5)
        self._paint_area(painter)
        painter.end()

    def _paint_area(self, painter: QPainter) -> None:
        area = world_plan.area_of(self.plan, self.chosen) if self.plan else None
        box = self.detail_rect()
        if area is None or box.height() < 24:
            return
        w, h = area["size"]
        cell = max(2, min(box.width() // w, box.height() // h))
        left, top = box.left(), box.top()
        painter.fillRect(QRect(left, top, w * cell, h * cell), QColor(BIOME_COLORS[area["biome"]]))
        painter.setPen(QPen(QColor("#333"), max(1, cell // 3)))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRect(left, top, w * cell, h * cell))
        painter.setPen(Qt.PenStyle.NoPen)

        def dot(at: list[int], colour: str) -> None:
            painter.fillRect(
                QRect(left + at[0] * cell, top + at[1] * cell, cell, cell), QColor(colour)
            )

        water = area.get("water")
        if water:
            painter.fillRect(
                QRect(
                    left + water[0] * cell, top + water[1] * cell, water[2] * cell, water[3] * cell
                ),
                QColor("#3d79b8"),
            )
        for at in area.get("decorations", []):
            dot(at, "#2c5a31")
        for chest in area.get("chests", []):
            dot(chest["cell"], "#f2c230")
        for enemy in area.get("enemies", []):
            dot(enemy["cell"], "#c62828")
        for door in area["doors"]:
            dot(door["cell"], "#e6c765")
            dot(door["spawn"], "#ffffff")
