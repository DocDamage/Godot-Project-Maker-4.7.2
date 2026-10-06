"""Object cutter: draw, move and annotate objects (regions) on a sheet."""

from __future__ import annotations

import copy
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QMouseEvent, QPen
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGraphicsRectItem,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from rpggen.core import objects as objects_mod
from rpggen.core.catalog import SheetObject
from rpggen.gui.widgets.image_view import ImageView

TOOLS = ["rect", "select", "footprint", "door", "origin"]
TOOL_LABELS = {
    "rect": "Rectangle",
    "select": "Select / move",
    "footprint": "Footprint",
    "door": "Door point",
    "origin": "Origin",
}
OBJECT_ROLES = ["BUILDING", "DECORATION", "INTERIOR", "NPC", "ENEMY", "ITEM", "WALL", "WATER"]
COLLISION_PROFILES = ["CUSTOM", "NONE", "FULL", "BOTTOM_HALF", "BOTTOM_EDGE", "ALPHA_POLYGON"]
AUTO_COLOR = QColor(40, 130, 255)
USER_COLOR = QColor(40, 190, 70)
SELECTED_COLOR = QColor(255, 220, 0)
FOOTPRINT_COLOR = QColor(255, 0, 0, 100)
HANDLE_PIXELS = 8  # corner grab radius on screen


class CutterView(ImageView):
    """Reports raw mouse positions (image pixels) so the dialog can run the active tool."""

    pressed = Signal(float, float, bool)  # x, y, alt held
    moved = Signal(float, float, bool)
    released = Signal(float, float, bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("cutterView", parent)
        self.setDragMode(self.DragMode.NoDrag)
        self.setMouseTracking(False)

    def _emit(self, signal: Signal, event: QMouseEvent) -> None:
        point = self.mapToScene(event.position().toPoint())
        alt = bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)
        signal.emit(point.x(), point.y(), alt)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._emit(self.pressed, event)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._emit(self.moved, event)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._emit(self.released, event)
            event.accept()
        else:
            super().mouseReleaseEvent(event)


class ObjectCutterDialog(QDialog):
    def __init__(
        self,
        sheet_path: Path,
        sheet_id: str,
        objects: list[SheetObject],
        grid: dict[str, list[int]] | None,
        taken_ids: set[str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("objectCutter")
        self.setWindowTitle(self.tr("Object cutter"))
        self.resize(1100, 720)
        self.sheet_id = sheet_id
        self.grid = grid
        self.objects: list[SheetObject] = copy.deepcopy(objects)
        self.taken_ids = set(taken_ids or set()) | {o.id for o in self.objects}
        self.selected: str | None = None
        self.tool = "rect"
        self._drag: dict | None = None
        self._items: list = []
        self._rubber: QGraphicsRectItem | None = None
        self._loading = False

        layout = QHBoxLayout(self)
        left = QVBoxLayout()
        layout.addLayout(left, 1)
        bar = QHBoxLayout()
        self.tool_group = QButtonGroup(self)
        self.tool_buttons: dict[str, QToolButton] = {}
        for tool in TOOLS:
            button = QToolButton()
            button.setObjectName(f"tool_{tool}")
            button.setText(self.tr(TOOL_LABELS[tool]))
            button.setCheckable(True)
            button.setAutoRaise(False)
            self.tool_group.addButton(button)
            bar.addWidget(button)
            button.clicked.connect(lambda _=False, t=tool: self.set_tool(t))
            self.tool_buttons[tool] = button
        bar.addStretch(1)
        left.addLayout(bar)
        self.view = CutterView()
        left.addWidget(self.view, 1)
        self.hint = QLabel()
        self.hint.setObjectName("cutterHint")
        left.addWidget(self.hint)

        side = QVBoxLayout()
        layout.addLayout(side)
        self.list = QListWidget()
        self.list.setObjectName("objectList")
        self.list.setMinimumWidth(240)
        side.addWidget(self.list, 1)
        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setObjectName("objectName")
        self.role_combo = QComboBox()
        self.role_combo.setObjectName("objectRole")
        self.role_combo.addItems(OBJECT_ROLES)
        self.tags_edit = QLineEdit()
        self.tags_edit.setObjectName("objectTags")
        self.collision_combo = QComboBox()
        self.collision_combo.setObjectName("objectCollision")
        self.collision_combo.addItems(COLLISION_PROFILES)
        form.addRow(self.tr("Name"), self.name_edit)
        form.addRow(self.tr("Role"), self.role_combo)
        form.addRow(self.tr("Tags"), self.tags_edit)
        form.addRow(self.tr("Collision"), self.collision_combo)
        side.addLayout(form)
        self.delete_button = QPushButton(self.tr("Delete"))
        self.delete_button.setObjectName("deleteObject")
        self.reject_button = QPushButton(self.tr("Reject suggestion"))
        self.reject_button.setObjectName("rejectObject")
        self.accept_all_button = QPushButton(self.tr("Accept all suggestions"))
        self.accept_all_button.setObjectName("acceptAll")
        for b in (self.delete_button, self.reject_button, self.accept_all_button):
            side.addWidget(b)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Cancel
        )
        self.apply_button = buttons.button(QDialogButtonBox.StandardButton.Apply)
        self.apply_button.setObjectName("cutterApply")
        buttons.clicked.connect(
            lambda b: self.accept() if b is self.apply_button else self.reject()
        )
        side.addWidget(buttons)

        self.view.set_image(Path(sheet_path), grid)
        self.size = self.view.image_size
        self.view.pressed.connect(self.tool_press)
        self.view.moved.connect(self.tool_move)
        self.view.released.connect(self.tool_release)
        self.list.currentItemChanged.connect(self._on_list)
        self.name_edit.editingFinished.connect(self._on_name)
        self.role_combo.activated.connect(self._on_role)
        self.tags_edit.editingFinished.connect(self._on_tags)
        self.collision_combo.activated.connect(self._on_collision)
        self.delete_button.clicked.connect(self.delete_selected)
        self.reject_button.clicked.connect(self.reject_selected)
        self.accept_all_button.clicked.connect(self.accept_all)
        self.set_tool("rect")
        self._refresh()

    # ------------------------------------------------------------------ model helpers

    def visible_objects(self) -> list[SheetObject]:
        return [o for o in self.objects if o.role != "NONE"]

    def get(self, object_id: str | None) -> SheetObject | None:
        return next((o for o in self.objects if o.id == object_id), None)

    def result_objects(self) -> list[SheetObject]:
        return copy.deepcopy(self.objects)

    def _replace(self, new: SheetObject) -> None:
        self.objects = [new if o.id == new.id else o for o in self.objects]

    def hit(self, x: float, y: float) -> SheetObject | None:
        """The smallest visible object containing the point."""
        found = [
            o
            for o in self.visible_objects()
            if o.region[0] <= x < o.region[0] + o.region[2]
            and o.region[1] <= y < o.region[1] + o.region[3]
        ]
        return min(found, key=lambda o: o.region[2] * o.region[3], default=None)

    def set_tool(self, tool: str) -> None:
        self.tool = tool
        self.tool_buttons[tool].setChecked(True)
        hints = {
            "rect": self.tr("Drag to cut an object (snaps to the grid; hold Alt for pixels)."),
            "select": self.tr("Click to select; drag to move; drag a corner to resize."),
            "footprint": self.tr("Drag inside an object to set the area that blocks movement."),
            "door": self.tr("Click inside an object to place its door point."),
            "origin": self.tr("Click inside an object to set its origin."),
        }
        self.hint.setText(hints[tool])

    def select(self, object_id: str | None) -> None:
        self.selected = object_id
        self._refresh()

    # ------------------------------------------------------------------ tools

    def tool_press(self, x: float, y: float, alt: bool = False) -> None:
        self._drag = None
        snap = not alt
        if self.tool == "rect":
            self._drag = {"kind": "rect", "start": (x, y), "snap": snap}
        elif self.tool == "select":
            self._press_select(x, y)
        elif self.tool in ("footprint", "door", "origin"):
            obj = self.hit(x, y)
            if obj is None:
                return
            self.select(obj.id)
            if self.tool == "footprint":
                self._drag = {"kind": "footprint", "start": (x, y), "id": obj.id}
            elif self.tool == "door":
                self._set_point(obj, "door", x, y)
            else:
                self._set_point(obj, "origin", x, y)

    def _press_select(self, x: float, y: float) -> None:
        selected = self.get(self.selected)
        if selected is not None:
            corner = self._corner_at(selected, x, y)
            if corner is not None:
                self._drag = {"kind": "resize", "id": selected.id, "corner": corner}
                return
        obj = self.hit(x, y)
        self.select(obj.id if obj else None)
        if obj is not None:
            self._drag = {
                "kind": "move",
                "id": obj.id,
                "start": (x, y),
                "region": list(obj.region),
            }

    def _corner_at(self, obj: SheetObject, x: float, y: float) -> tuple[int, int] | None:
        rx, ry, rw, rh = obj.region
        radius = max(2.0, HANDLE_PIXELS / max(self.view.zoom, 0.01))
        for cx, cy in ((0, 0), (1, 0), (0, 1), (1, 1)):
            px, py = rx + cx * rw, ry + cy * rh
            if abs(x - px) <= radius and abs(y - py) <= radius:
                return cx, cy
        return None

    def tool_move(self, x: float, y: float, alt: bool = False) -> None:
        drag = self._drag
        if drag is None:
            return
        kind = drag["kind"]
        if kind == "rect":
            rect = objects_mod.snap_rect(*drag["start"], x, y, self.grid, self.size, snap=not alt)
            drag["rect"] = rect
            self._show_rubber(rect)
        elif kind == "move":
            obj = self.get(drag["id"])
            if obj is not None:
                self._apply_move(obj, drag, x, y, snap=not alt)
        elif kind == "resize":
            obj = self.get(drag["id"])
            if obj is not None:
                self._apply_resize(obj, drag, x, y, snap=not alt)
        elif kind == "footprint":
            drag["end"] = (x, y)
            obj = self.get(drag["id"])
            if obj is not None:
                self._show_rubber(self._footprint_rect_in_image(obj, drag["start"], (x, y)))

    def tool_release(self, x: float, y: float, alt: bool = False) -> None:
        drag, self._drag = self._drag, None
        self._clear_rubber()
        if drag is None:
            return
        kind = drag["kind"]
        if kind == "rect":
            rect = objects_mod.snap_rect(*drag["start"], x, y, self.grid, self.size, snap=not alt)
            self.add_region(rect)
        elif kind == "footprint":
            obj = self.get(drag["id"])
            if obj is not None:
                ix, iy, w, h = self._footprint_rect_in_image(obj, drag["start"], (x, y))
                rel = [ix - obj.region[0], iy - obj.region[1], w, h]
                self._replace(objects_mod.with_footprint(obj, rel))
                self._touch(obj.id)
        self._refresh()

    def _footprint_rect_in_image(
        self, obj: SheetObject, a: tuple[float, float], b: tuple[float, float]
    ) -> objects_mod.Rect:
        rx, ry, rw, rh = obj.region
        x0, x1 = sorted((int(a[0]), int(b[0])))
        y0, y1 = sorted((int(a[1]), int(b[1])))
        x0, x1 = max(rx, x0), min(rx + rw - 1, x1)
        y0, y1 = max(ry, y0), min(ry + rh - 1, y1)
        return x0, y0, max(1, x1 - x0 + 1), max(1, y1 - y0 + 1)

    def _snap_coord(self, value: float, axis: int) -> int:
        if not self.grid:
            return int(value)
        c = self.grid["cell"][axis]
        m = self.grid.get("margin", [0, 0])[axis]
        s = self.grid.get("separation", [0, 0])[axis]
        return m + round((value - m) / (c + s)) * (c + s)

    def _apply_move(self, obj: SheetObject, drag: dict, x: float, y: float, *, snap: bool) -> None:
        dx, dy = x - drag["start"][0], y - drag["start"][1]
        nx, ny = drag["region"][0] + int(dx), drag["region"][1] + int(dy)
        if snap and self.grid:
            nx, ny = self._snap_coord(nx, 0), self._snap_coord(ny, 1)
        nx = max(0, min(nx, self.size[0] - obj.region[2]))
        ny = max(0, min(ny, self.size[1] - obj.region[3]))
        moved = copy.deepcopy(obj)
        moved.region = [nx, ny, obj.region[2], obj.region[3]]
        self._replace(moved)
        self._touch(obj.id, redraw=True)

    def _nearest_edge(self, value: float, axis: int) -> int:
        """The cell edge (start or end of a cell) closest to ``value``."""
        if not self.grid:
            return int(value)
        c = self.grid["cell"][axis]
        m = self.grid.get("margin", [0, 0])[axis]
        s = self.grid.get("separation", [0, 0])[axis]
        k = max(0, round((value - m) / (c + s)))
        edges = [m + j * (c + s) + off for j in (k - 1, k, k + 1) if j >= 0 for off in (0, c)]
        return min(edges, key=lambda e: abs(e - value))

    def _apply_resize(
        self, obj: SheetObject, drag: dict, x: float, y: float, *, snap: bool
    ) -> None:
        cx, cy = drag["corner"]
        rx, ry, rw, rh = obj.region
        fixed_x = rx + (rw if cx == 0 else 0)
        fixed_y = ry + (rh if cy == 0 else 0)
        mx = self._nearest_edge(x, 0) if snap else int(round(x))
        my = self._nearest_edge(y, 1) if snap else int(round(y))
        left, right = sorted((fixed_x, mx))
        top, bottom = sorted((fixed_y, my))
        rect = objects_mod.clamp_rect(
            (left, top, max(1, right - left), max(1, bottom - top)), *self.size
        )
        resized = copy.deepcopy(obj)
        resized.region = list(rect)
        self._fit_inner(resized)
        self._replace(resized)
        self._touch(obj.id, redraw=True)

    @staticmethod
    def _fit_inner(obj: SheetObject) -> None:
        rw, rh = obj.region[2], obj.region[3]
        obj.origin = [max(0, min(obj.origin[0], rw - 1)), max(0, min(obj.origin[1], rh - 1))]
        obj.footprint = objects_mod.clamp_inner(tuple(obj.footprint), obj.region)  # type: ignore[arg-type]
        if obj.collision.get("profile") == "CUSTOM":
            obj.collision = objects_mod.custom_collision(obj.footprint)
        if obj.door is not None:
            obj.door = [max(0, min(obj.door[0], rw - 1)), max(0, min(obj.door[1], rh - 1))]

    def _set_point(self, obj: SheetObject, key: str, x: float, y: float) -> None:
        edited = copy.deepcopy(obj)
        point = [int(x) - obj.region[0], int(y) - obj.region[1]]
        setattr(edited, key, point)
        self._replace(edited)
        self._touch(obj.id)
        self._refresh()

    def _touch(self, object_id: str, redraw: bool = False) -> None:
        """An edited auto object becomes a user object (a re-analysis then keeps the edit)."""
        obj = self.get(object_id)
        if obj is not None and obj.source == "auto":
            edited = copy.deepcopy(obj)
            edited.source = "user"
            self._replace(edited)
        if redraw:
            self._draw()

    # ------------------------------------------------------------------ creating and editing

    def add_region(self, rect: objects_mod.Rect) -> SheetObject:
        n = len(self.objects) + 1
        names = {o.name for o in self.objects}
        while f"object_{n}" in names:
            n += 1
        obj = objects_mod.make_object(self.sheet_id, f"object_{n}", rect, self.taken_ids)
        self.taken_ids.add(obj.id)
        self.objects.append(obj)
        self.selected = obj.id
        self._refresh()
        return obj

    def _on_list(self, item: QListWidgetItem | None) -> None:
        if self._loading:
            return
        self.selected = item.data(Qt.ItemDataRole.UserRole) if item else None
        self._draw()
        self._load_fields()

    def _edit_selected(self, **changes) -> None:  # noqa: ANN003
        obj = self.get(self.selected)
        if obj is None or self._loading:
            return
        edited = copy.deepcopy(obj)
        for key, value in changes.items():
            setattr(edited, key, value)
        self._replace(edited)
        self._touch(obj.id)
        self._refresh()

    def _on_name(self) -> None:
        name = self.name_edit.text().strip()
        obj = self.get(self.selected)
        if name and obj is not None and name != obj.name:
            self._edit_selected(name=name)

    def _on_role(self) -> None:
        self._edit_selected(role=self.role_combo.currentText())

    def _on_tags(self) -> None:
        tags = [t.strip() for t in self.tags_edit.text().split(",") if t.strip()]
        obj = self.get(self.selected)
        if obj is not None and tags != obj.tags:
            self._edit_selected(tags=tags)

    def _on_collision(self) -> None:
        obj = self.get(self.selected)
        if obj is None:
            return
        profile = self.collision_combo.currentText()
        collision = (
            objects_mod.custom_collision(obj.footprint)
            if profile == "CUSTOM"
            else {"profile": profile}
        )
        self._edit_selected(collision=collision)

    def delete_selected(self) -> None:
        """Remove a user object; deleting a suggestion rejects it (so it is not re-created)."""
        obj = self.get(self.selected)
        if obj is None:
            return
        if obj.source == "user":
            self.objects = [o for o in self.objects if o.id != obj.id]
            self.selected = None
            self._refresh()
        else:
            self.reject_selected()

    def reject_selected(self) -> None:
        obj = self.get(self.selected)
        if obj is None:
            return
        if obj.source == "user":
            self.delete_selected()
            return
        rejected = copy.deepcopy(obj)
        rejected.role, rejected.status = "NONE", "UNUSED"
        self._replace(rejected)
        self.selected = None
        self._refresh()

    def accept_all(self) -> None:
        for i, obj in enumerate(self.objects):
            if obj.source != "user" and obj.status == "AUTO_DETECTED":
                accepted = copy.deepcopy(obj)
                accepted.status = "CONFIRMED"
                self.objects[i] = accepted
        self._refresh()

    # ------------------------------------------------------------------ drawing

    def _refresh(self) -> None:
        self._loading = True
        try:
            self.list.clear()
            for obj in self.visible_objects():
                item = QListWidgetItem(f"{obj.name}  [{obj.role}]")
                item.setData(Qt.ItemDataRole.UserRole, obj.id)
                self.list.addItem(item)
                if obj.id == self.selected:
                    self.list.setCurrentItem(item)
        finally:
            self._loading = False
        self._load_fields()
        self._draw()

    def _load_fields(self) -> None:
        obj = self.get(self.selected)
        self._loading = True
        try:
            enabled = obj is not None
            for widget in (
                self.name_edit,
                self.role_combo,
                self.tags_edit,
                self.collision_combo,
                self.delete_button,
                self.reject_button,
            ):
                widget.setEnabled(enabled)
            if obj is not None:
                self.name_edit.setText(obj.name)
                index = self.role_combo.findText(obj.role)
                if index < 0:
                    self.role_combo.addItem(obj.role)
                    index = self.role_combo.findText(obj.role)
                self.role_combo.setCurrentIndex(index)
                self.tags_edit.setText(", ".join(obj.tags))
                profile = obj.collision.get("profile", "CUSTOM")
                idx = self.collision_combo.findText(profile)
                self.collision_combo.setCurrentIndex(max(0, idx))
            self.reject_button.setText(
                self.tr("Reject suggestion")
                if obj is not None and obj.source != "user"
                else self.tr("Delete")
            )
        finally:
            self._loading = False

    def _clear_items(self) -> None:
        for item in self._items:
            self.view.scene().removeItem(item)
        self._items = []

    def _draw(self) -> None:
        self._clear_items()
        scene = self.view.scene()
        for obj in self.visible_objects():
            selected = obj.id == self.selected
            color = (
                SELECTED_COLOR if selected else (USER_COLOR if obj.source == "user" else AUTO_COLOR)
            )
            pen = QPen(color)
            pen.setCosmetic(True)
            pen.setWidth(3 if selected else 2)
            x, y, w, h = obj.region
            rect = scene.addRect(x, y, w, h, pen, QBrush(Qt.BrushStyle.NoBrush))
            self._items.append(rect)
            label = scene.addText(obj.name, QFont("Sans", 7))
            label.setDefaultTextColor(color)
            label.setPos(x, y - 12)
            self._items.append(label)
            fx, fy, fw, fh = obj.footprint
            foot = scene.addRect(
                x + fx, y + fy, fw, fh, QPen(Qt.PenStyle.NoPen), QBrush(FOOTPRINT_COLOR)
            )
            self._items.append(foot)
            cross = QPen(QColor(255, 255, 255))
            cross.setCosmetic(True)
            ox, oy = x + obj.origin[0], y + obj.origin[1]
            self._items.append(scene.addLine(ox - 3, oy, ox + 3, oy, cross))
            self._items.append(scene.addLine(ox, oy - 3, ox, oy + 3, cross))
            if obj.door is not None:
                dx, dy = x + obj.door[0], y + obj.door[1]
                self._items.append(
                    scene.addEllipse(
                        dx - 2, dy - 2, 4, 4, QPen(QColor(255, 255, 0)), QBrush(QColor(255, 255, 0))
                    )
                )

    def _show_rubber(self, rect: objects_mod.Rect) -> None:
        self._clear_rubber()
        pen = QPen(QColor(255, 255, 255))
        pen.setCosmetic(True)
        pen.setStyle(Qt.PenStyle.DashLine)
        self._rubber = self.view.scene().addRect(*rect, pen)

    def _clear_rubber(self) -> None:
        if self._rubber is not None:
            self.view.scene().removeItem(self._rubber)
            self._rubber = None
