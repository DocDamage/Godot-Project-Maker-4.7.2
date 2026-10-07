"""Page 2: choose turn-based or action RPG."""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPalette, QPen
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
from rpggen.gui.pages.base import WizardPage
from rpggen.gui.state import WizardState

ARPG_WARNING = "ARPG will use a generic swing effect until you add attack animations."
ARPG_TOOLTIP = "Coming in a later version"


class FlowDiagram(QWidget):
    """Boxes joined by arrows, drawn with QPainter (no images)."""

    def __init__(self, steps: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.steps = steps
        self.setMinimumSize(QSize(360, 44))
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = self.palette()
        line = palette.color(QPalette.ColorRole.WindowText)
        fill = palette.color(QPalette.ColorRole.Base)
        n = len(self.steps)
        gap = 18.0
        box_w = (self.width() - gap * (n - 1) - 2) / n
        box_h = min(30.0, self.height() - 4.0)
        top = (self.height() - box_h) / 2
        painter.setPen(line)
        for i, text in enumerate(self.steps):
            x = 1 + i * (box_w + gap)
            rect = QRectF(x, top, box_w, box_h)
            painter.setBrush(fill)
            painter.drawRoundedRect(rect, 4, 4)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
            if i < n - 1:
                y = top + box_h / 2
                x0, x1 = x + box_w + 2, x + box_w + gap - 2
                painter.drawLine(int(x0), int(y), int(x1), int(y))
                painter.drawLine(int(x1), int(y), int(x1 - 4), int(y - 3))
                painter.drawLine(int(x1), int(y), int(x1 - 4), int(y + 3))
        painter.end()


class MockScreen(QWidget):
    """A drawing of what the game looks like, made with QPainter (no pictures): two battlers, a
    command box and HP rows for the turn-based game; a room, a swing and a HUD bar for the action
    game."""

    def __init__(self, kind: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.kind = kind
        self.setMinimumSize(QSize(240, 130))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(2, 2, -2, -2)
        painter.setPen(QPen(QColor(20, 20, 24), 2))
        painter.setBrush(QColor(38, 44, 60) if self.kind == "turn_based" else QColor(84, 130, 78))
        painter.drawRoundedRect(rect, 6, 6)
        w, h = rect.width(), rect.height()
        x0, y0 = rect.left(), rect.top()
        painter.setPen(Qt.PenStyle.NoPen)
        if self.kind == "turn_based":
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
        self.setMinimumSize(QSize(360, 300))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(
            "QToolButton { border: 2px solid #6b7280; border-radius: 8px; padding: 6px; }"
            "QToolButton:checked { border: 4px solid #3d6fb4; }"
        )
        layout = QVBoxLayout(self)
        head = QHBoxLayout()
        heading = QLabel(f"<b style='font-size:15px'>{title}</b>")
        heading.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.check_label = QLabel("✔")
        self.check_label.setObjectName(f"check_{key}")
        self.check_label.setStyleSheet("color: #3d6fb4; font-size: 20px; font-weight: bold;")
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
        self.bullet_label = QLabel("<ul>" + "".join(f"<li>{b}</li>" for b in bullets) + "</ul>")
        self.bullet_label.setWordWrap(True)
        self.bullet_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self.bullet_label)
        controls_label = QLabel(controls)
        controls_label.setWordWrap(True)
        controls_label.setProperty("muted", True)
        controls_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(controls_label)
        layout.addWidget(FlowDiagram(steps))
        self.toggled.connect(self.check_label.setVisible)


class ArchetypePage(WizardPage):
    title = "Archetype"
    help_anchor = "3. Using a pack you bought"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
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
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        for card in (self.turn_card, self.arpg_card):
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
        self.warning_label = QLabel(self.tr(ARPG_WARNING))
        self.warning_label.setObjectName("arpgWarning")
        self.warning_label.setProperty("state", "warning")
        self.warning_label.setVisible(False)
        layout.addWidget(self.warning_label)
        self.turn_card.setChecked(True)
        self.group.buttonToggled.connect(lambda *_: self._on_toggled())

    def _on_toggled(self) -> None:
        self._update_warning()
        self.changed.emit()

    def selected(self) -> str:
        return "arpg" if self.arpg_card.isChecked() else "turn_based"

    def _update_warning(self) -> None:
        self.warning_label.setVisible(self.arpg_card.isChecked() and not self._has_attack)

    def enter(self, state: WizardState) -> None:
        self._has_attack = has_attack_animation(state.catalog)
        archetype = (
            state.archetype
            if state.archetype == "turn_based" or features.ARPG_AVAILABLE
            else "turn_based"
        )
        (self.arpg_card if archetype == "arpg" else self.turn_card).setChecked(True)
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
