"""The starter map preview of the Options page (T11.26): a picture of what the options will
produce, drawn from the same planner as the generator, with a Reroll button."""

from __future__ import annotations

import io
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from rpggen.core import map_preview
from rpggen.core.orchestrator import Callbacks
from rpggen.gui import theme, thumbnails, workers
from rpggen.gui.widgets.flow_layout import FlowLayout

DEBOUNCE_MS = 200


def render_png(
    catalog: Any,
    resolver: Callable[[Any], Any],
    options: dict[str, Any],
    seed: int,
    archetype: str,
    ground_id: str,
    building_id: str,
    scale: int,
    *,
    callbacks: Callbacks,
) -> tuple[bytes, list[str]]:
    """Worker function: (PNG bytes of the preview, the planner's warnings)."""
    art = map_preview.load_art(catalog, resolver, ground_id, building_id)
    plan = map_preview.plan(options, seed, map_preview.building_info(art), archetype)
    image = map_preview.render(plan, art, scale)
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue(), list(plan["warnings"])


class MapPreviewWidget(QWidget):
    """Shows the preview; ``request`` renders it in a worker after a short pause (200 ms) so that
    typing in a spin box does not start a render per key."""

    rerollRequested = Signal()  # noqa: N815
    rendered = Signal()

    MARKER_NAMES = {
        "spawn": "start",
        "npc": "villager",
        "enemy": "enemy",
        "chest": "chest",
        "exit": "east exit",
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("mapPreview")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.image_label = QLabel()
        self.image_label.setObjectName("mapPreviewImage")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(QSize(240, 140))
        self.image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.image_label)
        # the legend is made of widgets (a dot and a name each), so it stays legible at any size
        # and is translated; the picture itself carries no text
        self.legend_box = QWidget()
        self.legend_box.setObjectName("mapLegend")
        legend = FlowLayout(self.legend_box, spacing=10)
        self.legend_labels: dict[str, QLabel] = {}
        self.legend_dots: dict[str, QLabel] = {}
        for kind in map_preview.MARKER_ORDER:
            item = QWidget()
            row = QHBoxLayout(item)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(4)
            r, g, b = map_preview.MARKER_COLORS[kind]
            dot = QLabel()
            dot.setObjectName(f"legendDot_{kind}")
            dot.setFixedSize(10, 10)
            dot.setStyleSheet(
                f"background: rgb({r},{g},{b}); border: 1px solid black; border-radius: 5px;"
            )
            label = QLabel(self.tr(self.MARKER_NAMES[kind]))
            label.setObjectName(f"legend_{kind}")
            row.addWidget(dot)
            row.addWidget(label)
            legend.addWidget(item)
            self.legend_dots[kind] = dot
            self.legend_labels[kind] = label
        layout.addWidget(self.legend_box)
        self.note_label = QLabel()
        self.note_label.setObjectName("mapPreviewNote")
        self.note_label.setWordWrap(True)
        self.note_label.setProperty("muted", True)
        layout.addWidget(self.note_label)
        self.reroll_button = QPushButton(self.tr("Reroll"))
        self.reroll_button.setObjectName("rerollButton")
        self.reroll_button.setToolTip(
            self.tr("Try another arrangement: picks a new seed (see Advanced)")
        )
        self.reroll_button.clicked.connect(self.rerollRequested)
        layout.addWidget(self.reroll_button, 0, Qt.AlignmentFlag.AlignLeft)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(DEBOUNCE_MS)
        self._timer.timeout.connect(self._start)
        self._job: tuple[Any, ...] | None = None
        self._generation = 0
        self._worker: workers.Worker | None = None
        self.pixmap_size = QSize()
        self.warnings: list[str] = []
        self.last_png = b""
        self._pixmap = QPixmap()

    def set_disabled(self, reason: str) -> None:
        """Greys the preview out (the starter map already exists)."""
        self._timer.stop()
        self._generation += 1
        self.reroll_button.setEnabled(False)
        self.note_label.setText(reason)
        self.image_label.setEnabled(False)

    def request(self, *job: Any) -> None:
        """Render soon: (catalog, resolver, options, seed, archetype, ground_id, building_id)."""
        self.reroll_button.setEnabled(True)
        self.image_label.setEnabled(True)
        self._job = job
        self._timer.start()

    def flush(self) -> None:
        """Render now (tests, and when the page is shown)."""
        if self._timer.isActive():
            self._timer.stop()
            self._start()

    def _start(self) -> None:
        if self._job is None:
            return
        self._generation += 1
        generation = self._generation
        catalog, resolver, options, seed, archetype, ground_id, building_id = self._job
        worker = workers.Worker(
            render_png,
            catalog,
            resolver,
            dict(options),
            seed,
            archetype,
            ground_id,
            building_id,
            2,
        )

        def done(result: tuple[bytes, list[str]]) -> None:
            if generation != self._generation:
                return  # an older render finished after a newer one was asked for
            png, warnings = result
            try:
                self.image_label.objectName()  # the widget may be gone (the page was closed)
            except RuntimeError:
                return
            self.last_png = png
            self.warnings = warnings
            self._pixmap = thumbnails.pixmap_from_bytes(png)
            self._fit()
            self.note_label.setText(
                self.tr("Preview: the generated map can differ in tile details.")
                + ("  " + "; ".join(warnings) if warnings else "")
            )
            self.rendered.emit()

        def failed(error: object) -> None:
            if generation == self._generation:
                self.note_label.setText(
                    self.tr("The preview could not be drawn: {0}").format(error)
                )

        worker.signals.finished.connect(done)
        worker.signals.failed.connect(failed)
        self._worker = worker  # keep it alive until its signals are delivered
        worker.start()

    def _fit(self) -> None:
        if self._pixmap.isNull():
            return
        width = max(240, self.image_label.width())
        ratio = self.devicePixelRatioF()
        shown = self._pixmap.scaledToWidth(
            theme.device_size(width, ratio), Qt.TransformationMode.FastTransformation
        )
        shown.setDevicePixelRatio(ratio)  # as many device pixels as the label has (T13.10)
        self.image_label.setPixmap(shown)
        self.pixmap_size = self._pixmap.size()

    def resizeEvent(self, event) -> None:  # noqa: ANN001, N802
        super().resizeEvent(event)
        self._fit()
