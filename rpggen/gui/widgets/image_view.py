"""A nearest-neighbor image view with Ctrl+wheel zoom and a grid overlay."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPen, QPixmap, QWheelEvent
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView, QWidget

MARGIN_TINT = QColor(255, 160, 0, 70)
GUTTER_TINT = QColor(0, 200, 255, 70)
LINE_COLOR = QColor(255, 255, 255, 150)


class ImageView(QGraphicsView):
    """Shows one image; Ctrl+wheel zooms. ``draw_grid`` overlays cell lines, the tinted margin
    area and the separation gutters."""

    def __init__(self, object_name: str = "imageView", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setScene(QGraphicsScene(self))
        self.setBackgroundBrush(QColor(60, 60, 60))
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.zoom = 1.0
        self.pixmap_item = None
        self.image_size = (0, 0)
        self.grid_items: list = []

    def set_image(self, path: Path | None, grid: dict | None = None, fit: bool = True) -> None:
        scene = self.scene()
        scene.clear()
        self.grid_items = []
        self.pixmap_item = None
        self.image_size = (0, 0)
        if path is None or not Path(path).exists():
            return
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return
        self.pixmap_item = scene.addPixmap(pixmap)  # smooth transformation stays off
        self.image_size = (pixmap.width(), pixmap.height())
        scene.setSceneRect(self.pixmap_item.boundingRect())
        if grid:
            self.draw_grid(grid)
        if fit:
            self.fit()

    def clear_grid(self) -> None:
        for item in self.grid_items:
            self.scene().removeItem(item)
        self.grid_items = []

    def draw_grid(self, grid: dict) -> None:
        self.clear_grid()
        width, height = self.image_size
        if not width:
            return
        scene = self.scene()
        line = QPen(LINE_COLOR)
        line.setCosmetic(True)
        none = QPen(Qt.PenStyle.NoPen)
        cw, ch = grid["cell"]
        mx, my = grid.get("margin", [0, 0])
        sx, sy = grid.get("separation", [0, 0])
        if cw < 1 or ch < 1:
            return
        tint = QBrush(MARGIN_TINT)
        for x, y, w, h in (
            (0, 0, width, my),
            (0, height - my, width, my),
            (0, 0, mx, height),
            (width - mx, 0, mx, height),
        ):
            if w > 0 and h > 0:
                self.grid_items.append(scene.addRect(x, y, w, h, none, tint))
        gutter = QBrush(GUTTER_TINT)
        x = mx + cw
        while sx and x < width - mx:
            self.grid_items.append(scene.addRect(x, my, sx, height - 2 * my, none, gutter))
            x += cw + sx
        y = my + ch
        while sy and y < height - my:
            self.grid_items.append(scene.addRect(mx, y, width - 2 * mx, sy, none, gutter))
            y += ch + sy
        x = mx
        while x <= width - mx:
            self.grid_items.append(scene.addLine(x, my, x, height - my, line))
            x += cw
            if sx:
                self.grid_items.append(scene.addLine(x, my, x, height - my, line))
                x += sx
        y = my
        while y <= height - my:
            self.grid_items.append(scene.addLine(mx, y, width - mx, y, line))
            y += ch
            if sy:
                self.grid_items.append(scene.addLine(mx, y, width - mx, y, line))
                y += sy

    def fit(self) -> None:
        if self.pixmap_item is None:
            return
        self.resetTransform()
        rect = self.pixmap_item.boundingRect()
        if rect.width() <= 0 or rect.height() <= 0:
            return
        view = self.viewport().size()
        scale = min(max(view.width(), 64) / rect.width(), max(view.height(), 64) / rect.height())
        scale = max(1.0, float(int(scale))) if scale >= 1 else scale
        self.zoom = scale
        self.scale(scale, scale)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.25 if event.angleDelta().y() > 0 else 0.8
            self.zoom *= factor
            self.scale(factor, factor)
            event.accept()
        else:
            super().wheelEvent(event)
