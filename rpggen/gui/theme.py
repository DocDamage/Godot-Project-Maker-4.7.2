"""Dark and light themes: a palette and a stylesheet each, switched at run time."""

from __future__ import annotations

import math
import sys
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


def crisp_scale(scale: float, ratio: float) -> float:
    """The largest scale not above ``scale`` at which one image pixel covers a whole number of
    device pixels on a screen with the device pixel ratio ``ratio`` (T13.10): at 150 % a scale
    of 2 would be 3 device pixels (fine), a scale of 3 would be 4.5 (blurred edges), so 3
    becomes 2.667 (4 device pixels). A picture shown smaller than its pixels is left alone."""
    ratio = ratio if ratio > 0 else 1.0
    device = scale * ratio
    if device < 1:
        return scale
    return math.floor(device + 1e-6) / ratio


def device_size(logical: int, ratio: float) -> int:
    """How many device pixels a length of ``logical`` pixels has on the screen."""
    return max(1, round(logical * (ratio if ratio > 0 else 1.0)))


def system_reduces_motion() -> bool:
    """Whether the operating system asks for fewer animations (Windows: "Show animations in
    Windows" turned off). False where it cannot be asked."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        enabled = ctypes.c_int(1)
        spi_getclientareaanimation = 0x1042
        ok = ctypes.windll.user32.SystemParametersInfoW(  # type: ignore[attr-defined]
            spi_getclientareaanimation, 0, ctypes.byref(enabled), 0
        )
        return bool(ok) and not enabled.value
    except (OSError, AttributeError):
        return False


def reduce_motion() -> bool:
    """The setting in effect: the user's choice, else the system's."""
    choice = app_settings.get().reduce_motion
    return system_reduces_motion() if choice == "system" else choice == "on"


def apply_motion() -> bool:
    """Turn Qt's own animated effects (menus, combos, tooltips and tool boxes that fade or roll
    in) off or on for the setting in effect. Returns that setting."""
    reduced = reduce_motion()
    for effect in (
        Qt.UIEffect.UI_AnimateMenu,
        Qt.UIEffect.UI_FadeMenu,
        Qt.UIEffect.UI_AnimateCombo,
        Qt.UIEffect.UI_AnimateTooltip,
        Qt.UIEffect.UI_FadeTooltip,
        Qt.UIEffect.UI_AnimateToolBox,
    ):
        QApplication.setEffectEnabled(effect, not reduced)
    return reduced


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
