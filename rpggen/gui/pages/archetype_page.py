"""Page 2: choose turn-based or action RPG."""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QPainter, QPaintEvent, QPalette
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
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


class ArchetypeCard(QToolButton):
    """A large checkable card with a title, a two-line description and a diagram."""

    def __init__(self, key: str, title: str, text: str, steps: list[str]) -> None:
        super().__init__()
        self.key = key
        self.setObjectName(f"card_{key}")
        self.setCheckable(True)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.setMinimumSize(QSize(400, 170))
        layout = QVBoxLayout(self)
        heading = QLabel(f"<b>{title}</b>")
        heading.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        body = QLabel(text)
        body.setWordWrap(True)
        body.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(heading)
        layout.addWidget(body)
        layout.addWidget(FlowDiagram(steps))
        layout.addStretch(1)


class ArchetypePage(WizardPage):
    title = "Archetype"

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
        )
        self.arpg_card = ArchetypeCard(
            "arpg",
            self.tr("Action RPG"),
            self.tr("Fight in real time with attacks and dodges.\nLoot drops where enemies fall."),
            [self.tr("Move"), self.tr("Attack"), self.tr("Dodge"), self.tr("Loot")],
        )
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        for card in (self.turn_card, self.arpg_card):
            self.group.addButton(card)
            row.addWidget(card)
        layout.addLayout(row)
        self.arpg_card.setEnabled(features.ARPG_AVAILABLE)
        if not features.ARPG_AVAILABLE:
            self.arpg_card.setToolTip(self.tr(ARPG_TOOLTIP))
        self.warning_label = QLabel(self.tr(ARPG_WARNING))
        self.warning_label.setObjectName("arpgWarning")
        self.warning_label.setProperty("state", "warning")
        self.warning_label.setVisible(False)
        layout.addWidget(self.warning_label)
        layout.addStretch(1)
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
