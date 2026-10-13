"""Page 2: choose the kind of game: a turn-based RPG, an action RPG, a metroidvania, a
shoot 'em up, a run and gun, a racing game or a farm."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QT_TRANSLATE_NOOP, QEvent, QObject, QPointF, QRectF, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QImage,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPalette,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QWidget,
)

from rpggen import features
from rpggen.core import catalog as catalog_mod
from rpggen.core import config as config_mod
from rpggen.core import mapping, options, requirements
from rpggen.gui import theme, thumbnails
from rpggen.gui.pages.base import WizardPage
from rpggen.gui.state import WizardState

ARPG_WARNING = "ARPG will use a generic swing effect until you add attack animations."
ARPG_TOOLTIP = "Coming in a later version"
LATER_TOOLTIP = ARPG_TOOLTIP
# ASSET-030, as the page says it (the run reports it with the asset's name)
AIR_WARNING = (
    "Your player has no jump or fall animation; a metroidvania will show its idle frame in the "
    "air until you add them."
)
SIDE_HINT = "This pack looks side-view: a metroidvania fits it."
TOP_DOWN_HINT = "Your characters have walk-down animations; a metroidvania uses side-view sprites."
# the same two once the run and gun can be chosen, and what T16.02 says of a pack (T16.16)
SIDE_BOTH_HINT = "This pack looks side-view: a metroidvania or a run and gun fits it."
TOP_DOWN_GUN_HINT = (
    "Your characters have walk-down animations; a run and gun uses side-view sprites."
)
AIR_WARNING_GUN = (
    "Your player has no jump or fall animation; a run and gun will show its idle frame in the "
    "air until you add them."
)
SHMUP_HINT = "This pack looks like a shooter pack: a shoot 'em up fits it."
RACING_HINT = "This pack looks like a racing pack: a racing game fits it."
FARM_HINT = "This pack looks like a farming pack: a farm fits it."  # T17.01, T17.16
# an isometric pack (T17.12), with the diamond of its tiles when the pack says or shows it
ISO_HINT = "This pack is isometric. The view is chosen on the Options page."
ISO_SIZE_HINT = (
    "This pack is isometric ({0} x {1} diamonds). The view is chosen on the Options page."
)
# the kinds in the order of their cards, and the switch of each
KINDS = ("turn_based", "arpg", "metroidvania", *config_mod.ARCADE_KINDS, "farm")
# The kinds that are walked from above: their starter map is the same map with the same options
# (an area table among them).
TOP_DOWN_KINDS = ("turn_based", "arpg", "farm")
GRID_WIDTH = 1000  # a window this wide has rows of three cards; a narrower one a column
GRID_COLUMNS = 3
WIDE_GRID_WIDTH = 1280  # ... and one this wide rows of four: seven cards in two rows (T17.16)
WIDE_GRID_COLUMNS = 4
MOCK_GRID_HEIGHT = 160  # the drawing of a card in the grid is no higher than this
MOCK_ROW_SIZE = (200, 112)  # ... and at the left of a card of the column it is this
FULL_CARD_HEIGHT = 380  # a card of the grid with its list; two rows of them need twice this


def kind_available(kind: str) -> bool:
    """True when the kind of game can be chosen (its feature flag; the RPG always can)."""
    return {
        "arpg": features.ARPG_AVAILABLE,
        "metroidvania": features.METROIDVANIA_AVAILABLE,
        "shmup": features.SHMUP_AVAILABLE,
        "run_and_gun": features.RUN_AND_GUN_AVAILABLE,
        "racing": features.RACING_AVAILABLE,
        "farm": features.FARM_AVAILABLE,
    }.get(kind, True)


class FlowDiagram(QWidget):
    """Boxes joined by arrows, drawn with QPainter (no images)."""

    GAP = 18.0
    BOX_H = 26.0
    ROW_GAP = 6.0
    PAD = 12  # around a step's text, inside its box

    def __init__(self, steps: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.steps = steps
        self.setMinimumSize(QSize(200, 44))
        # as high as its rows at the width it is given: the layouts ask ``heightForWidth``,
        # so a card knows its height at a width before it has that width (T17.16)
        policy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def rows_for(self, width: int) -> list[list[str]]:
        """The steps in as many rows as ``width`` needs: a step is never narrower than its
        text, so a narrow card (three of them side by side) gets a second row."""
        metrics = self.fontMetrics()
        rows: list[list[str]] = []
        row: list[str] = []
        used = 0.0
        for step in self.steps:
            need = metrics.horizontalAdvance(step) + self.PAD
            extra = need + (self.GAP if row else 0.0)
            if row and used + extra > width - 2:
                rows.append(row)
                row, used = [step], float(need)
            else:
                row.append(step)
                used += extra
        if row:
            rows.append(row)
        return rows

    def height_for(self, width: int) -> int:
        count = len(self.rows_for(width))
        return int(count * self.BOX_H + (count - 1) * self.ROW_GAP + 10)

    def hasHeightForWidth(self) -> bool:  # noqa: N802 - Qt override
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802 - Qt override
        return max(44, self.height_for(width))

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt override
        return QSize(max(200, self.width()), self.heightForWidth(max(200, self.width())))

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = self.palette()
        line = palette.color(QPalette.ColorRole.WindowText)
        fill = palette.color(QPalette.ColorRole.Base)
        rows = self.rows_for(self.width())
        gap = self.GAP
        box_h = min(30.0 if len(rows) == 1 else self.BOX_H, self.height() - 4.0)
        block = len(rows) * box_h + (len(rows) - 1) * self.ROW_GAP
        top = (self.height() - block) / 2
        painter.setPen(line)
        metrics = self.fontMetrics()
        for r, row in enumerate(rows):
            n = len(row)
            # a row that is followed by another leaves room for the arrow that leads on
            room = self.width() - 2 - (gap if r < len(rows) - 1 else 0.0)
            free = room - gap * (n - 1)
            needs = [metrics.horizontalAdvance(text) + self.PAD for text in row]
            if len(rows) == 1 and max(needs) <= free / n:
                widths = [free / n] * n  # one row with room: equal boxes, as the cards always had
            else:  # every box as wide as its text, the rest shared out
                spare = max(0.0, free - sum(needs)) / n
                widths = [need + spare for need in needs]
            y_top = top + r * (box_h + self.ROW_GAP)
            x = 1.0
            for i, text in enumerate(row):
                box_w = widths[i]
                rect = QRectF(x, y_top, box_w, box_h)
                painter.setBrush(fill)
                painter.drawRoundedRect(rect, 4, 4)
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
                if i < n - 1 or r < len(rows) - 1:
                    y = y_top + box_h / 2
                    x0, x1 = x + box_w + 2, x + box_w + gap - 2
                    painter.drawLine(int(x0), int(y), int(x1), int(y))
                    painter.drawLine(int(x1), int(y), int(x1 - 4), int(y - 3))
                    painter.drawLine(int(x1), int(y), int(x1 - 4), int(y + 3))
                x += box_w + gap
        painter.end()


@dataclass
class SceneArt:
    """The pack's own pictures for the cards: a ground tile, the hero and (when there is one) an
    enemy, as pixmaps at their file size."""

    player: QPixmap
    ground: QPixmap | None = None
    enemy: QPixmap | None = None
    # the player in the air or running (its `jump` or `run` frame), for the metroidvania card;
    # None when it has neither, and the card then shows `player`
    side_player: QPixmap | None = None


def _pixmap(image) -> QPixmap | None:  # noqa: ANN001 - a PIL image or None
    if image is None:
        return None
    rgba = image.convert("RGBA")
    qimage = QImage(rgba.tobytes(), rgba.width, rgba.height, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimage.copy())


def build_scene_art(state: WizardState, resolver=None) -> SceneArt | None:  # noqa: ANN001
    """Ground, player and enemy art of the analysed packs; None without a ``PLAYER`` (the cards
    keep their drawing). A piece that cannot be read is left out."""
    cat = state.catalog
    if cat is None:
        return None
    if resolver is None:
        from rpggen.gui.pages.audit_page import make_resolver

        resolver = make_resolver(state)

    def art_of(role: str, loader):  # noqa: ANN001, ANN202
        asset_id = mapping.best_for(cat, role)
        asset = cat.asset(asset_id) if asset_id else None
        path = resolver(asset) if asset is not None else None
        if asset is None or path is None:
            return None
        return _pixmap(loader(path, catalog_mod.effective(asset)))

    player = art_of("PLAYER", thumbnails.first_frame_image)
    if player is None:
        return None

    def moving_frame(path, facets):  # noqa: ANN001, ANN202
        return thumbnails.first_frame_image(path, facets, prefer=("jump", "run"), only=True)

    return SceneArt(
        player,
        art_of("GROUND", thumbnails.ground_tile_image),
        art_of("ENEMY", thumbnails.first_frame_image),
        art_of("PLAYER", moving_frame),
    )


def scaled_to_height(pixmap: QPixmap, height: float, ratio: float = 1.0) -> QPixmap:
    """Nearest-neighbour: a whole-number factor when the picture is smaller than ``height`` (the
    pixels stay square), the nearest size below it when it is larger. ``height`` is in the
    window's pixels; on a screen with the device pixel ratio ``ratio`` the picture is made for
    that many device pixels and tagged, so the factor is whole on the screen (T13.10)."""
    ratio = ratio if ratio > 0 else 1.0
    height = height * ratio
    h = max(1, pixmap.height())
    if height >= h:
        factor = max(1, int(height // h))
        scaled = pixmap.scaled(
            pixmap.width() * factor,
            h * factor,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
    else:
        scaled = pixmap.scaledToHeight(
            max(1, int(height)), Qt.TransformationMode.FastTransformation
        )
    scaled.setDevicePixelRatio(ratio)
    return scaled


class MockScreen(QWidget):
    """A drawing of what the game looks like, made with QPainter (no pictures): two battlers, a
    command box and HP rows for the turn-based game; a room, a swing and a HUD bar for the action
    game; a cave seen from the side with a gap, a plank, an orb and health pips for the
    metroidvania; a ship over stars for the shoot 'em up, a soldier on a ledge that aims up
    for the run and gun, a car on a curve for the racing game; a farmer by a row of crops, a
    house and the clock for the farm."""

    BACKGROUNDS = {
        "turn_based": QColor(38, 44, 60),
        "arpg": QColor(84, 130, 78),
        "metroidvania": QColor(44, 40, 66),
        "shmup": QColor(14, 16, 36),
        "run_and_gun": QColor(40, 58, 74),
        "racing": QColor(76, 150, 70),
        "farm": QColor(104, 158, 84),
    }
    # where the stars of the shoot 'em up are, as parts of the drawing (fixed: no randomness)
    STARS = (
        (0.08, 0.20), (0.19, 0.62), (0.27, 0.33), (0.36, 0.80), (0.44, 0.14), (0.58, 0.52),
        (0.66, 0.26), (0.74, 0.72), (0.83, 0.40), (0.91, 0.12), (0.95, 0.64), (0.13, 0.88),
    )  # fmt: skip

    def __init__(self, kind: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.kind = kind
        self.art: SceneArt | None = None
        self.setMinimumSize(QSize(200, 96))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def set_art(self, art: SceneArt | None) -> None:
        self.art = art
        self.update()

    def _paint_side(self, painter: QPainter, rect) -> None:  # noqa: ANN001
        """The metroidvania: a floor with a gap, a plank above it, the player in the air over the
        gap, an orb on the plank, an enemy on the far side and health pips. With the pack's art
        the floor is its ground tile and the figures are its sprites."""
        art = self.art
        w, h = rect.width(), rect.height()
        x0, y0 = rect.left(), rect.top()
        painter.save()
        painter.setClipRect(rect)
        ratio = self.devicePixelRatioF()
        floor_top = y0 + h * 0.78
        spans = ((0.0, 0.42), (0.58, 1.0))  # the floor left and right of the gap
        painter.setPen(Qt.PenStyle.NoPen)
        if art is not None and art.ground is not None:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
            tile = scaled_to_height(art.ground, 24, ratio)
            for left, right in spans:
                painter.drawTiledPixmap(
                    QRectF(x0 + w * left, floor_top, w * (right - left), y0 + h - floor_top), tile
                )
        else:
            painter.setBrush(QColor(96, 84, 110))
            for left, right in spans:
                painter.drawRect(
                    QRectF(x0 + w * left, floor_top, w * (right - left), y0 + h - floor_top)
                )
        painter.setBrush(QColor(150, 110, 70))  # the one-way plank
        painter.drawRect(QRectF(x0 + w * 0.66, y0 + h * 0.48, w * 0.24, h * 0.04))
        orb = min(h * 0.11, w * 0.08)
        painter.setBrush(QColor(250, 214, 90))  # the ability on it
        painter.drawEllipse(QRectF(x0 + w * 0.78 - orb / 2, y0 + h * 0.46 - orb, orb, orb))
        if art is not None:
            # the figures fit a card of any shape: as tall as the room allows, never so wide
            # that they leave the gap or the edge
            hero = art.side_player if art.side_player is not None else art.player
            player = scaled_to_height(hero, min(h * 0.30, w * 0.22), ratio)
            painter.drawPixmap(
                int(x0 + w * 0.50 - player.width() / ratio / 2),
                int(y0 + h * 0.66 - player.height() / ratio),
                player,
            )
            if art.enemy is not None:
                enemy = scaled_to_height(art.enemy, min(h * 0.26, w * 0.20), ratio)
                painter.drawPixmap(
                    int(x0 + w * 0.97 - enemy.width() / ratio),
                    int(floor_top - enemy.height() / ratio),
                    enemy,
                )
        else:
            painter.setBrush(QColor(96, 160, 232))  # the player, in the air over the gap
            painter.drawRoundedRect(QRectF(x0 + w * 0.44, y0 + h * 0.40, w * 0.07, h * 0.22), 3, 3)
            painter.setBrush(QColor(224, 96, 88))  # an enemy on the far side
            painter.drawRoundedRect(QRectF(x0 + w * 0.86, y0 + h * 0.62, w * 0.08, h * 0.16), 3, 3)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(230, 230, 240, 150), 1, Qt.PenStyle.DashLine))  # the jump
        painter.drawArc(QRectF(x0 + w * 0.32, y0 + h * 0.40, w * 0.36, h * 0.76), 20 * 16, 140 * 16)
        painter.setPen(Qt.PenStyle.NoPen)
        for i in range(5):  # health pips, the last one empty
            painter.setBrush(QColor(210, 70, 70) if i < 4 else QColor(70, 66, 84))
            painter.drawRect(
                QRectF(x0 + w * (0.05 + 0.045 * i), y0 + h * 0.10, w * 0.032, h * 0.07)
            )
        painter.restore()

    def _figure(self, painter: QPainter, pixmap, cx: float, bottom: float, height: float):  # noqa: ANN001, ANN202
        """A sprite of the pack, ``height`` high at most, standing on ``bottom`` around ``cx``."""
        ratio = self.devicePixelRatioF()
        shown = scaled_to_height(pixmap, height, ratio)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        painter.drawPixmap(
            int(cx - shown.width() / ratio / 2), int(bottom - shown.height() / ratio), shown
        )

    def _paint_shmup(self, painter: QPainter, rect) -> None:  # noqa: ANN001
        """The shoot 'em up: stars, a ship at the bottom that fires up the screen, a V of
        enemies at the top and the lives in a corner. With the pack's art the ship is its
        player and the enemies are its enemy."""
        art = self.art
        w, h = rect.width(), rect.height()
        x0, y0 = rect.left(), rect.top()
        painter.save()
        painter.setClipRect(rect)
        painter.setPen(Qt.PenStyle.NoPen)
        for i, (sx, sy) in enumerate(self.STARS):
            painter.setBrush(QColor(236, 238, 250, 230 if i % 3 else 120))
            size = 2.0 if i % 4 else 3.0
            painter.drawRect(QRectF(x0 + w * sx, y0 + h * sy, size, size))
        ship_x, ship_y = x0 + w * 0.50, y0 + h * 0.90
        painter.setBrush(QColor(250, 224, 96))  # the shots, on their way up
        for i in range(3):
            painter.drawRect(QRectF(ship_x - 1.5, y0 + h * (0.60 - 0.14 * i), 3.0, h * 0.07))
        enemies = ((0.30, 0.16), (0.50, 0.28), (0.70, 0.16))
        if art is not None:
            self._figure(painter, art.player, ship_x, ship_y, min(h * 0.26, w * 0.20))
        else:
            painter.setBrush(QColor(96, 160, 232))  # the ship: a wedge that points up
            painter.drawPolygon(
                [
                    QPointF(ship_x, ship_y - h * 0.20),
                    QPointF(ship_x + w * 0.06, ship_y),
                    QPointF(ship_x - w * 0.06, ship_y),
                ]
            )
        for ex, ey in enemies:
            if art is not None and art.enemy is not None:
                self._figure(
                    painter, art.enemy, x0 + w * ex, y0 + h * (ey + 0.12), min(h * 0.2, w * 0.14)
                )
            else:
                painter.setBrush(QColor(224, 96, 88))
                painter.drawRoundedRect(
                    QRectF(x0 + w * (ex - 0.04), y0 + h * ey, w * 0.08, h * 0.12), 3, 3
                )
        for i in range(3):  # the lives
            painter.setBrush(QColor(96, 160, 232))
            painter.drawRect(QRectF(x0 + w * (0.05 + 0.045 * i), y0 + h * 0.86, w * 0.03, h * 0.06))
        painter.restore()

    def _paint_gun(self, painter: QPainter, rect) -> None:  # noqa: ANN001
        """The run and gun: the ground with a ledge on it, the soldier on the ledge, its shots
        on the way up to an enemy on a plank, and the lives."""
        art = self.art
        w, h = rect.width(), rect.height()
        x0, y0 = rect.left(), rect.top()
        painter.save()
        painter.setClipRect(rect)
        painter.setPen(Qt.PenStyle.NoPen)
        ratio = self.devicePixelRatioF()
        floor_top = y0 + h * 0.80
        ledge = QRectF(x0 + w * 0.14, y0 + h * 0.62, w * 0.30, h * 0.18)
        ground = QRectF(x0, floor_top, w, y0 + h - floor_top)
        if art is not None and art.ground is not None:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            tile = scaled_to_height(art.ground, 24, ratio)
            painter.drawTiledPixmap(ground, tile)
            painter.drawTiledPixmap(ledge, tile)
        else:
            painter.setBrush(QColor(92, 104, 84))
            painter.drawRect(ground)
            painter.drawRect(ledge)
        plank = QRectF(x0 + w * 0.66, y0 + h * 0.34, w * 0.26, h * 0.04)
        painter.setBrush(QColor(150, 110, 70))
        painter.drawRect(plank)
        soldier_x, soldier_y = x0 + w * 0.30, ledge.top()
        if art is not None:
            hero = art.side_player if art.side_player is not None else art.player
            self._figure(painter, hero, soldier_x, soldier_y, min(h * 0.30, w * 0.22))
            if art.enemy is not None:
                self._figure(painter, art.enemy, x0 + w * 0.80, plank.top(), min(h * 0.26, w * 0.2))
        else:
            painter.setBrush(QColor(96, 160, 232))
            painter.drawRoundedRect(
                QRectF(soldier_x - w * 0.035, soldier_y - h * 0.24, w * 0.07, h * 0.24), 3, 3
            )
            painter.setBrush(QColor(224, 96, 88))
            painter.drawRoundedRect(
                QRectF(x0 + w * 0.76, plank.top() - h * 0.18, w * 0.08, h * 0.18), 3, 3
            )
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # the gun points up and to the right; three shots are on the way
        gx, gy = soldier_x + w * 0.03, soldier_y - h * 0.18
        painter.setPen(QPen(QColor(230, 230, 240), 2))
        painter.drawLine(QPointF(gx, gy), QPointF(gx + w * 0.06, gy - h * 0.08))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(250, 224, 96))
        for i in range(3):
            t = 0.12 + 0.11 * i
            painter.drawEllipse(QPointF(gx + w * t, gy - h * t * 1.3), 2.5, 2.5)
        for i in range(3):  # the lives
            painter.setBrush(QColor(210, 70, 70))
            painter.drawRect(
                QRectF(x0 + w * (0.05 + 0.045 * i), y0 + h * 0.10, w * 0.032, h * 0.07)
            )
        painter.restore()

    def _paint_race(self, painter: QPainter, rect) -> None:  # noqa: ANN001
        """The racing game, from above: a road that comes up the left and bends to the right,
        the start line across it, a car in the bend, a rival behind it and a lap counter."""
        w, h = rect.width(), rect.height()
        x0, y0 = rect.left(), rect.top()
        painter.save()
        painter.setClipRect(rect)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        road = min(w * 0.20, h * 0.34)
        cx, cy = x0 + w * 0.26, y0 + h * 0.30  # the middle of the road in the bend
        radius = road * 0.9
        path = QPainterPath()
        path.moveTo(cx, y0 + h + road)
        path.lineTo(cx, cy + radius)
        path.quadTo(cx, cy, cx + radius, cy)
        path.lineTo(x0 + w + road, cy)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        flat = Qt.PenCapStyle.FlatCap
        painter.setPen(QPen(QColor(236, 236, 236), road + 6, Qt.PenStyle.SolidLine, flat))
        painter.drawPath(path)  # the kerb
        painter.setPen(QPen(QColor(70, 70, 78), road, Qt.PenStyle.SolidLine, flat))
        painter.drawPath(path)
        painter.setPen(QPen(QColor(236, 236, 236, 170), 2, Qt.PenStyle.DashLine, flat))
        painter.drawPath(path)  # the line down its middle
        painter.setPen(QPen(QColor(240, 240, 240), 4, Qt.PenStyle.SolidLine, flat))
        line_y = y0 + h * 0.84
        painter.drawLine(QPointF(cx - road / 2, line_y), QPointF(cx + road / 2, line_y))
        painter.setPen(Qt.PenStyle.NoPen)
        car_w, car_h = road * 0.34, road * 0.62
        cars = (  # x, y, the way it points (0 is up), its colour
            (cx + radius * 0.32, cy + radius * 0.34, 45.0, QColor(220, 60, 60)),
            (cx - road * 0.16, y0 + h * 0.68, 0.0, QColor(96, 160, 232)),
        )
        for x, y, angle, colour in cars:
            painter.save()
            painter.translate(x, y)
            painter.rotate(angle)
            painter.setBrush(colour)
            painter.drawRoundedRect(QRectF(-car_w / 2, -car_h / 2, car_w, car_h), 3, 3)
            painter.setBrush(QColor(20, 24, 36))  # the windscreen, at the front
            painter.drawRect(QRectF(-car_w * 0.32, -car_h * 0.30, car_w * 0.64, car_h * 0.22))
            painter.restore()
        painter.setBrush(QColor(20, 24, 36, 220))  # the lap counter
        painter.drawRoundedRect(QRectF(x0 + w * 0.72, y0 + h * 0.72, w * 0.22, h * 0.18), 3, 3)
        for i in range(3):
            painter.setBrush(QColor(250, 210, 60) if i < 2 else QColor(90, 90, 100))
            painter.drawRect(QRectF(x0 + w * (0.75 + 0.06 * i), y0 + h * 0.78, w * 0.04, h * 0.06))
        painter.restore()

    def _paint_farm(self, painter: QPainter, rect) -> None:  # noqa: ANN001
        """The farm, from above: a house in a corner, a bed of tilled soil with a row of crops
        that are further on the further right they stand, the last of them watered, the farmer
        beside the row, and the clock of the day in the other corner. With the pack's art the
        farmer is its player."""
        art = self.art
        w, h = rect.width(), rect.height()
        x0, y0 = rect.left(), rect.top()
        painter.save()
        painter.setClipRect(rect)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        u = min(w, h * 2.2)  # what is as wide as it is high keeps its shape in a low drawing
        # the house: its wall, its roof and its door
        house = QRectF(x0 + w * 0.06, y0 + h * 0.14, u * 0.22, h * 0.34)
        painter.setBrush(QColor(206, 178, 132))
        painter.drawRect(house)
        painter.setBrush(QColor(176, 70, 60))
        painter.drawPolygon(
            [
                QPointF(house.left() - u * 0.02, house.top() + house.height() * 0.45),
                QPointF(house.center().x(), house.top() - h * 0.08),
                QPointF(house.right() + u * 0.02, house.top() + house.height() * 0.45),
            ]
        )
        painter.setBrush(QColor(96, 64, 44))
        painter.drawRect(
            QRectF(house.center().x() - u * 0.025, house.bottom() - h * 0.16, u * 0.05, h * 0.16)
        )
        # the bed: dry soil, and wet soil under the plants that were watered
        bed = QRectF(x0 + w * 0.12, y0 + h * 0.66, w * 0.76, h * 0.20)
        painter.setBrush(QColor(142, 98, 62))
        painter.drawRect(bed)
        painter.setBrush(QColor(98, 66, 44))
        painter.drawRect(
            QRectF(bed.left() + bed.width() * 0.6, bed.top(), bed.width() * 0.4, bed.height())
        )
        plants = 5
        for i in range(plants):  # a seedling at the left, a ripe plant at the right
            cx = bed.left() + bed.width() * (i + 0.5) / plants
            tall = h * (0.05 + 0.035 * i)
            painter.setBrush(QColor(60, 150, 66))
            painter.drawRoundedRect(
                QRectF(cx - u * 0.008, bed.center().y() - tall, u * 0.016, tall), 1, 1
            )
            leaf = u * (0.010 + 0.004 * i)
            painter.drawEllipse(
                QPointF(cx - leaf * 0.8, bed.center().y() - tall * 0.6), leaf, leaf * 0.6
            )
            painter.drawEllipse(
                QPointF(cx + leaf * 0.8, bed.center().y() - tall * 0.8), leaf, leaf * 0.6
            )
            if i == plants - 1:  # what is ripe
                painter.setBrush(QColor(232, 134, 46))
                painter.drawEllipse(QPointF(cx, bed.center().y() - tall), u * 0.018, u * 0.018)
        farmer_x, farmer_y = x0 + w * 0.52, bed.top() - h * 0.02
        if art is not None:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            self._figure(painter, art.player, farmer_x, farmer_y, min(h * 0.32, w * 0.22))
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        else:
            painter.setBrush(QColor(96, 160, 232))  # the farmer
            painter.drawRoundedRect(
                QRectF(farmer_x - u * 0.035, farmer_y - h * 0.24, u * 0.07, h * 0.24), 3, 3
            )
            painter.setBrush(QColor(236, 204, 120))  # and the hat
            painter.drawRect(QRectF(farmer_x - u * 0.05, farmer_y - h * 0.26, u * 0.10, h * 0.035))
        # the can: drops over the wet soil
        painter.setBrush(QColor(120, 190, 240))
        for i in range(3):
            painter.drawEllipse(
                QPointF(farmer_x + u * (0.07 + 0.03 * i), farmer_y - h * (0.10 - 0.03 * i)),
                2.0,
                2.0,
            )
        # the clock: a dial with its hand, and the day of the season beside it
        box = QRectF(x0 + w * 0.94 - u * 0.26, y0 + h * 0.08, u * 0.26, h * 0.22)
        painter.setBrush(QColor(20, 24, 36, 220))
        painter.drawRoundedRect(box, 3, 3)
        radius = min(box.height() * 0.34, box.width() * 0.18)
        dial = QPointF(box.left() + radius * 1.5, box.center().y())
        painter.setBrush(QColor(250, 214, 90))
        painter.drawEllipse(dial, radius, radius)
        painter.setPen(QPen(QColor(20, 24, 36), 2))
        painter.drawLine(dial, QPointF(dial.x() + radius * 0.6, dial.y() - radius * 0.5))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(230, 230, 240))
        for i in range(2):  # the date and the money: two lines
            painter.drawRect(
                QRectF(
                    dial.x() + radius * 1.6,
                    box.top() + box.height() * (0.26 + 0.30 * i),
                    box.right() - dial.x() - radius * 2.2,
                    box.height() * 0.14,
                )
            )
        painter.restore()

    def _paint_art(self, painter: QPainter, rect) -> None:  # noqa: ANN001
        """The scene with the pack's pictures; the layout is the drawing's, the pieces are art."""
        art = self.art
        assert art is not None
        w, h = rect.width(), rect.height()
        x0, y0 = rect.left(), rect.top()
        painter.save()
        painter.setClipRect(rect)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        ratio = self.devicePixelRatioF()
        if art.ground is not None:
            tile = scaled_to_height(art.ground, 24, ratio)
            painter.drawTiledPixmap(rect, tile)
        player = scaled_to_height(art.player, h * 0.30, ratio)
        enemy = scaled_to_height(art.enemy, h * 0.30, ratio) if art.enemy is not None else None
        if self.kind == "turn_based":
            if enemy is not None:
                for i in range(2):  # the enemies on the left
                    painter.drawPixmap(int(x0 + w * 0.14), int(y0 + h * (0.12 + 0.30 * i)), enemy)
            for i in range(2):  # the party on the right
                painter.drawPixmap(int(x0 + w * 0.72), int(y0 + h * (0.12 + 0.30 * i)), player)
            painter.setBrush(QColor(20, 24, 36, 220))
            painter.setPen(QPen(QColor(220, 220, 230), 1))
            painter.drawRoundedRect(QRectF(x0 + w * 0.05, y0 + h * 0.70, w * 0.40, h * 0.24), 3, 3)
            for i in range(3):  # the command list
                y = int(y0 + h * (0.76 + 0.055 * i))
                painter.drawLine(int(x0 + w * 0.09), y, int(x0 + w * 0.30), y)
        else:
            painter.drawPixmap(int(x0 + w * 0.30), int(y0 + h * 0.40), player)
            if enemy is not None:
                painter.drawPixmap(int(x0 + w * 0.70), int(y0 + h * 0.40), enemy)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(250, 250, 250), 3))  # the swing, next to the enemy
            painter.drawArc(
                QRectF(x0 + w * 0.40, y0 + h * 0.26, w * 0.26, h * 0.46), -50 * 16, 100 * 16
            )
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(60, 60, 70))  # the HUD bar
            painter.drawRect(QRectF(x0 + w * 0.06, y0 + h * 0.10, w * 0.30, h * 0.07))
            painter.setBrush(QColor(210, 70, 70))
            painter.drawRect(QRectF(x0 + w * 0.06, y0 + h * 0.10, w * 0.22, h * 0.07))
        painter.restore()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(2, 2, -2, -2)
        painter.setPen(QPen(QColor(20, 20, 24), 2))
        painter.setBrush(self.BACKGROUNDS.get(self.kind, self.BACKGROUNDS["arpg"]))
        painter.drawRoundedRect(rect, 6, 6)
        w, h = rect.width(), rect.height()
        x0, y0 = rect.left(), rect.top()
        painter.setPen(Qt.PenStyle.NoPen)
        if self.kind == "metroidvania":
            self._paint_side(painter, rect)
        elif self.kind == "shmup":
            self._paint_shmup(painter, rect)
        elif self.kind == "run_and_gun":
            self._paint_gun(painter, rect)
        elif self.kind == "racing":
            self._paint_race(painter, rect)
        elif self.kind == "farm":
            self._paint_farm(painter, rect)
        elif self.art is not None:
            self._paint_art(painter, rect)
        elif self.kind == "turn_based":
            painter.setBrush(QColor(224, 96, 88))  # the enemies
            for i in range(2):
                painter.drawRoundedRect(
                    QRectF(x0 + w * 0.12, y0 + h * (0.18 + 0.25 * i), w * 0.12, h * 0.16), 3, 3
                )
            painter.setBrush(QColor(96, 160, 232))  # the party
            for i in range(2):
                painter.drawRoundedRect(
                    QRectF(x0 + w * 0.70, y0 + h * (0.18 + 0.25 * i), w * 0.10, h * 0.16), 3, 3
                )
            painter.setBrush(QColor(20, 24, 36))
            painter.setPen(QPen(QColor(220, 220, 230), 1))
            painter.drawRoundedRect(QRectF(x0 + w * 0.05, y0 + h * 0.66, w * 0.40, h * 0.28), 3, 3)
            for i in range(3):  # the command list
                painter.drawLine(
                    int(x0 + w * 0.09),
                    int(y0 + h * (0.74 + 0.07 * i)),
                    int(x0 + w * 0.30),
                    int(y0 + h * (0.74 + 0.07 * i)),
                )
            painter.setPen(Qt.PenStyle.NoPen)
            for i in range(2):  # HP rows
                painter.setBrush(QColor(60, 60, 70))
                painter.drawRect(
                    QRectF(x0 + w * 0.55, y0 + h * (0.70 + 0.12 * i), w * 0.38, h * 0.06)
                )
                painter.setBrush(QColor(110, 200, 110))
                painter.drawRect(
                    QRectF(
                        x0 + w * 0.55, y0 + h * (0.70 + 0.12 * i), w * (0.38 - 0.1 * i), h * 0.06
                    )
                )
        else:
            painter.setBrush(QColor(110, 80, 56))  # walls of the room
            painter.drawRect(QRectF(x0, y0, w, h * 0.10))
            painter.drawRect(QRectF(x0, y0, w * 0.05, h))
            painter.setBrush(QColor(224, 96, 88))  # an enemy
            painter.drawRoundedRect(QRectF(x0 + w * 0.68, y0 + h * 0.40, w * 0.09, h * 0.18), 3, 3)
            painter.setBrush(QColor(96, 160, 232))  # the player
            painter.drawRoundedRect(QRectF(x0 + w * 0.32, y0 + h * 0.42, w * 0.09, h * 0.20), 3, 3)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(250, 250, 250), 3))  # the swing
            painter.drawArc(
                QRectF(x0 + w * 0.36, y0 + h * 0.28, w * 0.26, h * 0.46), -50 * 16, 100 * 16
            )
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(60, 60, 70))  # the HUD bar
            painter.drawRect(QRectF(x0 + w * 0.06, y0 + h * 0.14, w * 0.30, h * 0.07))
            painter.setBrush(QColor(210, 70, 70))
            painter.drawRect(QRectF(x0 + w * 0.06, y0 + h * 0.14, w * 0.22, h * 0.07))
        painter.end()


class ArchetypeCard(QToolButton):
    """A large checkable card: title, description, a mock screen, what is generated, the controls
    and the flow of the game. The chosen card has a thick border and a check mark."""

    def __init__(
        self,
        key: str,
        title: str,
        text: str,
        steps: list[str],
        bullets: list[str],
        controls: str,
    ) -> None:
        super().__init__()
        self.key = key
        self.setObjectName(f"card_{key}")
        self.setAccessibleName(title)
        self.setCheckable(True)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        # three cards share a row of the grid (T14.10, T16.16): a card is as narrow as its
        # drawing
        self.setMinimumWidth(250)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setProperty("card", True)  # the stylesheet draws the card and its checked border
        self.grid = QGridLayout(self)
        self.head_box = QWidget()
        self.head_box.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        head = QHBoxLayout(self.head_box)
        head.setContentsMargins(0, 0, 0, 0)
        heading = QLabel(title)
        heading.setProperty("role", "section")
        heading.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.check_label = QLabel("✔")
        self.check_label.setObjectName(f"check_{key}")
        self.check_label.setProperty("accentGlyph", True)
        self.check_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.check_label.setVisible(False)
        # the mark keeps its room while it is hidden: a card is as high chosen as not, so the
        # rows of the grid do not move when another card is chosen (T17.16)
        keep = self.check_label.sizePolicy()
        keep.setRetainSizeWhenHidden(True)
        self.check_label.setSizePolicy(keep)
        head.addWidget(heading, 1)
        head.addWidget(self.check_label)
        body = QLabel(text)
        body.setWordWrap(True)
        body.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.body_label = body
        self.mock = MockScreen(key)
        self.bullet_label = QLabel(
            # a small list indent: three cards side by side leave a card little width
            "<ul style='margin-left:-22px; margin-top:0px; margin-bottom:0px'>"
            + "".join(f"<li>{b}</li>" for b in bullets)
            + "</ul>"
        )
        self.bullet_label.setWordWrap(True)
        self.bullet_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        controls_label = QLabel(controls)
        controls_label.setWordWrap(True)
        controls_label.setProperty("muted", True)
        controls_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.controls_label = controls_label
        self.flow = FlowDiagram(steps)
        self.shape = ""
        self.compact = False
        self.set_shape("grid")
        self.toggled.connect(self.check_label.setVisible)

    def set_shape(self, shape: str, compact: bool = False) -> None:
        """``"grid"``: the drawing between the text and the list, for a card that shares its
        row with two others. ``"row"``: the drawing at the left and everything else beside
        it, for a card that has the width of the page. ``compact`` leaves the list of what
        is generated and the controls line out (two rows of cards in a window that is not
        high; the generated README has both in full)."""
        if (shape, compact) == (self.shape, self.compact):
            return
        self.shape, self.compact = shape, compact
        texts = (self.head_box, self.body_label, self.bullet_label, self.controls_label, self.flow)
        for widget in (self.mock, *texts):
            self.grid.removeWidget(widget)
        for row in range(6):
            self.grid.setRowStretch(row, 0)
        # a card of the grid grows with its row (the drawing takes what there is, up to its
        # height); a card of the column is as high as what is in it
        grows = QSizePolicy.Policy.Minimum if shape == "row" else QSizePolicy.Policy.Expanding
        self.setSizePolicy(QSizePolicy.Policy.Expanding, grows)
        if shape == "row":
            self.mock.setFixedSize(QSize(*MOCK_ROW_SIZE))
            self.grid.addWidget(self.mock, 0, 0, len(texts), 1, Qt.AlignmentFlag.AlignTop)
            for row, widget in enumerate(texts):
                self.grid.addWidget(widget, row, 1)
            self.grid.setColumnStretch(0, 0)
            self.grid.setColumnStretch(1, 1)
        else:
            self.mock.setMinimumSize(QSize(200, 48 if compact else 96))
            self.mock.setMaximumSize(QSize(16777215, MOCK_GRID_HEIGHT))
            for row, widget in enumerate((texts[0], texts[1], self.mock, *texts[2:])):
                self.grid.addWidget(widget, row, 0)
            self.grid.setRowStretch(2, 1)
            self.grid.setColumnStretch(0, 1)
            self.grid.setColumnStretch(1, 0)
        self.bullet_label.setVisible(not compact)
        self._show_controls()

    # below this width a card has no room for the controls line: three cards in the minimum
    # window. The generated README lists the controls in full.
    CONTROLS_WIDTH = 280

    def _show_controls(self, width: int | None = None) -> None:
        wide = self.width() if width is None else width
        roomy = not self.compact and wide >= self.CONTROLS_WIDTH
        if roomy == self.controls_label.isHidden():
            self.controls_label.setVisible(roomy)

    def height_at(self, width: int) -> int:
        """How high the card has to be when it is ``width`` wide, with what it shows at that
        width (the controls line comes and goes with it)."""
        self._show_controls(width)
        return self.grid.heightForWidth(width)

    def resizeEvent(self, event) -> None:  # noqa: ANN001, N802 - Qt override
        super().resizeEvent(event)
        self._show_controls()

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt override
        """What the card's own layout asks for: a tool button's own hint is its (empty) text."""
        return self.grid.sizeHint()

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - Qt override
        return self.grid.minimumSize()

    def hasHeightForWidth(self) -> bool:  # noqa: N802 - Qt override
        return self.grid.hasHeightForWidth()

    def heightForWidth(self, width: int) -> int:  # noqa: N802 - Qt override
        return self.grid.heightForWidth(width)


class ArchetypePage(WizardPage):
    title = "Archetype"
    heading = str(QT_TRANSLATE_NOOP("MainWindow", "Kind of game"))
    purpose = str(
        QT_TRANSLATE_NOOP(
            "WizardPage", "Choose how the game plays. You can make the other kinds later."
        )
    )
    help_anchor = "3. Using a pack you bought"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = self.page_layout()
        layout.addWidget(QLabel(self.tr("What kind of game do you want to start with?")))
        self.turn_card = ArchetypeCard(
            "turn_based",
            self.tr("Turn-based RPG"),
            self.tr(
                "Walk around, meet enemies and fight in menu battles.\nRewards follow every win."
            ),
            [self.tr("Explore"), self.tr("Encounter"), self.tr("Battle"), self.tr("Rewards")],
            [
                self.tr("A battle scene with commands: attack, defend, item, run"),
                self.tr("Enemies that wait on the map and start a battle when touched"),
                self.tr("Experience, levels, gold and loot after a win"),
            ],
            self.tr("Controls: arrow keys or WASD to walk, E to talk, Enter to choose in battle."),
        )
        self.arpg_card = ArchetypeCard(
            "arpg",
            self.tr("Action RPG"),
            self.tr("Fight in real time with attacks and dodges.\nLoot drops where enemies fall."),
            [self.tr("Move"), self.tr("Attack"), self.tr("Dodge"), self.tr("Loot")],
            [
                self.tr("A sword swing, a heavy attack and a dodge roll"),
                self.tr("Enemies that see you, chase you and strike"),
                self.tr("A health bar, loot that drops and a quick item slot"),
            ],
            self.tr("Controls: WASD to walk, J to attack, K for a heavy attack, Shift to dodge."),
        )
        self.metroidvania_card = ArchetypeCard(
            "metroidvania",
            self.tr("Metroidvania"),
            self.tr("Run and jump through joined rooms.\nNew abilities open new ways."),
            [
                self.tr("Run"),
                self.tr("Jump"),
                self.tr("Find an ability"),
                self.tr("Open the way"),
                self.tr("Explore"),
            ],
            [
                self.tr("A side-view hero that runs, jumps and climbs"),
                self.tr("Rooms joined into one world, with a map"),
                self.tr("Abilities, a guardian and save stations"),
            ],
            self.tr("Controls: A and D to run, Space to jump, J to attack, Shift to dash."),
        )
        self.shmup_card = ArchetypeCard(
            "shmup",
            self.tr("Shoot 'em up"),
            self.tr("Fly over a scrolling stage and shoot waves of enemies.\nA boss ends it."),
            [self.tr("Fly"), self.tr("Shoot"), self.tr("Power up"), self.tr("Boss")],
            [
                self.tr("A ship, its shots, its bombs and power-up capsules"),
                self.tr("Stages of waves that scroll up or to the right"),
                self.tr("Lives, a score, a continue screen and high scores"),
            ],
            self.tr("Controls: WASD or arrows to fly, Z to shoot, X for a bomb, Shift to slow."),
        )
        self.run_and_gun_card = ArchetypeCard(
            "run_and_gun",
            self.tr("Run and gun"),
            self.tr("Run right through a stage, aim in eight ways.\nA boss waits at its end."),
            [self.tr("Run"), self.tr("Aim"), self.tr("Shoot"), self.tr("Boss")],
            [
                self.tr("A soldier that runs, jumps, ducks and aims up and down"),
                self.tr("Weapons to pick up, enemies that spawn, and bosses"),
                self.tr("A grapple arm that swings, if you want one"),
            ],
            self.tr("Controls: A and D to run, Space to jump, J to shoot, K for a grenade."),
        )
        self.racing_card = ArchetypeCard(
            "racing",
            self.tr("Racing"),
            self.tr("Race rivals round a track seen from above.\nA championship of tracks."),
            [self.tr("Drive"), self.tr("Overtake"), self.tr("Lap"), self.tr("Podium")],
            [
                self.tr("A car in sixteen headings, with rivals that race it"),
                self.tr("Tracks with laps, checkpoints, hazards and pickups"),
                self.tr("Points for every race, and a champion at the end"),
            ],
            self.tr("Controls: Up to accelerate, Down to brake, Left and Right to steer."),
        )
        self.farm_card = ArchetypeCard(
            "farm",
            self.tr("Farm"),
            self.tr("Grow crops through days and seasons.\nSell them and get to know a village."),
            [
                self.tr("Till"),
                self.tr("Plant"),
                self.tr("Water"),
                self.tr("Harvest"),
                self.tr("Sell"),
            ],
            [
                self.tr("A farmer with tools, energy and a hotbar"),
                self.tr("Crops that grow by the day, seasons, weather and animals"),
                self.tr("A shipping bin, a shop and villagers with days of their own"),
            ],
            self.tr(
                "Controls: WASD to walk, Space to use what you hold, E to talk, 1 to 0 to choose."
            ),
        )
        self.cards = {
            "turn_based": self.turn_card,
            "arpg": self.arpg_card,
            "metroidvania": self.metroidvania_card,
            "shmup": self.shmup_card,
            "run_and_gun": self.run_and_gun_card,
            "racing": self.racing_card,
            "farm": self.farm_card,
        }
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        # seven cards (T16.16, T17.16): rows of four in a very wide window, rows of three in a
        # wide one (the third row scrolls), else a column that scrolls
        self.cards_scroll = QScrollArea()
        self.cards_scroll.setObjectName("archetypeScroll")
        self.cards_scroll.setWidgetResizable(True)
        self.cards_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.cards_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.cards_box = QWidget()
        self.cards_box.setObjectName("archetypeCards")
        self.cards_grid = QGridLayout(self.cards_box)
        self.cards_grid.setContentsMargins(0, 0, theme.px("space_8"), 0)
        self.cards_grid.setSpacing(theme.px("space_12"))
        for card in self.cards.values():
            self.group.addButton(card)
        self.cards_scroll.setWidget(self.cards_box)
        self.cards_scroll.installEventFilter(self)
        self.cards_scroll.viewport().installEventFilter(self)
        layout.addWidget(self.cards_scroll, 1)
        self._grid_shape: tuple[int, bool] | None = None
        # (columns, the width of a card) -> the heights of the rows of whole cards
        self._whole_rows: dict[tuple[int, int], list[int]] = {}
        self._apply_shape()
        self.same_label = QLabel(
            self.tr(
                "You can generate the other kind later into a new project; saving, dialogue, "
                "inventory and menus are the same."
            )
        )
        self.same_label.setObjectName("sameLabel")
        self.same_label.setWordWrap(True)
        self.same_label.setProperty("muted", True)
        layout.addWidget(self.same_label)
        for key, card in self.cards.items():  # a kind behind its flag: there, and not yet
            card.setEnabled(kind_available(key))
            if not kind_available(key):
                card.setToolTip(self.tr(LATER_TOOLTIP))
        # what detection says about the pack's point of view (T14.02): a suggestion, never a lock
        self.view_hint = QLabel()
        self.view_hint.setObjectName("viewHint")
        self.view_hint.setWordWrap(True)
        self.view_hint.setProperty("muted", True)
        self.view_hint.setVisible(False)
        layout.addWidget(self.view_hint)
        # an isometric pack (T17.16): said under the cards while the view can be chosen
        self.iso_hint = QLabel()
        self.iso_hint.setObjectName("isoHint")
        self.iso_hint.setWordWrap(True)
        self.iso_hint.setProperty("muted", True)
        self.iso_hint.setVisible(False)
        layout.addWidget(self.iso_hint)
        self.warning_label = QLabel(self.tr(ARPG_WARNING))
        self.warning_label.setObjectName("arpgWarning")
        self.warning_label.setProperty("state", "warning")
        self.warning_label.setWordWrap(True)
        self.warning_label.setVisible(False)
        layout.addWidget(self.warning_label)
        self.air_warning = QLabel(self.tr(AIR_WARNING))
        self.air_warning.setObjectName("airWarning")
        self.air_warning.setProperty("state", "warning")
        self.air_warning.setWordWrap(True)
        self.air_warning.setVisible(False)
        layout.addWidget(self.air_warning)
        self.turn_card.setChecked(True)
        self.group.buttonToggled.connect(lambda *_: self._on_toggled())

    def status(self, state: WizardState) -> tuple[str, int]:
        return ("ok", 0)

    # ------------------------------------------------------------------ layout

    @property
    def in_grid(self) -> bool:
        """True when the cards are rows of three or four (else one column)."""
        return self.columns > 1

    @property
    def columns(self) -> int:
        """How many cards share a row: 4, 3 or 1."""
        return self._grid_shape[0] if self._grid_shape else 1

    def _card_width(self, columns: int) -> int:
        """How wide a card of the grid is. Three rows scroll, so the bar is counted in whether
        it is there yet or not: what is decided from this width must not change when it comes."""
        margins = self.cards_grid.contentsMargins()
        room = self.cards_scroll.width() - margins.left() - margins.right()
        if -(-len(self.cards) // columns) > 2:
            room -= self.cards_scroll.verticalScrollBar().sizeHint().width()
        return max(1, (room - (columns - 1) * self.cards_grid.horizontalSpacing()) // columns)

    def _row_needs(self, columns: int) -> list[int]:
        """How high every row of the grid has to be for its cards as they are shaped now."""
        width = self._card_width(columns)
        cards = list(self.cards.values())
        return [
            max(card.height_at(width) for card in cards[first : first + columns])
            for first in range(0, len(cards), columns)
        ]

    def _fit(self, needs: list[int], room: int, rows: int = 2) -> bool:
        """True when the first ``rows`` rows of these heights are in view together."""
        shown = needs[:rows]
        return sum(shown) + (len(shown) - 1) * self.cards_grid.verticalSpacing() <= room

    def _lay_out(self, columns: int, compact: bool) -> None:
        if (columns, compact) == self._grid_shape:
            return
        self._grid_shape = (columns, compact)
        wide = columns > 1
        for card in self.cards.values():
            self.cards_grid.removeWidget(card)
        for index, card in enumerate(self.cards.values()):
            card.set_shape("grid" if wide else "row", compact)
            self.cards_grid.addWidget(card, index // columns, index % columns)
        for column in range(WIDE_GRID_COLUMNS):
            self.cards_grid.setColumnStretch(column, 1 if column < columns else 0)
        rows = -(-len(self.cards) // columns)
        for row in range(len(self.cards) + 1):
            # the rows of the grid share the height; under a column the room that is left
            self.cards_grid.setRowStretch(row, int(row < rows if wide else row == rows))

    def _apply_shape(self) -> None:
        """Rows of four cards in a window ``WIDE_GRID_WIDTH`` wide and more (seven cards in
        two rows), rows of three from ``GRID_WIDTH`` on (two rows are in view and the third
        scrolls), with the list of each card left out while two rows of whole cards would not
        fit; below that width one column of cards, each with its drawing at the left. Whether
        two rows of whole cards fit is measured on the cards (a card of four in a row is
        narrower and higher than one of three), once for every width they have."""
        window = self.window()
        width = window.width() if window is not None else self.width()
        columns = 1
        if width >= GRID_WIDTH:
            columns = WIDE_GRID_COLUMNS if width >= WIDE_GRID_WIDTH else GRID_COLUMNS
        wide = columns > 1
        room = self.cards_scroll.viewport().height()
        key = (columns, self._card_width(columns))
        compact = wide and room < 2 * FULL_CARD_HEIGHT
        if wide and not compact and key in self._whole_rows:
            compact = not self._fit(self._whole_rows[key], room)
        self._lay_out(columns, compact)
        if wide and not compact and key not in self._whole_rows and self.isVisible():
            self._whole_rows[key] = self._row_needs(columns)  # the cards are whole: measured
            if not self._fit(self._whole_rows[key], room):
                self._lay_out(columns, True)
        self._apply_rows()

    def _apply_rows(self) -> None:
        """A grid whose rows are not all in view (three rows of three in a window of the
        default height) keeps two rows in view, which fill the room as the two rows of six
        cards did (each as high as its cards need, and what is left shared out), and the rest
        scrolls. Where not even two rows fit, every row is as high as its cards need."""
        columns = self.columns
        rows = -(-len(self.cards) // columns)
        room = self.cards_scroll.viewport().height()
        gap = self.cards_grid.verticalSpacing()
        high = [0] * (len(self.cards) + 1)
        if columns > 1 and rows > 2:
            needs = self._row_needs(columns)
            if not self._fit(needs, room, rows) and self._fit(needs, room):
                spare = room - gap - needs[0] - needs[1]
                high[0] = needs[0] + spare // 2
                high[1] = room - gap - high[0]
                for row in range(2, rows):
                    high[row] = max(needs[row], (room - gap) // 2)
        for row, least in enumerate(high):
            if self.cards_grid.rowMinimumHeight(row) != least:
                self.cards_grid.setRowMinimumHeight(row, least)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt override
        if event.type() == QEvent.Type.Resize:
            # The room of the cards changed: the shape and the rows follow. The scroll area is
            # as large as the page's layout makes it (the window was resized); its viewport is
            # lower when a hint under the cards came, and narrower only by the scroll bar,
            # which must change nothing (the bar comes and goes with what is decided here).
            if watched is self.cards_scroll:
                self._apply_shape()
            elif watched is self.cards_scroll.viewport():
                self._room_changed(event.oldSize().height(), event.size().height())  # type: ignore[attr-defined]
        return super().eventFilter(watched, event)

    def _room_changed(self, before: int, now: int) -> None:
        if before != now:
            self._apply_shape()

    def resizeEvent(self, event) -> None:  # noqa: ANN001, N802 - Qt override
        super().resizeEvent(event)
        self._apply_shape()

    def showEvent(self, event) -> None:  # noqa: ANN001, N802 - Qt override
        super().showEvent(event)
        self._whole_rows.clear()  # measured before the page had its font and its style
        self._apply_shape()  # the window is known now

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 - Qt override
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            self._whole_rows.clear()  # another font: the cards are measured again

    def _update_art(self, state: WizardState) -> None:
        """Draw the cards with the pack's art; one build per catalog."""
        if state.catalog is not None and state.catalog is self._art_catalog:
            return
        self._art_catalog = state.catalog
        try:
            art = build_scene_art(state)
        except Exception:  # noqa: BLE001 - the plain drawing is always there
            art = None
        for card in self.cards.values():
            card.mock.set_art(art)

    _art_catalog: catalog_mod.Catalog | None = None

    def _on_toggled(self) -> None:
        self._update_warning()
        self.changed.emit()

    def selected(self) -> str:
        return next((key for key, card in self.cards.items() if card.isChecked()), "turn_based")

    def _update_warning(self) -> None:
        self.warning_label.setVisible(self.arpg_card.isChecked() and not self._has_attack)
        gun = self.run_and_gun_card.isChecked()
        side = self.metroidvania_card.isChecked() or gun
        self.air_warning.setText(self.tr(AIR_WARNING_GUN if gun else AIR_WARNING))
        self.air_warning.setVisible(side and self._no_air)
        self.iso_hint.setVisible(bool(self._iso_hint) and features.ISOMETRIC_AVAILABLE)
        # what a pack is made for points at its card (T16.02), when the card can be chosen
        hints = {"shmup": SHMUP_HINT, "racing": RACING_HINT, "farm": FARM_HINT}
        made_for = hints.get(self._pack_kind, "")
        if made_for and kind_available(self._pack_kind):
            self.view_hint.setText(self.tr(made_for))
            self.view_hint.setVisible(True)
            return
        # the hint is about the side-view cards: shown when one could be chosen, and it matters
        # most for a top-down pack once such a card is chosen
        both = features.METROIDVANIA_AVAILABLE and features.RUN_AND_GUN_AVAILABLE
        hint = ""
        if features.METROIDVANIA_AVAILABLE or features.RUN_AND_GUN_AVAILABLE:
            if self._view == "side":
                hint = self.tr(SIDE_BOTH_HINT) if both else self._view_hint
            elif self._view == "top":
                hint = self.tr(TOP_DOWN_GUN_HINT) if gun else self._view_hint
        self.view_hint.setText(hint)
        self.view_hint.setVisible(bool(hint) and (side or self._view == "side"))

    def enter(self, state: WizardState) -> None:
        self._has_attack = has_attack_animation(state.catalog)
        self._view = pack_view_of(state.catalog)
        self._pack_kind = pack_kind_of(state.catalog)
        self._no_air = bool(missing_air(state.catalog))
        self._iso_hint = self._isometric_text(state.catalog)
        self.iso_hint.setText(self._iso_hint)
        self._view_hint = {"side": self.tr(SIDE_HINT), "top": self.tr(TOP_DOWN_HINT)}.get(
            self._view, ""
        )
        self._update_art(state)
        known = state.archetype in self.cards and kind_available(state.archetype)
        archetype = state.archetype if known else "turn_based"
        self.cards[archetype].setChecked(True)
        self._update_warning()
        self._apply_shape()
        if self.in_grid:  # the card's row, and no more: the rows of a grid are whole
            self.cards_scroll.ensureWidgetVisible(self.cards[archetype], 0, 0)
        else:
            self.cards_scroll.ensureWidgetVisible(self.cards[archetype])

    def _isometric_text(self, catalog: catalog_mod.Catalog | None) -> str:
        """*This pack is isometric*, with the diamond of its tiles, when a pack is; else ""."""
        packs = catalog.packs if catalog is not None else []
        if not any(catalog_mod.pack_view(pack) == "isometric" for pack in packs):
            return ""
        size = options.pack_footprint(catalog)
        return self.tr(ISO_SIZE_HINT).format(*size) if size else self.tr(ISO_HINT)

    def leave(self, state: WizardState) -> bool | None:
        from rpggen.gui.models.options_model import apply_default_view

        state.archetype = self.selected()
        cfg = state.config
        if cfg is not None and cfg.archetype != state.archetype:
            old, new = cfg.archetype, state.archetype
            if cfg.input == config_mod.default_input(old):
                cfg.input = config_mod.default_input(new)  # untouched bindings follow
            if cfg.features == config_mod.default_features(old):
                cfg.features = config_mod.default_features(new)  # and untouched features
            planned = ("metroidvania", *config_mod.ARCADE_KINDS, "farm")
            if old in planned or new in planned:
                # rooms, stages, tracks and a farm have options of their own: another kind's
                # are not taken along (the areas of a map seen from above are no default and
                # stay with such a map)
                fits = set(config_mod.starter_map_defaults(new))
                if old in TOP_DOWN_KINDS and new in TOP_DOWN_KINDS:
                    fits.add("areas")
                cfg.starter_map = {k: v for k, v in cfg.starter_map.items() if k in fits}
            cfg.archetype = new
        apply_default_view(state)  # the view of the packs, until somebody chooses (T17.16)
        return None

    _has_attack = False
    _no_air = False
    _view = ""
    _view_hint = ""
    _iso_hint = ""
    _pack_kind = ""


def pack_view_of(catalog: catalog_mod.Catalog | None) -> str:
    """``"side"`` when any analysed pack looks side-view (T14.02), ``"top"`` when none does and
    the player walks down the screen, else ``""`` (nothing to say)."""
    if catalog is None or not catalog.packs:
        return ""
    if any(catalog_mod.pack_view(pack) == "side" for pack in catalog.packs):
        return "side"
    player_id = mapping.best_for(catalog, "PLAYER")
    player = catalog.asset(player_id) if player_id else None
    animations = (catalog_mod.effective(player).get("animations") or {}) if player else {}
    return "top" if any(str(name).endswith("_down") for name in animations) else ""


def pack_kind_of(catalog: catalog_mod.Catalog | None) -> str:
    """``"shmup"``, ``"racing"`` or ``"farm"`` when an analysed pack looks made for one (T16.02,
    T17.01), else ``""``. Racing wins when the packs say several: a car in sixteen headings is
    rarer; a farm comes last, because crops and hens are in many packs."""
    if catalog is None:
        return ""
    found = {mark for pack in catalog.packs for mark in pack.warnings}
    if catalog_mod.VIEW_RACING in found:
        return "racing"
    if catalog_mod.VIEW_SHMUP in found:
        return "shmup"
    return "farm" if catalog_mod.VIEW_FARM in found else ""


def missing_air(catalog: catalog_mod.Catalog | None) -> list[str]:
    """The air animations (jump, fall) the mapped player lacks: what ASSET-030 reports."""
    if catalog is None:
        return []
    player_id = mapping.best_for(catalog, "PLAYER")
    player = catalog.asset(player_id) if player_id else None
    return requirements.missing_air_animations(player)


def has_attack_animation(catalog: catalog_mod.Catalog | None) -> bool:
    """True when any (non-excluded) asset has an ``attack_*`` animation."""
    if catalog is None:
        return False
    for asset in catalog.assets:
        if asset.status == "UNUSED":
            continue
        eff = catalog_mod.effective(asset)
        if any(name.startswith("attack_") for name in (eff.get("animations") or {})):
            return True
    return False
