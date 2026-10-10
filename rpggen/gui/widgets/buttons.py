"""Button kinds (T15.03): how much weight a button carries on its view.

``primary`` is the one main action of a view (the wizard's Next, Open in Godot on the Results
page, Confirm in the audit's detail panel, the accepting button of a dialog); ``secondary`` is
the plain look; ``quiet`` has no border and no fill until the pointer is over it; ``danger`` is
for the one destructive action. The stylesheet draws them from the property ``kind``.
"""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QAbstractButton, QDialogButtonBox, QPushButton

from rpggen.gui import icons, theme

PRIMARY, SECONDARY, QUIET, DANGER = "primary", "secondary", "quiet", "danger"
KINDS = (PRIMARY, SECONDARY, QUIET, DANGER)
BAR_BUTTON_WIDTH = 96  # the wizard's Back and Next: the bar does not move as the label changes


def main_action_text() -> str:
    return QCoreApplication.translate("Buttons", "main action")


def set_kind(button: QAbstractButton, kind: str) -> None:
    """Set a button's kind and restyle it (a property that is set after the widget was shown
    does not restyle it by itself). A primary button says "main action" to a screen reader."""
    if kind not in KINDS:
        raise ValueError(f"unknown button kind {kind!r}")
    was = button.property("kind")
    button.setProperty("kind", kind)
    described = button.accessibleDescription()
    marker = main_action_text()
    if kind == PRIMARY and marker not in described:
        button.setAccessibleDescription(f"{described} ({marker})" if described else marker)
    elif kind != PRIMARY and was == PRIMARY:
        button.setAccessibleDescription(
            described.replace(f" ({marker})", "").replace(marker, "").strip()
        )
    if was != kind:
        theme.repolish(button)


def kind_of(button: QAbstractButton) -> str:
    return str(button.property("kind") or SECONDARY)


def icon_only(button: QAbstractButton, name: str, text: str, kind: str = QUIET) -> None:
    """A button that shows an icon alone: ``text`` becomes its tooltip and its accessible name,
    so that the icon never carries the meaning alone."""
    button.setText("")
    button.setProperty("iconOnly", True)
    button.setToolTip(text)
    button.setAccessibleName(text)
    icons.set_icon(button, name)
    set_kind(button, kind)


_ACCEPTING = (
    QDialogButtonBox.ButtonRole.AcceptRole,
    QDialogButtonBox.ButtonRole.YesRole,
    QDialogButtonBox.ButtonRole.ApplyRole,
)


def style_box(box: QDialogButtonBox) -> None:
    """A dialog's buttons (T15.19): the accepting one is primary and the others secondary. A
    box without an accepting button (Close alone, or Close beside an action) has its closing
    button as the main action. A button marked ``danger`` or ``primary`` by the dialog itself
    is left alone, and a box that has a primary button already gets no second one."""
    all_buttons = [b for b in box.buttons() if isinstance(b, QPushButton)]
    if not all_buttons:
        return
    chosen = next((b for b in all_buttons if b.property("kind") == PRIMARY), None)
    if chosen is None:
        chosen = next((b for b in all_buttons if box.buttonRole(b) in _ACCEPTING), None)
    if chosen is None:
        chosen = next(
            (b for b in all_buttons if box.buttonRole(b) == QDialogButtonBox.ButtonRole.RejectRole),
            all_buttons[0],
        )
    for button in all_buttons:
        if button.property("kind") == DANGER:
            continue
        set_kind(button, PRIMARY if button is chosen else SECONDARY)
