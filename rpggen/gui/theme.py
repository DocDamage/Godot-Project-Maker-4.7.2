"""Dark and light themes: a palette and a stylesheet each, switched at run time."""

from __future__ import annotations

from importlib import resources

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from rpggen.core import app_settings

FILES = {"dark": "style.qss", "light": "style_light.qss"}
# The backgrounds the status colours must stand out from (3:1, checked by a test).
BACKGROUNDS = {"dark": "#20232a", "light": "#ffffff"}


def stylesheet(name: str) -> str:
    """The stylesheet text of a theme; an unknown or missing one falls back to the dark theme."""
    for candidate in (FILES.get(name, FILES["dark"]), FILES["dark"]):
        try:
            return resources.files("rpggen.gui").joinpath(candidate).read_text(encoding="utf-8")
        except OSError:
            continue
    return ""


def palette(name: str) -> QPalette:
    """The application palette of a theme (the stylesheets only colour a few widgets)."""
    pal = QPalette()
    if name == "light":
        window, base, text, button, mid = "#f3f4f6", "#ffffff", "#1f2328", "#e8eaee", "#c4c8d0"
        disabled, highlight, placeholder = "#8a9099", "#3d6fb4", "#6b7280"
    else:
        window, base, text, button, mid = "#2a2e37", "#20232a", "#e6e8ec", "#353a45", "#4a505c"
        disabled, highlight, placeholder = "#7b8290", "#3d6fb4", "#9aa0aa"
    roles = {
        QPalette.ColorRole.Window: window,
        QPalette.ColorRole.WindowText: text,
        QPalette.ColorRole.Base: base,
        QPalette.ColorRole.AlternateBase: window,
        QPalette.ColorRole.Text: text,
        QPalette.ColorRole.Button: button,
        QPalette.ColorRole.ButtonText: text,
        QPalette.ColorRole.ToolTipBase: base,
        QPalette.ColorRole.ToolTipText: text,
        QPalette.ColorRole.Mid: mid,
        QPalette.ColorRole.Highlight: highlight,
        QPalette.ColorRole.HighlightedText: "#ffffff",
        QPalette.ColorRole.PlaceholderText: placeholder,
        QPalette.ColorRole.Link: "#4f8fd8" if name != "light" else "#1a5fb4",
    }
    for role, colour in roles.items():
        pal.setColor(role, QColor(colour))
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        pal.setColor(QPalette.ColorGroup.Disabled, role, QColor(disabled))
    return pal


def apply_theme(name: str, *, remember: bool = True) -> str:
    """Switch the running application to a theme; returns the theme that is now active."""
    name = name if name in FILES else "dark"
    app = QApplication.instance()
    if isinstance(app, QApplication):
        app.setPalette(palette(name))
        app.setStyleSheet(stylesheet(name))
    if remember:
        app_settings.update(theme=name)
    return name


def saved_theme() -> str:
    return app_settings.load().theme
