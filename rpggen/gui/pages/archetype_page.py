"""Page 2: choose a turn-based RPG, an action RPG or a metroidvania."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QT_TRANSLATE_NOOP, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPaintEvent, QPalette, QPen, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from rpggen import features
from rpggen.core import catalog as catalog_mod
from rpggen.core import config as config_mod
from rpggen.core import mapping, requirements
from rpggen.gui import thumbnails
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

    def resizeEvent(self, event) -> None:  # noqa: ANN001, N802 - Qt override
        super().resizeEvent(event)
        need = max(44, self.height_for(self.width()))
        if need != self.minimumHeight():
            self.setMinimumHeight(need)

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
    metroidvania."""

    BACKGROUNDS = {
        "turn_based": QColor(38, 44, 60),
        "arpg": QColor(84, 130, 78),
        "metroidvania": QColor(44, 40, 66),
    }

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
        # three cards share the minimum window (T14.10): a card is as narrow as its drawing
        self.setMinimumSize(QSize(250, 300))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setProperty("card", True)  # the stylesheet draws the card and its checked border
        layout = QVBoxLayout(self)
        head = QHBoxLayout()
        heading = QLabel(title)
        heading.setProperty("role", "section")
        heading.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.check_label = QLabel("✔")
        self.check_label.setObjectName(f"check_{key}")
        self.check_label.setProperty("accentGlyph", True)
        self.check_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.check_label.setVisible(False)
        head.addWidget(heading, 1)
        head.addWidget(self.check_label)
        layout.addLayout(head)
        body = QLabel(text)
        body.setWordWrap(True)
        body.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(body)
        self.mock = MockScreen(key)
        layout.addWidget(self.mock, 1)
        self.bullet_label = QLabel(
            # a small list indent: three cards side by side leave a card little width
            "<ul style='margin-left:-22px; margin-top:0px; margin-bottom:0px'>"
            + "".join(f"<li>{b}</li>" for b in bullets)
            + "</ul>"
        )
        self.bullet_label.setWordWrap(True)
        self.bullet_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self.bullet_label)
        controls_label = QLabel(controls)
        controls_label.setWordWrap(True)
        controls_label.setProperty("muted", True)
        controls_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(controls_label)
        self.controls_label = controls_label
        layout.addWidget(FlowDiagram(steps))
        self.toggled.connect(self.check_label.setVisible)

    # below this width a card has no room for the controls line: three cards in the minimum
    # window. The generated README lists the controls in full.
    CONTROLS_WIDTH = 280

    def resizeEvent(self, event) -> None:  # noqa: ANN001, N802 - Qt override
        super().resizeEvent(event)
        self.controls_label.setVisible(self.width() >= self.CONTROLS_WIDTH)


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
        row = QHBoxLayout()
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
        self.cards = {
            "turn_based": self.turn_card,
            "arpg": self.arpg_card,
            "metroidvania": self.metroidvania_card,
        }
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        for card in self.cards.values():
            self.group.addButton(card)
            row.addWidget(card)
        layout.addLayout(row, 1)
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
        self.arpg_card.setEnabled(features.ARPG_AVAILABLE)
        if not features.ARPG_AVAILABLE:
            self.arpg_card.setToolTip(self.tr(ARPG_TOOLTIP))
        self.metroidvania_card.setEnabled(features.METROIDVANIA_AVAILABLE)
        if not features.METROIDVANIA_AVAILABLE:
            self.metroidvania_card.setToolTip(self.tr(LATER_TOOLTIP))
        # what detection says about the pack's point of view (T14.02): a suggestion, never a lock
        self.view_hint = QLabel()
        self.view_hint.setObjectName("viewHint")
        self.view_hint.setWordWrap(True)
        self.view_hint.setProperty("muted", True)
        self.view_hint.setVisible(False)
        layout.addWidget(self.view_hint)
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
        side = self.metroidvania_card.isChecked()
        self.air_warning.setVisible(side and self._no_air)
        # the hint is about the third card: shown when it could be chosen, and it matters most
        # for a top-down pack once the card is chosen
        hint = self._view_hint if features.METROIDVANIA_AVAILABLE else ""
        self.view_hint.setText(hint)
        self.view_hint.setVisible(bool(hint) and (side or self._view == "side"))

    def enter(self, state: WizardState) -> None:
        self._has_attack = has_attack_animation(state.catalog)
        self._view = pack_view_of(state.catalog)
        self._no_air = bool(missing_air(state.catalog))
        self._view_hint = {"side": self.tr(SIDE_HINT), "top": self.tr(TOP_DOWN_HINT)}.get(
            self._view, ""
        )
        self._update_art(state)
        available = {
            "turn_based": True,
            "arpg": features.ARPG_AVAILABLE,
            "metroidvania": features.METROIDVANIA_AVAILABLE,
        }
        archetype = state.archetype if available.get(state.archetype) else "turn_based"
        self.cards[archetype].setChecked(True)
        self._update_warning()

    def leave(self, state: WizardState) -> bool | None:
        state.archetype = self.selected()
        cfg = state.config
        if cfg is not None and cfg.archetype != state.archetype:
            if cfg.input == config_mod.default_input(cfg.archetype):
                cfg.input = config_mod.default_input(state.archetype)  # untouched bindings follow
            cfg.archetype = state.archetype
        return None

    _has_attack = False
    _no_air = False
    _view = ""
    _view_hint = ""


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
