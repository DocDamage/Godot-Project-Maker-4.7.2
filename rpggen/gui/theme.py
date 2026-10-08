"""Dark and light themes: a palette and a stylesheet each, switched at run time."""

from __future__ import annotations

from importlib import resources

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication

from rpggen.core import app_settings

FILES = {"dark": "style.qss", "light": "style_light.qss"}
SYSTEM = "system"
CHOICES = (SYSTEM, "dark", "light")

# Colours the canvases (image views, the animation preview, the map preview) take from the theme,
# so that a light window has no dark boxes. The transparency checkerboard keeps its own greys.
TOKENS: dict[str, dict[str, QColor]] = {
    "dark": {
        "canvas_bg": QColor("#3c3c3c"),
        "canvas_bg_alt": QColor("#464646"),
        "grid_line": QColor(255, 255, 255, 150),
        "diff_changed": QColor(230, 170, 40, 70),  # lines that differ (conflict dialog)
    },
    "light": {
        "canvas_bg": QColor("#d9dce2"),
        "canvas_bg_alt": QColor("#cdd1d8"),
        "grid_line": QColor(20, 24, 32, 160),
        "diff_changed": QColor(230, 160, 20, 90),
    },
}


class ThemeSignals(QObject):
    changed = Signal(str)  # the theme now in effect ("dark" or "light")


signals = ThemeSignals()
_effective = "dark"
_choice = SYSTEM
_watching = False


def system_scheme() -> str:
    """ "dark" or "light": what the operating system asks for (dark when it does not say)."""
    hints = QGuiApplication.styleHints()
    scheme = hints.colorScheme() if hints is not None else Qt.ColorScheme.Unknown
    return "light" if scheme == Qt.ColorScheme.Light else "dark"


def resolve(choice: str) -> str:
    """The theme in effect for a choice: "system" is whatever the system says."""
    return system_scheme() if choice == SYSTEM else (choice if choice in FILES else "dark")


def current() -> str:
    """The theme in effect now ("dark" or "light")."""
    return _effective


def token(name: str, theme: str | None = None) -> QColor:
    """A canvas colour of the theme in effect (or of ``theme``)."""
    return QColor(TOKENS[theme or _effective][name])


def _follow_system() -> None:
    """Re-apply "system" whenever the operating system changes its colour scheme."""
    global _watching
    if _watching:
        return
    hints = QGuiApplication.styleHints()
    if hints is not None:
        hints.colorSchemeChanged.connect(on_system_scheme_changed)
        _watching = True


def on_system_scheme_changed(*_args: object) -> None:
    """The system changed its scheme: a window on "system" follows it, any other stays."""
    if _choice == SYSTEM:
        apply_theme(SYSTEM, remember=False)


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
    """Switch the running application to a theme ("system", "dark" or "light"); returns the
    choice now active. An unknown name is the dark theme."""
    global _effective, _choice
    name = name if name in CHOICES else "dark"
    _choice = name
    _effective = resolve(name)
    app = QApplication.instance()
    if isinstance(app, QApplication):
        app.setPalette(palette(_effective))
        app.setStyleSheet(stylesheet(_effective))
        _follow_system()
    if remember:
        app_settings.update(theme=name)
    signals.changed.emit(_effective)
    return name


def saved_theme() -> str:
    return app_settings.get().theme
