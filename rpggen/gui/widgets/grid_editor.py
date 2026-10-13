"""Modal grid editor: edit cell, margin and separation over a zoomable overlay; for a
picture of an isometric pack, the diamond it stands on and how many of them (T17.16)."""

from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import QPointF, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from rpggen.core import map_preview
from rpggen.core.analyzer import frames as frames_mod
from rpggen.core.analyzer import grid as grid_mod
from rpggen.core.analyzer import image_facts
from rpggen.errors import IssueList
from rpggen.gui import theme, workers
from rpggen.gui.widgets.image_view import ImageView

Grid = dict[str, list[int]]
RING_SIZE = 220  # the side of the heading ring, in the window's pixels


def _spin(name: str, low: int, high: int, value: int) -> QSpinBox:
    box = QSpinBox()
    box.setObjectName(name)
    box.setRange(low, high)
    box.setValue(value)
    return box


def detect_candidates(path: Path, *, callbacks) -> list[grid_mod.GridCandidate]:  # noqa: ANN001
    """Worker function: the top grid detections of an image (non-square allowed)."""
    a = image_facts.load_rgba(path)
    return grid_mod.detect_grid(a, image_facts.occupancy(a), square=False)


class HeadingRing(QWidget):
    """The views of a rotation sheet (T16.02) laid out in a ring, each where it points: the
    first one up or right, the next ones a step on, clockwise or not, as the sheet's
    ``heading_order`` says. A grid that cuts the sheet wrongly shows at once: the car does not
    turn evenly round the ring."""

    def __init__(self, sheet: QPixmap, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("headingRing")
        self.sheet = sheet
        self.headings = 0
        self.order = "up_cw"
        self.grid: Grid = {"cell": [16, 16], "margin": [0, 0], "separation": [0, 0]}
        self.setMinimumSize(RING_SIZE, RING_SIZE)

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt override
        return QSize(RING_SIZE, RING_SIZE)

    def set_ring(self, headings: int, order: str, grid: Grid) -> None:
        self.headings, self.order, self.grid = max(0, headings), order, grid
        self.setAccessibleName(self.tr("{0} headings in a ring").format(self.headings))
        self.update()

    def slot(self) -> float:
        """The side of the square a view is drawn in: as large as the ring allows."""
        radius = min(self.width(), self.height()) / 2
        if self.headings < 2:
            return radius
        # neighbours on a circle of radius r - s / 2 are 2 (r - s / 2) sin(pi / n) apart
        gap = math.sin(math.pi / self.headings)
        return max(4.0, 2 * radius * gap / (1 + gap) * 0.95)

    def positions(self) -> list[QPointF]:
        """Where the middle of each view lies, in the order of the sheet."""
        centre = QPointF(self.width() / 2, self.height() / 2)
        reach = min(self.width(), self.height()) / 2 - self.slot() / 2
        return [
            QPointF(centre.x() + reach * math.cos(a), centre.y() + reach * math.sin(a))
            for a in frames_mod.heading_angles(self.headings, self.order)
        ]

    def frame_rect(self, index: int) -> QRect:
        """The cell of view ``index`` on the sheet, row by row with the grid's gaps."""
        (cw, ch), (mx, my) = self.grid["cell"], self.grid.get("margin", [0, 0])
        sx, sy = self.grid.get("separation", [0, 0])
        cols = max(1, (self.sheet.width() - mx + sx) // max(1, cw + sx))
        return QRect(mx + (index % cols) * (cw + sx), my + (index // cols) * (ch + sy), cw, ch)

    def paintEvent(self, event) -> None:  # noqa: ANN001, N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        spots = self.positions()
        slot = self.slot()
        reach = min(self.width(), self.height()) / 2 - slot / 2
        centre = QPointF(self.width() / 2, self.height() / 2)
        painter.setPen(QPen(theme.color("border"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(centre, reach, reach)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        for index, spot in enumerate(spots):
            source = self.frame_rect(index)
            if not self.sheet.rect().contains(source):
                continue  # the grid has fewer cells than the sheet has headings
            scale = min(slot / source.width(), slot / source.height())
            if scale >= 1:
                scale = float(int(scale))
            width, height = source.width() * scale, source.height() * scale
            target = QRectF(spot.x() - width / 2, spot.y() - height / 2, width, height)
            painter.drawPixmap(target, self.sheet, QRectF(source))
        if spots:  # the first view: where the ring starts
            painter.setPen(QPen(theme.color("accent"), 2))
            painter.drawEllipse(spots[0], slot / 2, slot / 2)
        painter.end()


class GridEditorDialog(QDialog):
    def __init__(
        self,
        image_path: Path,
        grid: Grid | None,
        asset_label: str = "",
        parent: QWidget | None = None,
        *,
        headings: int = 0,
        heading_order: str = "up_cw",
        iso: dict | None = None,
    ) -> None:
        """``iso`` for a picture of an isometric pack (T17.16): ``footprint`` ([w, h], the
        diamond it stands on), ``origin`` ([x, y], the middle of that diamond in the picture),
        ``stands_on`` ([columns, rows] of an object; None for a tile) and ``has_grid`` (False
        for a single tile: it is one picture, and the square grid is not shown)."""
        super().__init__(parent)
        self.setObjectName("gridEditor")
        self.setWindowTitle(self.tr("Edit grid"))
        self.resize(900, 640)
        self.image_path = Path(image_path)
        self.asset_label = asset_label or self.image_path.name
        self.occupancy = image_facts.occupancy(image_facts.load_rgba(self.image_path))
        grid = grid or {"cell": [16, 16], "margin": [0, 0], "separation": [0, 0]}

        layout = QHBoxLayout(self)
        self.view = ImageView("gridView")
        layout.addWidget(self.view, 1)
        side = QVBoxLayout()
        layout.addLayout(side)
        form = QFormLayout()
        side.addLayout(form)
        cw, ch = grid["cell"]
        self.cell_w = _spin("cellW", 1, 1024, cw)
        self.cell_h = _spin("cellH", 1, 1024, ch)
        self.square = QCheckBox(self.tr("Square cells"))
        self.square.setObjectName("squareLock")
        self.square.setChecked(cw == ch)
        row = QHBoxLayout()
        row.addWidget(self.cell_w)
        row.addWidget(self.cell_h)
        row.addWidget(self.square)
        form.addRow(self.tr("Cell w / h"), row)
        mx, my = grid.get("margin", [0, 0])
        sx, sy = grid.get("separation", [0, 0])
        self.margin_x = _spin("marginX", 0, 1024, mx)
        self.margin_y = _spin("marginY", 0, 1024, my)
        self.sep_x = _spin("sepX", 0, 256, sx)
        self.sep_y = _spin("sepY", 0, 256, sy)
        for label, a, b in (
            (self.tr("Margin x / y"), self.margin_x, self.margin_y),
            (self.tr("Separation x / y"), self.sep_x, self.sep_y),
        ):
            box = QHBoxLayout()
            box.addWidget(a)
            box.addWidget(b)
            form.addRow(label, box)
        self.readout = QLabel()
        self.readout.setObjectName("gridReadout")
        self.warning = QLabel()
        self.warning.setObjectName("gridWarning")
        self.warning.setWordWrap(True)
        self.warning.setProperty("state", "warning")
        side.addWidget(self.readout)
        side.addWidget(self.warning)
        # a rotation sheet shows its views as the ring they make (T16.02)
        self.ring: HeadingRing | None = None
        self.headings, self.heading_order = headings, heading_order
        if headings > 0:
            self.ring_label = QLabel(
                self.tr("{0} headings, each where it points (the first is circled)").format(
                    headings
                )
            )
            self.ring_label.setObjectName("headingRingLabel")
            self.ring_label.setWordWrap(True)
            self.ring = HeadingRing(QPixmap(str(self.image_path)))
            side.addWidget(self.ring_label)
            side.addWidget(self.ring, 0, Qt.AlignmentFlag.AlignHCenter)
        # a picture of an isometric pack: the diamond it stands on, drawn over it (T17.16)
        self.iso = dict(iso) if iso else None
        self.has_grid = not self.iso or bool(self.iso.get("has_grid", True))
        if self.iso is not None:
            self._build_iso(form, side)
        self.candidates_label = QLabel(self.tr("Detected candidates"))
        side.addWidget(self.candidates_label)
        self.candidate_list = QListWidget()
        self.candidate_list.setObjectName("candidateList")
        side.addWidget(self.candidate_list, 1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Cancel
        )
        self.apply_button = buttons.button(QDialogButtonBox.StandardButton.Apply)
        self.apply_button.setObjectName("gridApply")
        buttons.clicked.connect(
            lambda b: self.accept() if b is self.apply_button else self.reject()
        )
        side.addWidget(buttons)

        self.view.set_image(self.image_path, None)
        for spin in (self.margin_x, self.margin_y, self.sep_x, self.sep_y, self.cell_h):
            spin.valueChanged.connect(self._on_changed)
        self.cell_w.valueChanged.connect(self._on_cell_w)
        self.square.toggled.connect(self._on_square)
        self.candidate_list.itemClicked.connect(self._on_candidate)
        self._candidates: list[grid_mod.GridCandidate] = []
        self._worker: workers.Worker | None = None
        if not self.has_grid:  # one tile a picture: there is no grid of cells to edit
            for index in range(form.rowCount()):
                form.setRowVisible(index, index in self._iso_rows)
            for widget in (self.readout, self.candidates_label, self.candidate_list):
                widget.setVisible(False)
        self._refresh()
        if self.has_grid:
            self._start_detection()

    # ------------------------------------------------------------------ isometric

    _iso_rows: tuple[int, ...] = ()

    def _build_iso(self, form: QFormLayout, side: QVBoxLayout) -> None:
        """The rows of an isometric picture: the diamond (a tile's can be edited; an object
        stands on its pack's) and, for an object, how many diamonds it stands on."""
        assert self.iso is not None
        fw, fh = (int(v) for v in self.iso.get("footprint") or (64, 32))
        stands = self.iso.get("stands_on")
        self.is_tile = stands is None
        self.diamond_w = _spin("diamondW", 2, 2048, fw)
        self.diamond_h = _spin("diamondH", 1, 2048, fh)
        tip = self.tr(
            "The diamond a tile of this pack stands on, in pixels (wide, high). Every tile of "
            "a project stands on the same one: a tile on another is left out of the tile set"
        )
        for box, name in (
            (self.diamond_w, self.tr("Diamond width")),
            (self.diamond_h, self.tr("Diamond height")),
        ):
            box.setToolTip(tip)
            box.setAccessibleName(name)
            box.setEnabled(self.is_tile)
            box.valueChanged.connect(self._refresh)
        row = QHBoxLayout()
        row.addWidget(self.diamond_w)
        row.addWidget(self.diamond_h)
        first = form.rowCount()
        form.addRow(self.tr("Diamond w / h"), row)
        columns, rows = (int(v) for v in (stands or (1, 1)))
        self.stands_columns = _spin("standsColumns", 1, 16, columns)
        self.stands_rows = _spin("standsRows", 1, 16, rows)
        stands_tip = self.tr(
            "How many diamonds this object stands on (columns, rows): it blocks them, and a "
            "building has its door before the middle of its front"
        )
        for box, name in (
            (self.stands_columns, self.tr("Stands on: columns")),
            (self.stands_rows, self.tr("Stands on: rows")),
        ):
            box.setToolTip(stands_tip)
            box.setAccessibleName(name)
            box.valueChanged.connect(self._refresh)
        if self.is_tile:
            self._iso_rows = (first,)
        else:
            stand_row = QHBoxLayout()
            stand_row.addWidget(self.stands_columns)
            stand_row.addWidget(self.stands_rows)
            form.addRow(self.tr("Stands on"), stand_row)
            self._iso_rows = (first, first + 1)
        self.iso_label = QLabel()
        self.iso_label.setObjectName("isoReadout")
        self.iso_label.setWordWrap(True)
        side.addWidget(self.iso_label)

    def iso_origin(self) -> tuple[float, float]:
        """The middle of the diamond nearest the camera, in the picture: the asset's origin,
        or the middle of the bottom of the picture less half a diamond when it has none."""
        assert self.iso is not None
        origin = self.iso.get("origin")
        if origin:
            return float(origin[0]), float(origin[1])
        width, height = self.view.image_size
        return width / 2.0, height - self.diamond_h.value() / 2.0

    def diamonds(self) -> list[list[list[float]]]:
        """The diamonds drawn over the picture (``map_preview.standing_diamonds``); empty for a
        picture that is not isometric."""
        if self.iso is None:
            return []
        columns = 1 if self.is_tile else self.stands_columns.value()
        rows = 1 if self.is_tile else self.stands_rows.value()
        return map_preview.standing_diamonds(
            self.iso_origin(), self.diamond_w.value(), self.diamond_h.value(), columns, rows
        )

    def iso_values(self) -> dict[str, list[int]]:
        """The overrides of an isometric picture that Apply writes: ``footprint`` of a tile
        and ``stands_on`` of an object, each only when it was changed."""
        if self.iso is None:
            return {}
        out: dict[str, list[int]] = {}
        footprint = [self.diamond_w.value(), self.diamond_h.value()]
        if self.is_tile and footprint != [int(v) for v in self.iso.get("footprint") or ()]:
            out["footprint"] = footprint
        stands = [self.stands_columns.value(), self.stands_rows.value()]
        if not self.is_tile and stands != [int(v) for v in self.iso.get("stands_on") or ()]:
            out["stands_on"] = stands
        return out

    # ------------------------------------------------------------------ values

    def grid(self) -> Grid:
        return {
            "cell": [self.cell_w.value(), self.cell_h.value()],
            "margin": [self.margin_x.value(), self.margin_y.value()],
            "separation": [self.sep_x.value(), self.sep_y.value()],
        }

    def set_grid(self, grid: Grid) -> None:
        widgets = (
            (self.cell_w, grid["cell"][0]),
            (self.cell_h, grid["cell"][1]),
            (self.margin_x, grid["margin"][0]),
            (self.margin_y, grid["margin"][1]),
            (self.sep_x, grid["separation"][0]),
            (self.sep_y, grid["separation"][1]),
        )
        for box, value in widgets:
            box.blockSignals(True)
            box.setValue(value)
            box.blockSignals(False)
        self.square.blockSignals(True)
        self.square.setChecked(grid["cell"][0] == grid["cell"][1])
        self.square.blockSignals(False)
        self._refresh()

    # ------------------------------------------------------------------ reacting

    def _on_cell_w(self) -> None:
        if self.square.isChecked():
            self.cell_h.blockSignals(True)
            self.cell_h.setValue(self.cell_w.value())
            self.cell_h.blockSignals(False)
        self._refresh()

    def _on_square(self, checked: bool) -> None:
        if checked:
            self.cell_h.blockSignals(True)
            self.cell_h.setValue(self.cell_w.value())
            self.cell_h.blockSignals(False)
        self._refresh()

    def _on_changed(self) -> None:
        self._refresh()

    def _refresh(self, *_args: object) -> None:
        grid = self.grid()
        if self.has_grid:
            self.view.draw_grid(grid)
        if self.iso is not None:
            found = self.diamonds()
            self.view.draw_diamonds(found)
            self.iso_label.setText(
                self.tr("A diamond of {0} × {1} px").format(
                    self.diamond_w.value(), self.diamond_h.value()
                )
                if self.is_tile
                else self.tr("Stands on {0} × {1} diamonds of {2} × {3} px").format(
                    self.stands_columns.value(),
                    self.stands_rows.value(),
                    self.diamond_w.value(),
                    self.diamond_h.value(),
                )
            )
        if self.ring is not None:
            self.ring.set_ring(self.headings, self.heading_order, grid)
        info = grid_mod.grid_readout(
            self.occupancy,
            (grid["cell"][0], grid["cell"][1]),
            (grid["margin"][0], grid["margin"][1]),
            (grid["separation"][0], grid["separation"][1]),
        )
        self.readout.setText(
            self.tr("{0} × {1}, {2} non-empty, remainder {3} px").format(
                info.cols, info.rows, info.nonempty, f"{info.remainder[0]}×{info.remainder[1]}"
            )
        )
        issues = IssueList()
        if info.remainder != (0, 0):
            issues.add(
                "ASSET-003",
                file=self.asset_label,
                remainder=f"{info.remainder[0]}×{info.remainder[1]}",
            )
        self.warning.setText("\n".join(f"{i.code}: {i.message} {i.fix}" for i in issues))
        self.warning.setVisible(bool(issues))
        self.readout_info = info

    def _start_detection(self) -> None:
        worker = workers.Worker(detect_candidates, self.image_path)
        worker.signals.finished.connect(self._show_candidates)
        self._worker = worker
        worker.start()

    def _show_candidates(self, candidates: list[grid_mod.GridCandidate]) -> None:
        self._candidates = list(candidates)
        self.candidate_list.clear()
        for cand in self._candidates[:5]:
            text = (
                f"{cand.cell[0]}×{cand.cell[1]}  margin {cand.margin[0]}  "
                f"gap {cand.separation[0]}  score {cand.score:.2f}"
            )
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, self._candidates.index(cand))
            self.candidate_list.addItem(item)

    def _on_candidate(self, item: QListWidgetItem) -> None:
        cand = self._candidates[item.data(Qt.ItemDataRole.UserRole)]
        self.set_grid(
            {
                "cell": list(cand.cell),
                "margin": list(cand.margin),
                "separation": list(cand.separation),
            }
        )
