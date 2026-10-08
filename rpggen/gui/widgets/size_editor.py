"""A preset combo with width and height spin boxes."""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QSpinBox, QWidget

from rpggen.core import options


def spin(low: int, high: int) -> QSpinBox:
    box = QSpinBox()
    box.setRange(low, high)
    return box


class SizeEditor(QWidget):
    """A preset combo plus width / height spin boxes that are enabled for Custom."""

    def __init__(
        self,
        name: str,
        presets: list[tuple[int, int]],
        low: int,
        high: int,
        names: dict[tuple[int, int], str] | None = None,
    ) -> None:
        super().__init__()
        self.presets = presets
        self._labels: list[str] = []
        self.combo = QComboBox()
        self.combo.setObjectName(f"{name}Combo")
        for w, h in presets:
            label = f"{w} × {h}"
            if names and (w, h) in names:
                label = f"{self.tr(names[(w, h)])} {label}"
            self._labels.append(label)
            self.combo.addItem(label, (w, h))
        self.combo.addItem(self.tr("Custom"), None)
        self.width_box = spin(low, high)
        self.width_box.setObjectName(f"{name}Width")
        self.height_box = spin(low, high)
        self.height_box.setObjectName(f"{name}Height")
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.combo)
        row.addWidget(self.width_box)
        row.addWidget(QLabel("×"))
        row.addWidget(self.height_box)
        row.addStretch(1)
        self.combo.currentIndexChanged.connect(self._on_combo)

    def _on_combo(self, _index: int) -> None:
        value = self.combo.currentData()
        custom = value is None
        self.width_box.setEnabled(custom)
        self.height_box.setEnabled(custom)
        if value is not None:
            self.width_box.setValue(value[0])
            self.height_box.setValue(value[1])

    def mark_suggested(self, preset: tuple[int, int] | None) -> None:
        """Adds "(suggested)" to the label of ``preset`` (and takes it off the others)."""
        for index, (label, item) in enumerate(zip(self._labels, self.presets, strict=True)):
            suffix = " " + self.tr("(suggested)") if item == preset else ""
            self.combo.setItemText(index, label + suffix)

    def value(self) -> tuple[int, int]:
        return (self.width_box.value(), self.height_box.value())

    def set_value(self, value: tuple[int, int]) -> None:
        self.width_box.setValue(value[0])
        self.height_box.setValue(value[1])
        index = options.preset_index(self.presets, value)
        self.combo.setCurrentIndex(index)
        self._on_combo(index)
