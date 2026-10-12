"""Modal grid editor: edit cell, margin and separation over a zoomable overlay."""

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
    ) -> None:
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
        side.addWidget(QLabel(self.tr("Detected candidates")))
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
        self._refresh()
        self._start_detection()

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

    def _refresh(self) -> None:
        grid = self.grid()
        self.view.draw_grid(grid)
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
