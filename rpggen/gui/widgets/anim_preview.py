"""Animation preview and editor dialog."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from PySide6.QtCore import QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen, QPixmap, QTransform
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSlider,
    QSplitter,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rpggen.core import anim_edit
from rpggen.gui.widgets.image_view import ImageView

Anim = dict[str, Any]
PREVIEW_SCALE = 4
SPEED_MIN, SPEED_MAX = 25, 400  # percent


class FramePreview(QWidget):
    """One animation frame scaled with nearest-neighbor; click to place the origin."""

    originPicked = Signal(int, int)  # noqa: N815 - frame pixel coordinates

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("framePreview")
        self.pixmap: QPixmap | None = None
        self.origin: tuple[int, int] | None = None
        self.scale = PREVIEW_SCALE
        self.setMinimumSize(160, 200)

    def set_frame(self, pixmap: QPixmap | None, flip: bool = False) -> None:
        if pixmap is not None and flip:
            pixmap = pixmap.transformed(QTransform().scale(-1, 1))
        self.pixmap = pixmap
        if pixmap is not None and not pixmap.isNull():
            self.scale = max(
                1, min(8, min(200 // max(1, pixmap.width()), 220 // max(1, pixmap.height())))
            )
        self.update()

    def set_origin(self, origin: tuple[int, int] | None) -> None:
        self.origin = origin
        self.update()

    def _target(self) -> QRect:
        if self.pixmap is None:
            return QRect()
        w, h = self.pixmap.width() * self.scale, self.pixmap.height() * self.scale
        return QRect((self.width() - w) // 2, (self.height() - h) // 2, w, h)

    def paintEvent(self, event) -> None:  # noqa: ANN001
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(70, 70, 70))
        if self.pixmap is None:
            painter.end()
            return
        target = self._target()
        painter.drawPixmap(target, self.pixmap)
        if self.origin is not None:
            ox = target.left() + self.origin[0] * self.scale + self.scale // 2
            oy = target.top() + self.origin[1] * self.scale + self.scale // 2
            baseline = QPen(QColor(255, 220, 0, 160))
            painter.setPen(baseline)
            painter.drawLine(target.left(), oy, target.right(), oy)  # baseline
            cross = QPen(QColor(255, 60, 60))
            painter.setPen(cross)
            painter.drawLine(ox - 6, oy, ox + 6, oy)
            painter.drawLine(ox, oy - 6, ox, oy + 6)
        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        target = self._target()
        if self.pixmap is None or not target.contains(event.position().toPoint()):
            return
        point = event.position().toPoint() - target.topLeft()
        self.originPicked.emit(point.x() // self.scale, point.y() // self.scale)


class AnimEditorDialog(QDialog):
    """Preview, edit and apply the animations of one sprite asset."""

    def __init__(
        self,
        sheet_path: Path,
        animations: dict[str, Anim],
        frame: tuple[int, int],
        origin: tuple[int, int] | None,
        grid: dict[str, list[int]] | None,
        *,
        arpg: bool = False,
        sheet_resolver=None,  # noqa: ANN001 - callable(source) -> Path | None
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("animEditor")
        self.setWindowTitle(self.tr("Animations"))
        self.resize(1000, 760)
        self.sheet_path = Path(sheet_path)
        self.original: dict[str, Anim] = copy.deepcopy(animations)
        self.animations: dict[str, Anim] = copy.deepcopy(animations)
        self.frame = tuple(frame)
        self.original_frame = tuple(frame)
        self.origin = tuple(origin) if origin else None
        self.original_origin = self.origin
        self.grid = grid or {"cell": list(frame), "margin": [0, 0], "separation": [0, 0]}
        self.arpg = arpg
        self.sheet_resolver = sheet_resolver or (lambda source: None)
        self.current: str | None = None
        self.index = 0
        self.playing = False
        self._pixmaps: dict[Path, QPixmap] = {}

        outer = QVBoxLayout(self)
        top = QSplitter(Qt.Orientation.Horizontal)
        outer.addWidget(top, 3)

        # left: names, direction groups together
        left = QWidget()
        left_box = QVBoxLayout(left)
        self.tree = QTreeWidget()
        self.tree.setObjectName("animTree")
        self.tree.setHeaderHidden(True)
        left_box.addWidget(self.tree, 1)
        row = QHBoxLayout()
        self.add_button = QToolButton()
        self.add_button.setObjectName("addAnimButton")
        self.add_button.setText(self.tr("Add animation"))
        self.add_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.mirror_button = QToolButton()
        self.mirror_button.setObjectName("mirrorButton")
        self.mirror_button.setText(self.tr("Mirror from…"))
        self.mirror_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        row.addWidget(self.add_button)
        row.addWidget(self.mirror_button)
        left_box.addLayout(row)
        top.addWidget(left)

        # center: playback
        center = QWidget()
        center_box = QVBoxLayout(center)
        self.preview = FramePreview()
        center_box.addWidget(self.preview, 1)
        self.frame_label = QLabel()
        self.frame_label.setObjectName("frameLabel")
        center_box.addWidget(self.frame_label)
        controls = QHBoxLayout()
        self.play_button = QPushButton(self.tr("Play"))
        self.play_button.setObjectName("playButton")
        self.play_button.setCheckable(True)
        self.step_button = QPushButton(self.tr("Step"))
        self.step_button.setObjectName("stepButton")
        self.speed = QSlider(Qt.Orientation.Horizontal)
        self.speed.setObjectName("speedSlider")
        self.speed.setRange(SPEED_MIN, SPEED_MAX)
        self.speed.setValue(100)
        controls.addWidget(self.play_button)
        controls.addWidget(self.step_button)
        controls.addWidget(QLabel(self.tr("Speed")))
        controls.addWidget(self.speed, 1)
        center_box.addLayout(controls)
        top.addWidget(center)

        # right: fields and list buttons
        right = QWidget()
        form = QFormLayout(right)
        self.fps_spin = QDoubleSpinBox()
        self.fps_spin.setObjectName("fpsSpin")
        self.fps_spin.setRange(0.5, 60)
        self.fps_spin.setDecimals(1)
        self.loop_check = QCheckBox(self.tr("Loop"))
        self.loop_check.setObjectName("loopCheck")
        self.flip_check = QCheckBox(self.tr("Flip horizontally"))
        self.flip_check.setObjectName("flipCheck")
        self.active_edit = QLineEdit()
        self.active_edit.setObjectName("activeFramesEdit")
        self.active_edit.setPlaceholderText(self.tr("e.g. 2,3"))
        self.active_label = QLabel(self.tr("Active frames"))
        form.addRow(self.tr("Frames per second"), self.fps_spin)
        form.addRow(self.loop_check)
        form.addRow(self.flip_check)
        form.addRow(self.active_label, self.active_edit)
        self.active_label.setVisible(arpg)
        self.active_edit.setVisible(arpg)
        self.clear_button = QPushButton(self.tr("Clear"))
        self.clear_button.setObjectName("clearButton")
        self.reverse_button = QPushButton(self.tr("Reverse"))
        self.reverse_button.setObjectName("reverseButton")
        self.pingpong_button = QPushButton(self.tr("Ping-pong"))
        self.pingpong_button.setObjectName("pingPongButton")
        for b in (self.clear_button, self.reverse_button, self.pingpong_button):
            form.addRow(b)
        top.addWidget(right)

        # bottom: the sheet; clicking cells toggles them in the selected animation
        self.sheet = ImageView("animSheet")
        outer.addWidget(self.sheet, 2)
        self.sheet.set_image(self.sheet_path, self.grid)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Cancel
        )
        self.apply_button = buttons.button(QDialogButtonBox.StandardButton.Apply)
        self.apply_button.setObjectName("animApply")
        buttons.clicked.connect(
            lambda b: self.accept() if b is self.apply_button else self.reject()
        )
        outer.addWidget(buttons)

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._tick)

        self.tree.currentItemChanged.connect(self._on_item)
        self.play_button.toggled.connect(self._on_play)
        self.step_button.clicked.connect(self.step)
        self.fps_spin.valueChanged.connect(self._on_fps)
        self.loop_check.toggled.connect(self._on_loop)
        self.flip_check.toggled.connect(self._on_flip)
        self.active_edit.editingFinished.connect(self._on_active)
        self.clear_button.clicked.connect(lambda: self._replace(anim_edit.cleared))
        self.reverse_button.clicked.connect(lambda: self._replace(anim_edit.reversed_frames))
        self.pingpong_button.clicked.connect(lambda: self._replace(anim_edit.ping_pong))
        self.sheet.clicked.connect(self._on_sheet_click)
        self.preview.originPicked.connect(self._on_origin)
        self._rebuild_tree()
        self._rebuild_menus()
        first = next(iter(self.animations), None)
        if first:
            self.select(first)

    # ------------------------------------------------------------------ list of names

    def _rebuild_tree(self, keep: str | None = None) -> None:
        self.tree.blockSignals(True)
        self.tree.clear()
        for action, names in anim_edit.groups(list(self.animations)):
            if len(names) == 1 and anim_edit.split_name(names[0])[1] is None:
                item = QTreeWidgetItem([names[0]])
                item.setData(0, Qt.ItemDataRole.UserRole, names[0])
                self.tree.addTopLevelItem(item)
                continue
            parent = QTreeWidgetItem([action])
            self.tree.addTopLevelItem(parent)
            for name in names:
                child = QTreeWidgetItem([name])
                child.setData(0, Qt.ItemDataRole.UserRole, name)
                parent.addChild(child)
            parent.setExpanded(True)
        self.tree.blockSignals(False)
        if keep:
            self.select(keep)

    def _rebuild_menus(self) -> None:
        add = QMenu(self.add_button)
        for name in anim_edit.missing_standard_names(self.animations):
            add.addAction(name, lambda n=name: self.add_animation(n))
        self.add_button.setMenu(add)
        mirror = QMenu(self.mirror_button)
        for name in self.animations:
            target = anim_edit.mirror_name(name)
            if target:
                mirror.addAction(
                    f"{name} → {target}", lambda n=name, t=target: self.mirror_from(n, t)
                )
        self.mirror_button.setMenu(mirror)

    def names(self) -> list[str]:
        return list(self.animations)

    def select(self, name: str) -> None:
        iterator = [self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount())]
        stack = list(iterator)
        while stack:
            item = stack.pop()
            if item.data(0, Qt.ItemDataRole.UserRole) == name:
                self.tree.setCurrentItem(item)
                return
            stack.extend(item.child(i) for i in range(item.childCount()))

    def _on_item(self, item: QTreeWidgetItem | None) -> None:
        name = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        self.current = name
        self.index = 0
        self._load_fields()
        self._show_frame()
        if self.playing:
            self._schedule()

    # ------------------------------------------------------------------ editing

    def anim(self) -> Anim | None:
        return self.animations.get(self.current) if self.current else None

    def _replace(self, change) -> None:  # noqa: ANN001
        anim = self.anim()
        if anim is not None:
            self.animations[self.current] = change(anim)
            self.index = 0
            self._load_fields()
            self._show_frame()

    def _load_fields(self) -> None:
        anim = self.anim()
        enabled = anim is not None
        for widget in (
            self.fps_spin,
            self.loop_check,
            self.flip_check,
            self.active_edit,
            self.clear_button,
            self.reverse_button,
            self.pingpong_button,
        ):
            widget.setEnabled(enabled)
        for widget in (self.fps_spin, self.loop_check, self.flip_check):
            widget.blockSignals(True)
        if anim:
            self.fps_spin.setValue(float(anim.get("fps", anim_edit.DEFAULT_FPS)))
            self.loop_check.setChecked(bool(anim.get("loop", True)))
            self.flip_check.setChecked(bool(anim.get("flip_h", False)))
            self.active_edit.setText(",".join(str(i) for i in anim.get("active_frames", [])))
        for widget in (self.fps_spin, self.loop_check, self.flip_check):
            widget.blockSignals(False)

    def _on_fps(self, value: float) -> None:
        if self.anim() is not None:
            self.anim()["fps"] = value

    def _on_loop(self, checked: bool) -> None:
        if self.anim() is not None:
            self.anim()["loop"] = checked

    def _on_flip(self, checked: bool) -> None:
        anim = self.anim()
        if anim is not None:
            if checked:
                anim["flip_h"] = True
            else:
                anim.pop("flip_h", None)
            self._show_frame()

    def _on_active(self) -> None:
        anim = self.anim()
        if anim is None:
            return
        try:
            values = [int(p) for p in self.active_edit.text().replace(" ", "").split(",") if p]
        except ValueError:
            return
        if values:
            anim["active_frames"] = values
        else:
            anim.pop("active_frames", None)

    def add_animation(self, name: str) -> None:
        if name in self.animations:
            return
        self.animations[name] = anim_edit.new_animation()
        self._rebuild_tree(keep=name)
        self._rebuild_menus()

    def mirror_from(self, source: str, target: str) -> None:
        if source not in self.animations:
            return
        self.animations[target] = anim_edit.mirrored(self.animations[source])
        self._rebuild_tree(keep=target)
        self._rebuild_menus()

    def _on_sheet_click(self, x: float, y: float) -> None:
        anim = self.anim()
        if anim is None:
            return
        cell = anim_edit.cell_at(self.grid, x, y)
        if cell is None:
            return
        self.animations[self.current] = anim_edit.toggle_cell(anim, cell)
        self.index = 0
        self._show_frame()

    def _on_origin(self, x: int, y: int) -> None:
        self.origin = (x, y)
        self.preview.set_origin(self.origin)

    # ------------------------------------------------------------------ playback

    def _sheet_pixmap(self, path: Path) -> QPixmap | None:
        if path not in self._pixmaps:
            self._pixmaps[path] = QPixmap(str(path))
        pixmap = self._pixmaps[path]
        return None if pixmap.isNull() else pixmap

    def frame_pixmap(self, anim: Anim, index: int) -> QPixmap | None:
        if not anim.get("frames"):
            return None
        source = anim.get("source")
        path = self.sheet_resolver(source) if source else self.sheet_path
        sheet = self._sheet_pixmap(Path(path)) if path else None
        if sheet is None:
            return None
        x, y, w, h = anim_edit.frame_rect(anim, index, self.frame, self.grid)
        return sheet.copy(x, y, w, h)

    def _show_frame(self) -> None:
        anim = self.anim()
        count = len(anim["frames"]) if anim else 0
        if not anim or count == 0:
            self.preview.set_frame(None)
            self.frame_label.setText(self.tr("No frames"))
            return
        self.index %= count
        self.preview.set_frame(self.frame_pixmap(anim, self.index), bool(anim.get("flip_h")))
        self.preview.set_origin(self.origin)
        self.frame_label.setText(self.tr("Frame {0} of {1}").format(self.index + 1, count))

    def step(self) -> None:
        anim = self.anim()
        if not anim or not anim["frames"]:
            return
        count = len(anim["frames"])
        self.index = (self.index + 1) % count
        self._show_frame()

    def _on_play(self, checked: bool) -> None:
        self.playing = checked
        self.play_button.setText(self.tr("Pause") if checked else self.tr("Play"))
        if checked:
            self._schedule()
        else:
            self.timer.stop()

    def interval_ms(self) -> int:
        anim = self.anim()
        if not anim or not anim["frames"]:
            return 100
        base = anim_edit.frame_duration_ms(anim, self.index % len(anim["frames"]))
        return max(1, round(base * 100 / self.speed.value()))

    def _schedule(self) -> None:
        self.timer.start(self.interval_ms())

    def _tick(self) -> None:
        anim = self.anim()
        if not anim or not anim["frames"]:
            return
        last = len(anim["frames"]) - 1
        if self.index >= last and not anim.get("loop", True):
            self.play_button.setChecked(False)  # a non-looping animation stops on its last frame
            return
        self.index = 0 if self.index >= last else self.index + 1
        self._show_frame()
        if self.playing:
            self._schedule()

    # ------------------------------------------------------------------ result

    def overrides(self) -> dict[str, Any]:
        """The facet overrides that apply the edits (empty when nothing changed)."""
        out: dict[str, Any] = {}
        changes = anim_edit.anim_overrides(self.original, self.animations)
        if changes:
            out["animations"] = changes
        if self.origin is not None and self.origin != self.original_origin:
            out["origin"] = list(self.origin)
        if self.frame != self.original_frame:
            out["frame"] = list(self.frame)
        return out

    def done(self, result: int) -> None:
        self.timer.stop()
        super().done(result)
