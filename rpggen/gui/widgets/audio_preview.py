"""Play a sound file in the wizard (T11.20). QtMultimedia is optional: the preview buttons hide
themselves when the module or an audio output device is missing. ``WaveformView`` (T13.17) draws
a sound's decoded samples with the play head and the loop markers; it needs no audio device."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QRect, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent, QPalette, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

_player: Any = None
_output: Any = None
_checked = False
_usable = False


def available() -> bool:
    """True when QtMultimedia loads and the machine has an audio output."""
    global _checked, _usable
    if not _checked:
        _checked = True
        try:
            from PySide6.QtMultimedia import QMediaDevices

            _usable = bool(QMediaDevices.audioOutputs())
        except (ImportError, RuntimeError):
            _usable = False
    return _usable


def _ensure() -> bool:
    global _player, _output
    if not available():
        return False
    if _player is None:
        from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

        _player = QMediaPlayer()
        _output = QAudioOutput()
        _player.setAudioOutput(_output)
    return True


def play(path: Path) -> bool:
    """Start playing ``path`` (replacing what plays); False when nothing can be played."""
    if not _ensure():
        return False
    _player.stop()
    _player.setSource(QUrl.fromLocalFile(str(path)))
    _player.play()
    return True


def stop() -> None:
    if _player is not None:
        _player.stop()


def is_playing() -> bool:
    if _player is None:
        return False
    from PySide6.QtMultimedia import QMediaPlayer

    return _player.playbackState() == QMediaPlayer.PlaybackState.PlayingState


def position_ms() -> int:
    """Where the playback is, in milliseconds (0 when nothing has played)."""
    return int(_player.position()) if _player is not None else 0


# --------------------------------------------------------------------------- the waveform (T13.17)


class WaveformView(QWidget):
    """The decoded samples of a sound as columns, with a play head and, for music, the two loop
    markers. A marker is dragged with the mouse or moved with the arrow keys of the spin boxes
    beside the view; ``loopChanged(start_ms, end_ms)`` is emitted when a drag ends (one change).
    Without peaks (a file that cannot be decoded) it shows a flat bar."""

    loopChanged = Signal(int, int)  # noqa: N815
    GRAB_PX = 6
    MARGIN = 4

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("waveformView")
        self.setMinimumHeight(64)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAccessibleName(self.tr("Waveform"))
        self.peaks: list[tuple[float, float]] | None = None
        self.duration_ms = 0
        self.loop_start_ms: int | None = None
        self.loop_end_ms: int | None = None
        self.markers = False  # music only
        self.head_ms: int | None = None
        self._dragging: str | None = None

    # ------------------------------------------------------------------ data

    def set_sound(self, peaks: list[tuple[float, float]] | None, duration_ms: int) -> None:
        self.peaks = list(peaks) if peaks else None
        self.duration_ms = max(0, int(duration_ms))
        self.head_ms = None
        self.update()

    def set_loop(self, start_ms: int | None, end_ms: int | None, markers: bool = True) -> None:
        self.loop_start_ms, self.loop_end_ms, self.markers = start_ms, end_ms, markers
        self.update()

    def set_head(self, ms: int | None) -> None:
        if ms != self.head_ms:
            self.head_ms = ms
            self.update()

    def loop(self) -> tuple[int, int]:
        """The loop as it is drawn: a missing start is 0, a missing end the end of the track."""
        start = self.loop_start_ms or 0
        end = self.loop_end_ms if self.loop_end_ms else self.duration_ms
        return start, max(start, end)

    # ------------------------------------------------------------------ geometry

    def _span(self) -> int:
        return max(1, self.width() - 2 * self.MARGIN)

    def x_of(self, ms: int) -> int:
        if self.duration_ms <= 0:
            return self.MARGIN
        return self.MARGIN + round(
            self._span() * min(max(ms, 0), self.duration_ms) / self.duration_ms
        )

    def ms_at(self, x: float) -> int:
        if self.duration_ms <= 0:
            return 0
        part = min(max((x - self.MARGIN) / self._span(), 0.0), 1.0)
        return round(part * self.duration_ms)

    def marker_at(self, x: float) -> str | None:
        """ "start" or "end" when ``x`` is on a loop marker (the nearer one wins)."""
        if not self.markers or self.duration_ms <= 0:
            return None
        start, end = self.loop()
        near = {"start": abs(x - self.x_of(start)), "end": abs(x - self.x_of(end))}
        name = min(near, key=lambda k: near[k])
        return name if near[name] <= self.GRAB_PX else None

    # ------------------------------------------------------------------ mouse

    def drag_to(self, which: str, ms: int) -> None:
        """Move one marker (the other one stays; they never cross)."""
        start, end = self.loop()
        if which == "start":
            start = min(max(0, ms), max(0, end - 1))
        else:
            end = max(min(self.duration_ms, ms), start + 1)
        self.loop_start_ms, self.loop_end_ms = start, end
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._dragging = self.marker_at(event.position().x())
        if self._dragging is None:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        x = event.position().x()
        if self._dragging is not None:
            self.drag_to(self._dragging, self.ms_at(x))
            return
        on_marker = self.marker_at(x) is not None
        self.setCursor(Qt.CursorShape.SizeHorCursor if on_marker else Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._dragging is None:
            super().mouseReleaseEvent(event)
            return
        self._dragging = None
        start, end = self.loop()
        self.loopChanged.emit(start, end)

    # ------------------------------------------------------------------ drawing

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        palette = self.palette()
        painter.fillRect(self.rect(), palette.color(QPalette.ColorRole.Base))
        mid = self.height() // 2
        half = max(1, mid - 3)
        ink = palette.color(QPalette.ColorRole.Highlight)
        if self.markers and self.duration_ms > 0:
            start, end = self.loop()
            shade = QColor(ink)
            shade.setAlpha(40)
            painter.fillRect(
                QRect(
                    self.x_of(start), 0, max(1, self.x_of(end) - self.x_of(start)), self.height()
                ),
                shade,
            )
        painter.setPen(QPen(ink, 1))
        if self.peaks:
            count = len(self.peaks)
            for x in range(self._span()):
                low, high = self.peaks[min(count - 1, x * count // self._span())]
                top = mid - round(max(0.0, high) * half)
                bottom = mid + round(max(0.0, -low) * half)
                painter.drawLine(self.MARGIN + x, min(top, mid), self.MARGIN + x, max(bottom, mid))
        else:  # nothing decoded: a flat bar
            painter.drawLine(self.MARGIN, mid, self.width() - self.MARGIN, mid)
        if self.markers and self.duration_ms > 0:
            text = palette.color(QPalette.ColorRole.Text)
            painter.setPen(QPen(text, 2))
            for ms in self.loop():
                painter.drawLine(self.x_of(ms), 0, self.x_of(ms), self.height())
        if self.head_ms is not None and self.duration_ms > 0:
            painter.setPen(QPen(palette.color(QPalette.ColorRole.BrightText), 1))
            painter.drawLine(self.x_of(self.head_ms), 0, self.x_of(self.head_ms), self.height())
        painter.end()
