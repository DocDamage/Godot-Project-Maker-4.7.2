"""Audit → Make variant…: a recoloured copy of a sprite as an asset of its own (T13.18)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image
from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QColorDialog,
    QDial,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSlider,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from rpggen.core import catalog as catalog_mod
from rpggen.core import variants

PREVIEW_PX = 220
Rgb = tuple[int, int, int]


def to_pixmap(image: Image.Image) -> QPixmap:
    rgba = image.convert("RGBA")
    data = rgba.tobytes("raw", "RGBA")
    picture = QImage(data, rgba.width, rgba.height, 4 * rgba.width, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(picture.copy())


class PictureLabel(QLabel):
    """A picture scaled up with hard pixels; a click says which pixel of the picture was hit."""

    pixelClicked = Signal(int, int)  # noqa: N815

    def __init__(self, name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName(name)
        self.setFixedSize(PREVIEW_PX, PREVIEW_PX)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFrameShape(QLabel.Shape.StyledPanel)
        self.picture_size = (1, 1)
        self.scale = 1.0

    def show_image(self, image: Image.Image) -> None:
        self.picture_size = image.size
        self.scale = min(PREVIEW_PX / image.width, PREVIEW_PX / image.height)
        if self.scale >= 1.0:
            self.scale = float(max(1, int(self.scale)))  # whole pixels when it is enlarged
        width = max(1, round(image.width * self.scale))
        height = max(1, round(image.height * self.scale))
        self.setPixmap(
            to_pixmap(image).scaled(
                width,
                height,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
        )

    def pixel_at(self, pos: QPoint) -> tuple[int, int] | None:
        width = round(self.picture_size[0] * self.scale)
        height = round(self.picture_size[1] * self.scale)
        left, top = (self.width() - width) // 2, (self.height() - height) // 2
        x, y = int((pos.x() - left) / self.scale), int((pos.y() - top) / self.scale)
        inside = 0 <= x < self.picture_size[0] and 0 <= y < self.picture_size[1]
        return (x, y) if inside and pos.x() >= left and pos.y() >= top else None

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        hit = self.pixel_at(event.position().toPoint())
        if hit is not None:
            self.pixelClicked.emit(*hit)
        super().mousePressEvent(event)


class VariantDialog(QDialog):
    """The source and the result side by side; a hue wheel with saturation and value, or a
    palette table (click a colour of the source to find its row, double-click a row to choose
    what it becomes); a name; and for an enemy or a boss the stats multipliers.
    ``definition()`` is what the catalog stores."""

    def __init__(
        self,
        catalog: catalog_mod.Catalog,
        source: catalog_mod.Asset,
        source_file: Path,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("variantDialog")
        self.setWindowTitle(self.tr("Make a variant"))
        self.catalog = catalog
        self.source = source
        with Image.open(source_file) as opened:
            self.image = opened.convert("RGBA")
        self.palette_map: dict[Rgb, Rgb] = {}
        layout = QVBoxLayout(self)

        pictures = QHBoxLayout()
        self.source_view = PictureLabel("variantSource")
        self.source_view.setToolTip(self.tr("The source. Click a colour to find it in the table."))
        self.result_view = PictureLabel("variantResult")
        for title, view in (
            (self.tr("Source"), self.source_view),
            (self.tr("Variant"), self.result_view),
        ):
            column = QVBoxLayout()
            column.addWidget(QLabel(title))
            column.addWidget(view)
            pictures.addLayout(column)
        layout.addLayout(pictures)
        self.source_view.show_image(self.image)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("variantTabs")
        hue_page = QWidget()
        hue_form = QFormLayout(hue_page)
        self.hue_dial = QDial()
        self.hue_dial.setObjectName("variantHue")
        self.hue_dial.setRange(0, 359)
        self.hue_dial.setWrapping(True)
        self.hue_dial.setNotchesVisible(True)
        self.hue_dial.setAccessibleName(self.tr("Hue shift in degrees"))
        self.hue_dial.setToolTip(self.tr("Turn every colour around the colour wheel"))
        self.hue_label = QLabel()
        hue_row = QHBoxLayout()
        hue_row.addWidget(self.hue_dial)
        hue_row.addWidget(self.hue_label, 1)
        hue_form.addRow(self.tr("Hue"), hue_row)
        self.saturation_slider = self._percent_slider("variantSaturation", self.tr("Saturation"))
        self.value_slider = self._percent_slider("variantValue", self.tr("Brightness"))
        hue_form.addRow(self.tr("Saturation"), self.saturation_slider)
        hue_form.addRow(self.tr("Brightness"), self.value_slider)
        self.tabs.addTab(hue_page, self.tr("Hue"))

        self.table = QTableWidget(0, 2)
        self.table.setObjectName("variantPalette")
        self.table.setHorizontalHeaderLabels([self.tr("Colour"), self.tr("Becomes")])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setToolTip(self.tr("Double-click a row to choose what the colour becomes"))
        self.colours = variants.palette_of(self.image)
        self.table.setRowCount(len(self.colours))
        for row in range(len(self.colours)):
            self._fill_row(row)
        self.tabs.addTab(self.table, self.tr("Palette"))
        layout.addWidget(self.tabs, 1)

        form = QFormLayout()
        self.name_edit = QLineEdit(self._default_name())
        self.name_edit.setObjectName("variantName")
        self.name_edit.setPlaceholderText(self.tr("Fire slime"))
        form.addRow(self.tr("Name"), self.name_edit)
        layout.addLayout(form)

        self.stats_box = QGroupBox(self.tr("Stats of the enemy, as multiples of the source's"))
        self.stats_box.setObjectName("variantStats")
        stats_row = QHBoxLayout(self.stats_box)
        self.stat_spins: dict[str, QDoubleSpinBox] = {}
        stat_labels = {
            "hp": self.tr("HP"),
            "attack": self.tr("Attack"),
            "xp": self.tr("XP"),
            "gold": self.tr("Gold"),
        }
        for key in variants.STAT_KEYS:
            spin = QDoubleSpinBox()
            spin.setObjectName(f"variantStat_{key}")
            spin.setRange(0.1, 20.0)
            spin.setSingleStep(0.1)
            spin.setDecimals(1)
            spin.setValue(1.0)
            spin.setPrefix("× ")
            spin.setAccessibleName(stat_labels[key])
            stats_row.addWidget(QLabel(stat_labels[key]))
            stats_row.addWidget(spin)
            self.stat_spins[key] = spin
        self.stats_box.setVisible(variants.stats_apply(source))
        layout.addWidget(self.stats_box)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.ok_button.setObjectName("variantOk")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.hue_dial.valueChanged.connect(lambda _v: self._refresh())
        self.saturation_slider.valueChanged.connect(lambda _v: self._refresh())
        self.value_slider.valueChanged.connect(lambda _v: self._refresh())
        self.tabs.currentChanged.connect(lambda _i: self._refresh())
        self.name_edit.textChanged.connect(lambda _t: self._refresh())
        self.table.cellDoubleClicked.connect(lambda row, _col: self.pick_colour(row))
        self.source_view.pixelClicked.connect(self.eyedrop)
        self._refresh()

    # ------------------------------------------------------------------ parts

    def _percent_slider(self, name: str, label: str) -> QSlider:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setObjectName(name)
        slider.setRange(0, 200)
        slider.setValue(100)
        slider.setAccessibleName(label)
        slider.setToolTip(self.tr("100 leaves it as it is"))
        return slider

    def _default_name(self) -> str:
        stem = self.source.path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        return self.tr("{0} variant").format(stem.replace("_", " ").capitalize())

    def _fill_row(self, row: int) -> None:
        colour = self.colours[row]
        target = self.palette_map.get(colour, colour)
        for column, rgb in enumerate((colour, target)):
            item = QTableWidgetItem("#{:02x}{:02x}{:02x}".format(*rgb))
            item.setBackground(QColor(*rgb))
            item.setForeground(QColor("black" if sum(rgb) > 380 else "white"))
            self.table.setItem(row, column, item)

    # ------------------------------------------------------------------ the definition

    def op(self) -> str:
        return "palette" if self.tabs.currentWidget() is self.table else "hue"

    def params(self) -> dict[str, Any]:
        if self.op() == "palette":
            pairs = [[list(old), list(new)] for old, new in self.palette_map.items() if old != new]
            return {"map": sorted(pairs)}
        return {
            "shift": self.hue_dial.value(),
            "saturation": self.saturation_slider.value() / 100.0,
            "value": self.value_slider.value() / 100.0,
        }

    def stats(self) -> dict[str, float]:
        if self.stats_box.isHidden():
            return {}
        return {key: round(spin.value(), 2) for key, spin in self.stat_spins.items()}

    def definition(self) -> dict[str, Any]:
        """What the catalog stores (already in its canonical form)."""
        name = self.name_edit.text().strip()
        taken = {a.id for a in self.catalog.assets} | {
            str(v.get("id")) for v in self.catalog.variants
        }
        raw: dict[str, Any] = {
            "id": variants.new_id(taken, self.source.pack_id, name),
            "source": self.source.id,
            "name": name,
            "op": self.op(),
            "params": self.params(),
        }
        if self.stats():
            raw["stats"] = self.stats()
        return variants.normalized(raw)

    # ------------------------------------------------------------------ actions

    def set_colour(self, row: int, rgb: Rgb) -> None:
        """The colour of ``row`` becomes ``rgb`` in the variant."""
        self.palette_map[self.colours[row]] = rgb
        self._fill_row(row)
        self._refresh()

    def choose_colour(self, start: Rgb) -> Rgb | None:  # overridden by tests
        chosen = QColorDialog.getColor(QColor(*start), self, self.tr("Becomes"))
        return (chosen.red(), chosen.green(), chosen.blue()) if chosen.isValid() else None

    def pick_colour(self, row: int) -> None:
        colour = self.colours[row]
        chosen = self.choose_colour(self.palette_map.get(colour, colour))
        if chosen is not None:
            self.set_colour(row, chosen)

    def eyedrop(self, x: int, y: int) -> int | None:
        """The row of the source's colour at (x, y): selected, and the Palette tab shown."""
        pixel = self.image.getpixel((x, y))
        assert isinstance(pixel, tuple)  # an RGBA image
        r, g, b, alpha = pixel
        if alpha == 0 or (r, g, b) not in self.colours:
            return None
        row = self.colours.index((r, g, b))
        self.tabs.setCurrentWidget(self.table)
        self.table.selectRow(row)
        return row

    def _refresh(self) -> None:
        self.hue_label.setText(self.tr("{0}°").format(self.hue_dial.value()))
        self.result_image = variants.render(self.image, self.op(), self.params())
        self.result_view.show_image(self.result_image)
        self.ok_button.setEnabled(bool(self.name_edit.text().strip()))
