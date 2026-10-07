"""Play a sound file in the wizard (T11.20). QtMultimedia is optional: the preview buttons hide
themselves when the module or an audio output device is missing."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QUrl

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
