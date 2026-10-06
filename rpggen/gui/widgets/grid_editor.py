"""Modal grid editor: edit cell, margin and separation over a zoomable overlay."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
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

from rpggen.core.analyzer import grid as grid_mod
from rpggen.core.analyzer import image_facts
from rpggen.errors import IssueList
from rpggen.gui import workers
from rpggen.gui.widgets.image_view import ImageView

Grid = dict[str, list[int]]


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


class GridEditorDialog(QDialog):
    def __init__(
        self,
        image_path: Path,
        grid: Grid | None,
        asset_label: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("gridEditor")
        self.setWindowTitle(self.tr("Edit grid"))
        self.resize(900, 640)
        self.image_path = Path(image_path)
        self.asset_label = asset_label or self.image_path.name
        self.mask = image_facts.occupancy(image_facts.load_rgba(self.image_path))
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
        for box in (self.margin_x, self.margin_y, self.sep_x, self.sep_y, self.cell_h):
            box.valueChanged.connect(self._on_changed)
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
        info = grid_mod.grid_readout(
            self.mask, tuple(grid["cell"]), tuple(grid["margin"]), tuple(grid["separation"])
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
