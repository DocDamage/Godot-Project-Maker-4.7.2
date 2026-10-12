"""Dark and light themes: a palette and a stylesheet each, switched at run time."""

from __future__ import annotations

import atexit
import math
import re
import shutil
import sys
import tempfile
from importlib import resources
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QColor, QFocusEvent, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QWidget

from rpggen.core import app_settings

TEMPLATE = "style.qss.in"
THEMES = ("dark", "light")
SYSTEM = "system"
CHOICES = (SYSTEM, *THEMES)

# The design values of the wizard (T15.01): every colour and every size the stylesheet, the
# palette and the painting widgets use comes from here. A colour is "#rrggbb" or
# "rgba(r, g, b, a)" with a from 0 to 255, which is what a Qt stylesheet reads too.
TOKENS: dict[str, dict[str, str]] = {
    "dark": {
        "bg": "#1b1e24",  # the window
        "base": "#20232a",  # inputs, lists, the audit grid
        "surface": "#262a32",  # cards, group boxes, the detail panel
        "surface_hover": "#2d323c",  # a card or row under the pointer
        "border": "#373d48",  # 1 px lines
        "border_strong": "#6b7486",  # input borders, dividers that must be seen (3:1)
        "text": "#e6e8ec",
        "text_muted": "#9aa3b2",  # hints, captions, secondary rows
        "text_disabled": "#8a92a1",
        "accent": "#5c9bff",  # the one primary button, selection, links, the current step
        "accent_hover": "#7aaeff",
        "accent_pressed": "#4680e4",
        "on_accent": "#0b1220",  # text on the accent (white has under 3:1 on this blue)
        "focus": "#8db8ff",  # the keyboard focus ring
        "danger": "#f2706d",
        "warning": "#ffb74d",
        "success": "#66bb6a",
        "on_status": "#0b1220",  # text and icons on a danger, warning or success fill
        # the canvases (image views, the animation preview, the map preview)
        "canvas_bg": "#3c3c3c",
        "canvas_bg_alt": "#464646",
        "grid_line": "rgba(255, 255, 255, 150)",
        "diff_changed": "rgba(230, 170, 40, 70)",  # lines that differ (conflict dialog)
    },
    "light": {
        "bg": "#f5f6f8",
        "base": "#ffffff",
        "surface": "#ffffff",
        "surface_hover": "#f0f2f5",
        "border": "#d9dde3",
        "border_strong": "#868e9b",
        "text": "#1f2328",
        "text_muted": "#5f6672",
        "text_disabled": "#838993",
        "accent": "#2b67c8",
        "accent_hover": "#265bb1",
        "accent_pressed": "#214f99",
        "on_accent": "#ffffff",
        "focus": "#2b67c8",
        "danger": "#b3261e",
        "warning": "#8a5a00",
        "success": "#2e7d32",
        "on_status": "#ffffff",
        "canvas_bg": "#d9dce2",
        "canvas_bg_alt": "#cdd1d8",
        "grid_line": "rgba(20, 24, 32, 160)",
        "diff_changed": "rgba(230, 160, 20, 90)",
    },
}

# Sizes in pixels, the same in both themes. The body text is the application font, unchanged.
SIZES: dict[str, int] = {
    "space_4": 4,
    "space_8": 8,
    "space_12": 12,
    "space_16": 16,
    "space_24": 24,
    "space_32": 32,
    "radius_control": 6,
    "radius_card": 10,
    "radius_chip": 10,  # half a chip's height (Qt draws no rounding for a larger radius)
    "radius_item": 4,
    "font_caption": 12,
    "font_section": 15,
    "font_title": 18,
    "font_display": 22,
    "control_height": 30,
    "control_inner": 28,  # the height inside a 1 px border
    "control_inner_focus": 26,  # and inside the 2 px focus ring
    "pad_control": 12,
    "pad_control_focus": 11,
    "icon": 16,
}

_PLACEHOLDER = re.compile(
    r"@icon\(\s*([a-z0-9][a-z0-9-]*)\s*,\s*([a-z_0-9]+)\s*\)|@([a-z][a-z0-9_]*)"
)
_COMMENT = re.compile(r"/[*].*?[*]/", re.S)
_RGBA = re.compile(r"rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)")


def _qcolor(value: str) -> QColor:
    match = _RGBA.fullmatch(value)
    if match is not None:
        return QColor(*(int(part) for part in match.groups()))
    return QColor(value)


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
    return system_scheme() if choice == SYSTEM else (choice if choice in THEMES else "dark")


def current() -> str:
    """The theme in effect now ("dark" or "light")."""
    return _effective


def token(name: str, theme: str | None = None) -> QColor:
    """A colour of the theme in effect (or of ``theme``)."""
    return _qcolor(TOKENS[theme or _effective][name])


color = token  # the name the painting widgets use (T15.01)


def hex_of(name: str, theme: str | None = None) -> str:
    """A token as the text a stylesheet or an SVG takes ("#rrggbb")."""
    return token(name, theme).name()


def px(name: str) -> int:
    """A size of the design system in logical pixels (``px("space_16")``, ``px("radius_card")``)."""
    return SIZES[name]


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
BACKGROUNDS = {name: TOKENS[name]["base"] for name in THEMES}

ICON_FOLDER = "icons"  # beside this module: data files, not a package
_icon_root: Path | None = None


def icon_source(name: str) -> str:
    """The text of an icon of the set (``rpggen/gui/icons/<name>.svg``); KeyError when the set
    has no such icon, so a typo is found by the first test that asks for it."""
    try:
        file = resources.files("rpggen.gui").joinpath(ICON_FOLDER, f"{name}.svg")
        return file.read_text(encoding="utf-8")
    except (OSError, ModuleNotFoundError) as exc:
        raise KeyError(f"no icon named {name!r}") from exc


def icon_file(name: str, token_name: str, theme: str | None = None) -> str:
    """The path (with forward slashes, as a stylesheet's ``url()`` wants it) of an icon drawn in
    a token's colour. A stylesheet cannot colour an SVG, so the coloured copies are written to
    a folder of this process, once each, and removed when the process ends."""
    global _icon_root
    theme = theme or _effective
    if _icon_root is None or not _icon_root.is_dir():
        _icon_root = Path(tempfile.mkdtemp(prefix="rpggen-icons-"))
        atexit.register(shutil.rmtree, _icon_root, ignore_errors=True)
    path = _icon_root / theme / f"{name}__{token_name}.svg"
    if not path.is_file():
        text = icon_source(name).replace("currentColor", hex_of(token_name, theme))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return path.as_posix()


def _values(name: str) -> dict[str, str]:
    """Every placeholder of the template for a theme: the colours, the sizes with their unit,
    the six status colours of the audit grid and the body font size."""
    from rpggen.gui.widgets.asset_grid import STATUS_COLORS  # the grid owns them (not a cycle
    # at import time: the grid imports this module)

    values = dict(TOKENS[name])
    values.update({key: f"{size}px" for key, size in SIZES.items()})
    values.update({f"status_{key.lower()}": colour for key, colour in STATUS_COLORS.items()})
    return values


def render(template: str, name: str) -> str:
    """The template with every ``@token`` and ``@icon(name, token)`` replaced for a theme. A
    placeholder that is not a token raises ``KeyError``."""
    values = _values(name)

    def replace(match: re.Match[str]) -> str:
        if match.group(1) is not None:
            if match.group(2) not in TOKENS[name]:
                raise KeyError(f"stylesheet: @icon colour {match.group(2)!r} is not a token")
            return icon_file(match.group(1), match.group(2), name)
        key = match.group(3)
        if key not in values:
            raise KeyError(f"stylesheet: @{key} is not a token")
        return values[key]

    return _PLACEHOLDER.sub(replace, _COMMENT.sub("", template))


def template_text() -> str:
    return resources.files("rpggen.gui").joinpath(TEMPLATE).read_text(encoding="utf-8")


def stylesheet(name: str) -> str:
    """The stylesheet of a theme, rendered from the one template; an unknown theme is dark."""
    return render(template_text(), name if name in THEMES else "dark")


def palette(name: str) -> QPalette:
    """The application palette of a theme, from the same tokens as the stylesheet."""
    name = name if name in THEMES else "dark"
    pal = QPalette()
    roles = {
        QPalette.ColorRole.Window: "bg",
        QPalette.ColorRole.WindowText: "text",
        QPalette.ColorRole.Base: "base",
        QPalette.ColorRole.AlternateBase: "bg",
        QPalette.ColorRole.Text: "text",
        QPalette.ColorRole.Button: "surface",
        QPalette.ColorRole.ButtonText: "text",
        QPalette.ColorRole.ToolTipBase: "surface",
        QPalette.ColorRole.ToolTipText: "text",
        QPalette.ColorRole.Mid: "border_strong",
        QPalette.ColorRole.Highlight: "accent",
        QPalette.ColorRole.HighlightedText: "on_accent",
        QPalette.ColorRole.PlaceholderText: "text_muted",
        QPalette.ColorRole.Link: "accent",
    }
    for role, token_name in roles.items():
        pal.setColor(role, token(token_name, name))
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        pal.setColor(QPalette.ColorGroup.Disabled, role, token("text_disabled", name))
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
        sheet = stylesheet(_effective)
        if app.styleSheet() != sheet:  # setting it restyles every widget there is: not for
            app.setStyleSheet(sheet)  # the theme that is in effect already
        _follow_system()
    if remember:
        app_settings.update(theme=name)
    signals.changed.emit(_effective)
    return name


class FocusRing(QObject):
    """Marks the widget that got the focus **from the keyboard** with the property
    ``kbfocus="true"``, which the stylesheet draws as the 2 px focus ring (T15.02). A click
    gives focus without a ring. (The stylesheet's own ``:focus`` cannot tell the two apart, and
    the style that draws styled controls never asks a proxy style for the ring.)"""

    REASONS = (
        Qt.FocusReason.TabFocusReason,
        Qt.FocusReason.BacktabFocusReason,
        Qt.FocusReason.ShortcutFocusReason,
    )

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt override
        kind = event.type()
        if kind == QEvent.Type.FocusIn:
            if isinstance(event, QFocusEvent) and event.reason() in self.REASONS:
                self.mark(watched, True)
        elif kind == QEvent.Type.FocusOut and watched.property("kbfocus"):
            self.mark(watched, False)
        elif kind == QEvent.Type.Show and isinstance(watched, QDialogButtonBox):
            # T15.19: the accepting button of every dialog is the primary one (message boxes
            # too); done here once, so that no dialog has to remember it
            from rpggen.gui.widgets import buttons

            buttons.style_box(watched)
        return False

    @staticmethod
    def mark(widget: QObject, on: bool) -> None:
        if not isinstance(widget, QWidget):
            return
        widget.setProperty("kbfocus", "true" if on else None)
        repolish(widget)


def repolish(widget: QWidget) -> None:
    """Make the stylesheet look at a widget's properties again (a property that changes after
    the widget was shown does not restyle it by itself)."""
    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)
    # not widget.update(): an item view's own update(index) hides it in PySide6 6.7
    QWidget.update(widget)


_focus_ring: FocusRing | None = None


def install_focus_ring(app: QApplication) -> None:
    global _focus_ring
    if _focus_ring is None:
        _focus_ring = FocusRing(app)
        app.installEventFilter(_focus_ring)


def saved_theme() -> str:
    return app_settings.get().theme
