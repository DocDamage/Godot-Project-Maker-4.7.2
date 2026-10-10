"""Animation preview and editor dialog."""

from __future__ import annotations

import contextlib
import copy
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen, QPixmap, QTransform
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
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
from rpggen.gui import theme
from rpggen.gui.widgets.image_view import ImageView

Anim = dict[str, Any]
PREVIEW_SCALE = 4
SPEED_MIN, SPEED_MAX = 25, 400  # percent


class AnimPlayer(QObject):
    """Steps through the frames of one animation at its own speed (fps or per-frame durations).
    Shared by the animation dialog and the audit page's detail panel (T13.03). ``source`` gives
    the animation to play each time it is asked, so an edit shows at the next frame."""

    frameChanged = Signal(int)  # noqa: N815 - the index of the frame now shown
    finished = Signal()  # a non-looping animation reached its last frame; playback stopped

    def __init__(self, source: Callable[[], Anim | None], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.source = source
        self.index = 0
        self.playing = False
        self.speed_percent = 100
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.tick)

    def count(self) -> int:
        anim = self.source()
        return len(anim["frames"]) if anim and anim.get("frames") else 0

    def interval_ms(self) -> int:
        anim = self.source()
        if not anim or not anim.get("frames"):
            return 100
        base = anim_edit.frame_duration_ms(anim, self.index % len(anim["frames"]))
        return max(1, round(base * 100 / max(1, self.speed_percent)))

    def set_playing(self, on: bool) -> None:
        self.playing = on
        if on:
            self.timer.start(self.interval_ms())
        else:
            self.timer.stop()

    def restart(self) -> None:
        """Another animation: back to its first frame, still playing if it was."""
        self.index = 0
        if self.playing:
            self.timer.start(self.interval_ms())

    def step(self) -> None:
        """One frame forward, wrapping around (the Step button)."""
        count = self.count()
        if count:
            self.index = (self.index + 1) % count
            self.frameChanged.emit(self.index)

    def tick(self) -> None:
        """What the timer does when a frame's time is up (tests call it as their clock)."""
        anim = self.source()
        count = self.count()
        if not anim or not count:
            return
        last = count - 1
        if self.index >= last and not anim.get("loop", True):
            self.set_playing(False)  # a non-looping animation stops on its last frame
            self.finished.emit()
            return
        self.index = 0 if self.index >= last else self.index + 1
        self.frameChanged.emit(self.index)
        if self.playing:
            self.timer.start(self.interval_ms())


class FramePreview(QWidget):
    """One animation frame scaled with nearest-neighbor; click to place the origin."""

    originPicked = Signal(int, int)  # noqa: N815 - frame pixel coordinates

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("framePreview")
        self.pixmap: QPixmap | None = None
        self.origin: tuple[int, int] | None = None
        self.scale = PREVIEW_SCALE
        theme.signals.changed.connect(lambda _name: self._repaint())
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

    def _repaint(self) -> None:
        with contextlib.suppress(RuntimeError):  # the widget was deleted
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
        painter.fillRect(self.rect(), theme.token("canvas_bg_alt"))
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
        self.frame: tuple[int, int] = (frame[0], frame[1])
        self.original_frame = tuple(frame)
        self.origin: tuple[int, int] | None = (origin[0], origin[1]) if origin else None
        self.original_origin = self.origin
        self.grid = grid or {"cell": list(frame), "margin": [0, 0], "separation": [0, 0]}
        self.arpg = arpg
        self.sheet_resolver = sheet_resolver or (lambda source: None)
        self.current: str | None = None
        self.player = AnimPlayer(self.anim, self)
        self.timer = self.player.timer
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
        self.rename_button = QToolButton()
        self.rename_button.setObjectName("renameAnimButton")
        self.rename_button.setText(self.tr("Rename…"))
        self.rename_button.setToolTip(
            self.tr("Give the selected animation its name: walk_down, attack_left, …")
        )
        self.rename_button.clicked.connect(self._on_rename)
        row.addWidget(self.add_button)
        row.addWidget(self.mirror_button)
        row.addWidget(self.rename_button)
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

        self.player.frameChanged.connect(lambda _index: self._show_frame())
        self.player.finished.connect(lambda: self.play_button.setChecked(False))
        self.speed.valueChanged.connect(self._on_speed)

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
            add.addAction(name, partial(self.add_animation, name))
        self.add_button.setMenu(add)
        mirror = QMenu(self.mirror_button)
        for name in self.animations:
            target = anim_edit.mirror_name(name)
            if target:
                mirror.addAction(f"{name} → {target}", partial(self.mirror_from, name, target))
        self.mirror_button.setMenu(mirror)

    def names(self) -> list[str]:
        return list(self.animations)

    def select(self, name: str) -> None:
        top = (self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount()))
        stack = [item for item in top if item is not None]
        while stack:
            item = stack.pop()
            if item.data(0, Qt.ItemDataRole.UserRole) == name:
                self.tree.setCurrentItem(item)
                return
            kids = (item.child(i) for i in range(item.childCount()))
            stack.extend(kid for kid in kids if kid is not None)

    def _on_item(self, item: QTreeWidgetItem | None) -> None:
        name = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        self.current = name
        self.player.restart()
        self._load_fields()
        self._show_frame()

    # ------------------------------------------------------------------ editing

    def anim(self) -> Anim | None:
        return self.animations.get(self.current) if self.current else None

    def _replace(self, change) -> None:  # noqa: ANN001
        anim = self.anim()
        if anim is not None and self.current is not None:
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
        anim = self.anim()
        if anim is not None:
            anim["fps"] = value

    def _on_loop(self, checked: bool) -> None:
        anim = self.anim()
        if anim is not None:
            anim["loop"] = checked

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

    def ask_name(self, current: str) -> str | None:  # overridden by tests
        """Ask for the new name of ``current``: the names the game plays are offered, any
        other can be typed. None when the question was cancelled."""
        text, ok = QInputDialog.getItem(
            self,
            self.tr("Rename animation"),
            self.tr("The new name of {0}:").format(current),
            anim_edit.offered_names(self.animations),
            0,
            True,
        )
        return text if ok else None

    def _on_rename(self) -> None:
        item = self.tree.currentItem()
        current = item.data(0, Qt.ItemDataRole.UserRole) if item is not None else None
        if not current:
            return
        typed = self.ask_name(str(current))
        if typed is not None:
            self.rename_animation(str(current), typed)

    def rename_animation(self, old: str, typed: str) -> bool:
        """Call the animation ``old`` what was typed (cleaned to a name). False, with nothing
        changed, when that is no name or another animation has it."""
        new = anim_edit.clean_name(typed)
        changed = anim_edit.renamed(self.animations, old, new)
        if not new or new == old or changed is self.animations:
            return False
        self.animations = changed
        self._rebuild_tree(keep=new)
        self._rebuild_menus()
        return True

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
        if self.current is None:
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

    # the player keeps the frame and whether it plays; the dialog's own names stay as they were
    @property
    def index(self) -> int:
        return self.player.index

    @index.setter
    def index(self, value: int) -> None:
        self.player.index = value

    @property
    def playing(self) -> bool:
        return self.player.playing

    def step(self) -> None:
        self.player.step()

    def _on_play(self, checked: bool) -> None:
        self.play_button.setText(self.tr("Pause") if checked else self.tr("Play"))
        self.player.set_playing(checked)

    def _on_speed(self, percent: int) -> None:
        self.player.speed_percent = percent

    def interval_ms(self) -> int:
        self.player.speed_percent = self.speed.value()
        return self.player.interval_ms()

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
