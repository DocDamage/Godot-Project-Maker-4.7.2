"""The wizard's icons (T15.04): SVG files in ``rpggen/gui/icons`` drawn in a colour of the theme.

An icon never carries meaning alone: it sits beside its word, or the control has the word as
its tooltip and accessible name.
"""

from __future__ import annotations

import contextlib
import weakref
from typing import Protocol

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt
from PySide6.QtGui import QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from rpggen.gui import theme

DEFAULT_COLOR = "text"
DISABLED_COLOR = "text_disabled"

_pixmaps: dict[tuple[str, str, str, float, int], QPixmap] = {}


class _TakesIcon(Protocol):
    def setIcon(self, icon: QIcon) -> None: ...  # noqa: N802 - Qt's name


def _resolve(color: str | None) -> str:
    """A colour as "#rrggbb": a token's name, a literal colour, or the body text."""
    name = color or DEFAULT_COLOR
    return theme.hex_of(name) if name in theme.TOKENS[theme.current()] else name


def screen_ratio() -> float:
    app = QGuiApplication.instance()
    if isinstance(app, QGuiApplication):
        return float(app.devicePixelRatio()) or 1.0
    return 1.0


def pixmap(
    name: str, color: str | None = None, size: int = 16, ratio: float | None = None
) -> QPixmap:
    """The icon ``name`` in ``color`` (a token or a colour; the body text by default), ``size``
    logical pixels wide and high, with the device pixels of the screen (or of ``ratio``)."""
    ratio = ratio if ratio and ratio > 0 else screen_ratio()
    resolved = _resolve(color)
    key = (name, resolved, theme.current(), ratio, size)
    cached = _pixmaps.get(key)
    if cached is not None:
        return cached
    source = theme.icon_source(name).replace("currentColor", resolved)
    renderer = QSvgRenderer(QByteArray(source.encode("utf-8")))
    side = theme.device_size(size, ratio)
    result = QPixmap(side, side)
    result.fill(Qt.GlobalColor.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter, QRectF(0, 0, side, side))
    painter.end()
    result.setDevicePixelRatio(ratio)
    _pixmaps[key] = result
    return result


def icon(name: str, color: str | None = None, size: int = 16) -> QIcon:
    """A ``QIcon`` of ``name``; its disabled mode is the same drawing in the disabled text."""
    result = QIcon()
    result.addPixmap(pixmap(name, color, size), QIcon.Mode.Normal)
    result.addPixmap(pixmap(name, DISABLED_COLOR, size), QIcon.Mode.Disabled)
    return result


def clear_cache() -> None:
    _pixmaps.clear()


def cached() -> int:
    return len(_pixmaps)


class ThemedIcon:
    """Keeps the icon of a button or an action in the colours of the theme in effect: it is set
    now and again after every theme change, for as long as the holder lives."""

    def __init__(
        self, holder: _TakesIcon, name: str, color: str | None = None, size: int = 16
    ) -> None:
        self._holder = weakref.ref(holder)  # type: ignore[arg-type]
        self.name, self.color, self.size = name, color, size
        self.apply()
        theme.signals.changed.connect(self.apply)

    def apply(self, *_args: object) -> None:
        holder = self._holder()
        if holder is None:
            self._disconnect()
            return
        try:
            holder.setIcon(icon(self.name, self.color, self.size))
            set_size = getattr(holder, "setIconSize", None)
            if callable(set_size):
                set_size(QSize(self.size, self.size))
        except RuntimeError:  # the C++ object is gone before the Python one
            self._disconnect()

    def _disconnect(self) -> None:
        with contextlib.suppress(RuntimeError, TypeError):
            theme.signals.changed.disconnect(self.apply)


def set_icon(holder: _TakesIcon, name: str, color: str | None = None, size: int = 16) -> ThemedIcon:
    """Give a button or an action an icon that follows the theme. The helper is kept on the
    holder, so that nothing else has to remember it."""
    themed = ThemedIcon(holder, name, color, size)
    holder._themed_icon = themed  # type: ignore[attr-defined]
    return themed


theme.signals.changed.connect(lambda *_: clear_cache())
