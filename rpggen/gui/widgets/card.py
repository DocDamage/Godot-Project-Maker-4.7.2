"""Cards (T15.08): the three card-shaped things of the wizard.

``Card`` is a surface with a border and rounded corners; ``Banner`` is a one-line card with an
icon and a kind that colours its left edge; ``CardButton`` is a whole card that is a button.
The stylesheet draws all three from properties, so they follow the theme.
"""

from __future__ import annotations

import contextlib

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from rpggen.gui import icons, theme
from rpggen.gui.widgets import buttons

INFO, WARNING, DANGER, SUCCESS = "info", "warning", "danger", "success"
BANNER_ICONS = {
    INFO: ("info", "accent"),
    WARNING: ("alert-triangle", "warning"),
    DANGER: ("x-circle", "danger"),
    SUCCESS: ("check-circle", "success"),
}


class Card(QFrame):
    """A surface for a group of things. ``interactive`` adds the hover look and the pointer."""

    def __init__(
        self, parent: QWidget | None = None, *, interactive: bool = False, margin: int | None = None
    ) -> None:
        super().__init__(parent)
        self.setProperty("card", True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        if interactive:
            self.setProperty("interactive", True)
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.box = QVBoxLayout(self)
        pad = theme.px("space_16") if margin is None else margin
        self.box.setContentsMargins(pad, pad, pad, pad)
        self.box.setSpacing(theme.px("space_8"))

    def add_heading(self, text: str, *trailing: QWidget) -> QLabel:
        """A section heading at the top of the card, with ``trailing`` widgets at its right."""
        heading = QLabel(text)
        heading.setProperty("role", "section")
        if not trailing:
            self.box.addWidget(heading)
            return heading
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(heading)
        row.addStretch(1)
        for widget in trailing:
            row.addWidget(widget)
        self.box.addLayout(row)
        return heading


class Banner(QFrame):
    """A line that says how things stand: an icon, a text that wraps, and room for one or two
    buttons at the right. Its kind (info, warning, danger, success) colours the left edge and
    the icon; the kind's word is in the accessible name, so the colour is never the only cue."""

    def __init__(self, kind: str = INFO, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("card", True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.kind = ""
        # as high with a button at its right as without one
        self.setMinimumHeight(theme.px("control_height") + 2 * theme.px("space_8"))
        row = QHBoxLayout(self)
        row.setContentsMargins(
            theme.px("space_12"), theme.px("space_8"), theme.px("space_12"), theme.px("space_8")
        )
        row.setSpacing(theme.px("space_8"))
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(QSize(theme.px("icon"), theme.px("icon")))
        row.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignTop)
        texts = QVBoxLayout()
        texts.setContentsMargins(0, 0, 0, 0)
        texts.setSpacing(2)
        self.text_label = QLabel(text)
        self.text_label.setWordWrap(True)
        self.text_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.detail_label = QLabel()
        self.detail_label.setWordWrap(True)
        self.detail_label.setProperty("role", "caption")
        self.detail_label.setVisible(False)
        texts.addWidget(self.text_label)
        texts.addWidget(self.detail_label)
        row.addLayout(texts, 1)
        self.action_row = QHBoxLayout()
        self.action_row.setContentsMargins(0, 0, 0, 0)
        self.action_row.setSpacing(theme.px("space_8"))
        row.addLayout(self.action_row)
        self.set_kind(kind)
        theme.signals.changed.connect(self._redraw)

    def set_kind(self, kind: str) -> None:
        if kind not in BANNER_ICONS:
            raise ValueError(f"unknown banner kind {kind!r}")
        changed = kind != self.kind
        self.kind = kind
        self.setProperty("banner", kind)
        self._redraw()
        if changed:
            theme.repolish(self)

    def _redraw(self, *_args: object) -> None:
        try:
            name, colour = BANNER_ICONS[self.kind]
            self.icon_label.setPixmap(icons.pixmap(name, colour, theme.px("icon")))
        except RuntimeError:  # deleted while a theme change was on its way
            pass

    def set_text(self, text: str, detail: str = "") -> None:
        self.text_label.setText(text)
        self.detail_label.setText(detail)
        self.detail_label.setVisible(bool(detail))
        self.setAccessibleName(f"{self.kind}: {text}")

    def text(self) -> str:
        return self.text_label.text()

    def setText(self, text: str) -> None:  # noqa: N802 - the name a label has
        self.set_text(text)

    def add_action(self, widget: QWidget) -> None:
        self.action_row.addWidget(widget)


class CardButton(QPushButton):
    """A card that is one button: an icon, a title, a description that wraps, and optionally a
    small button under them (``add_footer``). Tab reaches it, Enter and Space press it."""

    def __init__(
        self, title: str, description: str, icon_name: str = "", parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setProperty("kind", "card")
        self.setAccessibleName(title)
        self.setAccessibleDescription(description)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # as high as its content needs, and as high as the tallest card of its row
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self._icon_name = icon_name
        self._menu: QMenu | None = None
        pad = theme.px("space_16")
        self.inner = QVBoxLayout(self)
        self.inner.setContentsMargins(pad, pad, pad, pad)
        self.inner.setSpacing(theme.px("space_8"))
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(QSize(24, 24))
        self.icon_label.setVisible(bool(icon_name))
        self.title_label = QLabel(title)
        self.title_label.setProperty("role", "section")
        self.description_label = QLabel(description)
        self.description_label.setWordWrap(True)
        self.description_label.setProperty("muted", True)
        for label in (self.icon_label, self.title_label, self.description_label):
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.inner.addWidget(self.icon_label)
        self.inner.addWidget(self.title_label)
        self.inner.addWidget(self.description_label)
        self.inner.addStretch(1)
        self._redraw()
        theme.signals.changed.connect(self._redraw)

    def _redraw(self, *_args: object) -> None:
        if not self._icon_name:
            return
        with contextlib.suppress(RuntimeError):
            self.icon_label.setPixmap(icons.pixmap(self._icon_name, "accent", 24))

    def add_footer(self, text: str) -> QPushButton:
        """A quiet button under the description (the sample card's *Choose a sample*)."""
        footer = QPushButton(text, self)
        buttons.set_kind(footer, buttons.QUIET)
        self.inner.addWidget(footer, 0, Qt.AlignmentFlag.AlignLeft)
        return footer

    def set_choices(self, menu: QMenu) -> None:
        self._menu = menu

    def menu(self) -> QMenu | None:  # type: ignore[override]
        """The menu of the card's footer button, when it has one (the card itself is a plain
        button: a click on it never opens the menu)."""
        return self._menu

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt override
        hint = self.inner.sizeHint()
        return QSize(max(hint.width(), 200), max(hint.height(), self.minimumHeight()))

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - Qt override
        hint = self.inner.minimumSize()
        return QSize(max(hint.width(), 160), max(hint.height(), self.minimumHeight()))
