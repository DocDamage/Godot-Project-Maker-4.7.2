"""The Options page's summary card (T12.37): what the project will be, from the current options."""

from __future__ import annotations

from PySide6.QtWidgets import QGroupBox, QLabel, QVBoxLayout, QWidget

from rpggen.core import options
from rpggen.gui.widgets.flow_layout import FlowLayout


def format_estimate(seconds: float) -> str:
    """ "about 40 s", "about 3 min": a rounded figure, never a false precision."""
    if seconds < 90:
        return f"{max(5, round(seconds / 5) * 5)} s"
    return f"{round(seconds / 60)} min"


def format_bytes(size: int) -> str:
    megabytes = size / (1024 * 1024)
    if megabytes < 1:
        return f"{max(1, round(size / 1024))} KB"
    if megabytes < 10:
        return f"{megabytes:.1f} MB"
    if megabytes < 1024:
        return f"{round(megabytes)} MB"
    return f"{megabytes / 1024:.1f} GB"


ARCHETYPE_NAMES = {
    "turn_based": "Turn-based RPG",
    "arpg": "Action RPG",
    "metroidvania": "Metroidvania",
}


class OptionsSummary(QGroupBox):
    """Archetype, maps, the systems that are on (chips), tile size and view, and two estimates."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(self.tr("Summary"), parent)
        self.setObjectName("optionsSummary")
        outer = QVBoxLayout(self)
        self.archetype_label = self._line("summaryArchetype")
        self.maps_label = self._line("summaryMaps")
        self.tiles_label = self._line("summaryTiles")
        for label in (self.archetype_label, self.maps_label, self.tiles_label):
            outer.addWidget(label)
        self.chip_box = QWidget()
        self.chip_box.setObjectName("summaryChips")
        self.chip_flow = FlowLayout(self.chip_box)
        outer.addWidget(self.chip_box)
        self.chips: list[QLabel] = []
        self.time_label = self._line("summaryTime")
        self.size_label = self._line("summarySize")
        outer.addWidget(self.time_label)
        outer.addWidget(self.size_label)

    def _line(self, name: str) -> QLabel:
        label = QLabel()
        label.setObjectName(name)
        label.setWordWrap(True)
        return label

    def set_summary(
        self,
        summary: options.Summary,
        seconds: float | None,
        size_bytes: int | None,
    ) -> None:
        self.archetype_label.setText(
            "<b>" + self.tr(ARCHETYPE_NAMES.get(summary.archetype, summary.archetype)) + "</b>"
        )
        maps = [self.tr(m) if not m[0].isdigit() else self._interiors(m) for m in summary.maps]
        if summary.archetype == "metroidvania":
            self.maps_label.setText(
                self.tr("World: {0}").format(summary.world)
                if summary.world
                else self.tr("The world options do not fit together")
            )
        else:
            self.maps_label.setText(
                self.tr("Maps: {0}").format(", ".join(maps)) if maps else self.tr("No starter maps")
            )
        self.tiles_label.setText(
            self.tr("{0} px tiles, {1}").format(summary.tile_size, summary.tiles.lstrip("≈ "))
        )
        for chip in self.chips:
            self.chip_flow.removeWidget(chip)
            chip.deleteLater()
        self.chips = []
        for name in summary.systems:
            chip = QLabel(self.tr(name))
            chip.setObjectName("summaryChip")
            chip.setProperty("chip", True)
            chip.setStyleSheet(
                "QLabel#summaryChip { border: 1px solid #6b7280; border-radius: 9px;"
                " padding: 1px 8px; }"
            )
            self.chip_flow.addWidget(chip)
            self.chips.append(chip)
        self.chip_box.updateGeometry()
        self.time_label.setVisible(seconds is not None)
        if seconds is not None:
            self.time_label.setText(
                self.tr("Generation time: about {0}").format(format_estimate(seconds))
            )
        self.size_label.setVisible(size_bytes is not None)
        if size_bytes is not None:
            self.size_label.setText(
                self.tr("Project size: about {0}").format(format_bytes(size_bytes))
            )

    def _interiors(self, text: str) -> str:
        """ "1 interior", "3 interiors" or "2 imported maps": a map count with its noun."""
        count = int(text.split()[0])
        if text.split()[1].startswith("imported"):
            return (
                self.tr("{0} imported map").format(count)
                if count == 1
                else self.tr("{0} imported maps").format(count)
            )
        return (
            self.tr("{0} interior").format(count)
            if count == 1
            else self.tr("{0} interiors").format(count)
        )
