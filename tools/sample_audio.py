"""Synthesize the CC0 audio of the sample pack from integer arithmetic only (T11.20).

Mono, 16-bit, 22050 Hz WAV. No floating point goes into a sample, so the bytes are the same on
every machine and every numpy version. The tunes are two voices (a triangle melody over a square
bass) that loop seamlessly because they end on a rest.
"""

from __future__ import annotations

import io
import wave

import numpy as np

RATE = 22050
FULL = 32767


def _phase(freq: int, n: int, offset: int = 0) -> np.ndarray:
    """A 16-bit phase ramp: integer frequency in Hz, ``n`` samples."""
    i = np.arange(offset, offset + n, dtype=np.int64)
    return (i * freq * 65536 // RATE) & 0xFFFF


def triangle(freq: int, n: int, offset: int = 0) -> np.ndarray:
    return (np.abs(_phase(freq, n, offset) - 32768) * 2 - 32768).astype(np.int64)


def square(freq: int, n: int, offset: int = 0) -> np.ndarray:
    return np.where(_phase(freq, n, offset) < 32768, 32767, -32768).astype(np.int64)


def noise(n: int, seed: int) -> np.ndarray:
    """Pseudo-random samples from a 32-bit linear congruential generator (pure integers)."""
    out = np.empty(n, dtype=np.int64)
    x = seed & 0xFFFFFFFF
    for k in range(n):
        x = (x * 1664525 + 1013904223) & 0xFFFFFFFF
        out[k] = (x >> 16) - 32768
    return out


def envelope(n: int, attack: int, release: int) -> np.ndarray:
    """0..1024 gain: linear attack, flat, linear release (integers)."""
    env = np.full(n, 1024, dtype=np.int64)
    attack, release = min(attack, n), min(release, n)
    if attack:
        env[:attack] = np.arange(attack, dtype=np.int64) * 1024 // attack
    if release:
        env[n - release :] = np.minimum(
            env[n - release :], np.arange(release, 0, -1, dtype=np.int64) * 1024 // release
        )
    return env


def note(kind: str, freq: int, seconds_x100: int, volume: int) -> np.ndarray:
    """One note: ``seconds_x100`` in hundredths of a second, ``volume`` 0..100."""
    n = RATE * seconds_x100 // 100
    if freq == 0:
        return np.zeros(n, dtype=np.int64)
    wave_ = triangle(freq, n) if kind == "tri" else square(freq, n)
    return wave_ * envelope(n, RATE // 100, RATE // 25) // 1024 * volume // 100


def to_wav(samples: np.ndarray) -> bytes:
    clipped = np.clip(samples, -FULL - 1, FULL).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(clipped.tobytes())
    return buf.getvalue()


def _voice(kind: str, notes: list[tuple[int, int]], volume: int, bars: int) -> np.ndarray:
    parts = [note(kind, freq, length, volume) for freq, length in notes]
    return np.concatenate(parts * bars)


# --------------------------------------------------------------------------------- the tunes

# C major pentatonic, 50 hundredths of a second per step: 12 steps = 6 s per bar, 4 bars = 24 s
_TOWN_MELODY = [
    (523, 50), (440, 50), (392, 50), (330, 50), (392, 50), (440, 50),
    (523, 50), (392, 50), (330, 50), (294, 50), (262, 50), (0, 50),
]  # fmt: skip
_TOWN_BASS = [(131, 150), (196, 150), (110, 150), (147, 150)]


def town_theme() -> bytes:
    melody = _voice("tri", _TOWN_MELODY, 55, 4)
    bass = _voice("sq", _TOWN_BASS, 22, 4)
    n = min(len(melody), len(bass))
    return to_wav(melody[:n] + bass[:n])


# A minor, 25 hundredths per step: 16 steps = 4 s per bar, 4 bars = 16 s
_BATTLE_MELODY = [
    (440, 25), (440, 25), (523, 25), (440, 25), (392, 25), (330, 25), (392, 25), (440, 25),
    (587, 25), (523, 25), (440, 25), (392, 25), (330, 25), (392, 25), (330, 25), (0, 25),
]  # fmt: skip
_BATTLE_BASS = [(110, 100), (110, 100), (131, 100), (98, 100)]


def battle_theme() -> bytes:
    melody = _voice("tri", _BATTLE_MELODY, 55, 4)
    bass = _voice("sq", _BATTLE_BASS, 26, 4)
    n = min(len(melody), len(bass))
    return to_wav(melody[:n] + bass[:n])


# ----------------------------------------------------------------------------------- effects


def _shaped(raw: np.ndarray, volume: int, attack: int = 40, release_div: int = 2) -> np.ndarray:
    n = len(raw)
    return raw * envelope(n, attack, n // release_div) // 1024 * volume // 100


def blip() -> bytes:
    return to_wav(_shaped(triangle(880, RATE * 6 // 100), 45))


def confirm() -> bytes:
    return to_wav(np.concatenate([note("tri", 660, 7, 50), note("tri", 880, 9, 50)]))


def cancel() -> bytes:
    return to_wav(np.concatenate([note("tri", 440, 7, 50), note("tri", 294, 10, 50)]))


def hit() -> bytes:
    n = RATE * 14 // 100
    body = _shaped(noise(n, 7), 60, 20, 1) // 2 + _shaped(square(110, n), 40, 20, 1) // 3
    return to_wav(body)


def swing() -> bytes:
    n = RATE * 20 // 100
    sweep = np.concatenate(
        [triangle(300 + 40 * k, n // 5, k * 10000) for k in range(5)]
    )  # rising pitch
    return to_wav(_shaped(sweep // 2 + noise(len(sweep), 11) // 5, 50, RATE // 50, 1))


def coin() -> bytes:
    return to_wav(np.concatenate([note("sq", 988, 6, 30), note("sq", 1319, 18, 30)]))


def chest_open() -> bytes:
    steps = [262, 330, 392, 523]
    return to_wav(np.concatenate([note("tri", f, 9, 55) for f in steps]))


def step() -> bytes:
    n = RATE * 5 // 100
    return to_wav(_shaped(noise(n, 3), 30, 10, 1) // 3)


def jump() -> bytes:
    n = RATE * 12 // 100
    sweep = np.concatenate([square(330 + 60 * k, n // 6, k * 7000) for k in range(6)])
    return to_wav(_shaped(sweep, 28, RATE // 100, 1))


def land() -> bytes:
    n = RATE * 7 // 100
    return to_wav(_shaped(noise(n, 5), 34, 10, 1) // 2 + _shaped(square(82, n), 30, 10, 1) // 3)


def dash() -> bytes:
    n = RATE * 16 // 100
    sweep = np.concatenate([triangle(620 - 70 * k, n // 4, k * 9000) for k in range(4)])
    return to_wav(_shaped(sweep // 3 + noise(len(sweep), 13) // 4, 46, RATE // 60, 1))


def powerup() -> bytes:
    steps = [392, 523, 659, 784, 1047]
    return to_wav(np.concatenate([note("tri", f, 8, 52) for f in steps]))


MUSIC = {"music/town_theme.wav": town_theme, "music/battle_theme.wav": battle_theme}
EFFECTS = {
    "sfx/cursor_blip.wav": blip,
    "sfx/confirm.wav": confirm,
    "sfx/cancel.wav": cancel,
    "sfx/hit.wav": hit,
    "sfx/swing.wav": swing,
    "sfx/coin.wav": coin,
    "sfx/chest_open.wav": chest_open,
    "sfx/step.wav": step,
}
FILES = {**MUSIC, **EFFECTS}
# The side-view sample pack (T14.09): the same set, and the sounds of a platformer.
SIDE_EFFECTS = {
    "sfx/jump.wav": jump,
    "sfx/land.wav": land,
    "sfx/dash.wav": dash,
    "sfx/powerup.wav": powerup,
}
SIDE_FILES = {**FILES, **SIDE_EFFECTS}
