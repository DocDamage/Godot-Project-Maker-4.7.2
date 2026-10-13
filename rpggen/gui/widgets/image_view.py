"""A nearest-neighbor image view with Ctrl+wheel zoom and a grid overlay."""

from __future__ import annotations

import contextlib
from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QMouseEvent, QPen, QPixmap, QPolygonF, QWheelEvent
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QGraphicsView, QWidget

from rpggen.gui import theme

MARGIN_TINT = QColor(255, 160, 0, 70)
GUTTER_TINT = QColor(0, 200, 255, 70)
# Marks over the picture (T13.03), as ``(kind, x, y, w, h)`` in image pixels: the footprint of
# an object, its origin (a cross at x, y), the frames of an animation where the attack hits,
# and the frame the transport is on.
MARK_FOOTPRINT = "footprint"
MARK_ORIGIN = "origin"
MARK_ACTIVE = "active"
MARK_CURRENT = "current"
Mark = tuple[str, float, float, float, float]
FOOTPRINT_TINT = QColor(0, 200, 255, 60)
FOOTPRINT_LINE = QColor(0, 200, 255)
ORIGIN_LINE = QColor(255, 64, 160)
ACTIVE_TINT = QColor(255, 48, 48, 80)
CURRENT_LINE = QColor(255, 220, 0)


class ImageView(QGraphicsView):
    """Shows one image; Ctrl+wheel zooms. ``draw_grid`` overlays cell lines, the tinted margin
    area and the separation gutters."""

    clicked = Signal(float, float)  # image pixel position of a click (not a drag)

    def __init__(self, object_name: str = "imageView", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._press: QPoint | None = None
        self.setObjectName(object_name)
        self.setScene(QGraphicsScene(self))
        self._grid: dict | None = None
        self.setBackgroundBrush(theme.token("canvas_bg"))
        theme.signals.changed.connect(self._on_theme_changed)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.zoom = 1.0
        self.pixmap_item: QGraphicsPixmapItem | None = None
        self.image_size = (0, 0)
        self.grid_items: list = []
        self.mark_items: list = []
        self.marks: list[Mark] = []
        self.diamond_items: list = []
        self.diamonds: list[list[list[float]]] = []

    def set_image(self, path: Path | None, grid: dict | None = None, fit: bool = True) -> None:
        if path is None or not Path(path).exists():
            self.set_pixmap(None)
            return
        self.set_pixmap(QPixmap(str(path)), grid, fit)

    def set_pixmap(
        self, pixmap: QPixmap | None, grid: dict | None = None, fit: bool = True
    ) -> None:
        """Show a picture that is already loaded (one frame of an animation, say)."""
        scene = self.scene()
        scene.clear()
        self.grid_items = []
        self.mark_items = []
        self.marks = []
        self.diamond_items = []
        self.diamonds = []
        self._grid = None
        self.pixmap_item = None
        self.image_size = (0, 0)
        if pixmap is None or pixmap.isNull():
            return
        item = scene.addPixmap(pixmap)  # smooth transformation stays off
        self.pixmap_item = item
        self.image_size = (pixmap.width(), pixmap.height())
        scene.setSceneRect(item.boundingRect())
        if grid:
            self.draw_grid(grid)
        if fit:
            self.fit()

    def _on_theme_changed(self, _name: str = "") -> None:
        """The canvas follows the theme: its background and the colour of the grid lines."""
        with contextlib.suppress(RuntimeError):  # the view was deleted
            self.setBackgroundBrush(theme.token("canvas_bg"))
            if self._grid is not None:
                self.draw_grid(self._grid)

    def draw_marks(self, marks: list[Mark]) -> None:
        """Replace the marks over the picture (see ``Mark``)."""
        scene = self.scene()
        for item in self.mark_items:
            scene.removeItem(item)
        self.mark_items = []
        self.marks = list(marks)
        if self.pixmap_item is None:
            return
        none = QPen(Qt.PenStyle.NoPen)
        for kind, x, y, w, h in marks:
            if kind == MARK_ORIGIN:
                pen = QPen(ORIGIN_LINE)
                pen.setCosmetic(True)
                pen.setWidth(2)
                arm = max(2.0, min(self.image_size) / 16)
                self.mark_items.append(scene.addLine(x - arm, y, x + arm, y, pen))
                self.mark_items.append(scene.addLine(x, y - arm, x, y + arm, pen))
            elif kind == MARK_ACTIVE:
                self.mark_items.append(scene.addRect(x, y, w, h, none, QBrush(ACTIVE_TINT)))
            else:
                pen = QPen(FOOTPRINT_LINE if kind == MARK_FOOTPRINT else CURRENT_LINE)
                pen.setCosmetic(True)
                pen.setWidth(2)
                brush = QBrush(FOOTPRINT_TINT) if kind == MARK_FOOTPRINT else QBrush()
                self.mark_items.append(scene.addRect(x, y, w, h, pen, brush))

    def draw_diamonds(self, diamonds: list[list[list[float]]]) -> None:
        """Replace the diamond grid over an isometric picture (T17.16): each diamond is its
        four corners in image pixels (``map_preview.standing_diamonds``), drawn with the line of
        the square grid and a light tint, so that the tile under it stays visible."""
        scene = self.scene()
        for item in self.diamond_items:
            scene.removeItem(item)
        self.diamond_items = []
        self.diamonds = [list(d) for d in diamonds]
        if self.pixmap_item is None:
            return
        line = QPen(theme.token("grid_line"))
        line.setCosmetic(True)
        line.setWidth(2)
        tint = QBrush(FOOTPRINT_TINT)
        for corners in self.diamonds:
            polygon = QPolygonF([QPointF(float(x), float(y)) for x, y in corners])
            self.diamond_items.append(scene.addPolygon(polygon, line, tint))

    def clear_grid(self) -> None:
        for item in self.grid_items:
            self.scene().removeItem(item)
        self.grid_items = []

    def draw_grid(self, grid: dict) -> None:
        self.clear_grid()
        self._grid = grid
        width, height = self.image_size
        if not width:
            return
        scene = self.scene()
        line = QPen(theme.token("grid_line"))
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
        # on a screen scaled to 150 % a whole number here is not one on the screen (T13.10)
        scale = theme.crisp_scale(scale, self.devicePixelRatioF())
        self.zoom = scale
        self.scale(scale, scale)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        super().mouseReleaseEvent(event)
        press, self._press = self._press, None
        if press is None or event.button() != Qt.MouseButton.LeftButton:
            return
        release = event.position().toPoint()
        if (release - press).manhattanLength() <= 3 and self.pixmap_item is not None:
            point = self.mapToScene(release)
            self.clicked.emit(point.x(), point.y())

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.25 if event.angleDelta().y() > 0 else 0.8
            self.zoom *= factor
            self.scale(factor, factor)
            event.accept()
        else:
            super().wheelEvent(event)
