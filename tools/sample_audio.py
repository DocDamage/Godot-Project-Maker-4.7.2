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


# ------------------------------------------------------------------- the arcade samples (T16.17)
# Three small packs of under 200 KB each, sounds included: these files are mono, 8-bit, 11025 Hz
# (every second sample of what the functions above make, its high byte), and their loops are one
# bar of 2.56 s.

SMALL_RATE = RATE // 2


def to_wav_small(samples: np.ndarray) -> bytes:
    """``samples`` (16-bit values at ``RATE``) as an 8-bit WAV of half the rate."""
    halved = np.clip(samples[::2], -FULL - 1, FULL)
    data = ((halved >> 8) + 128).astype(np.uint8)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(1)
        w.setframerate(SMALL_RATE)
        w.writeframes(data.tobytes())
    return buf.getvalue()


def _loop(melody: list[int], bass: list[int], step: int = 16) -> bytes:
    """One bar: sixteen melody notes of ``step`` hundredths over four bass notes; 0 is a rest."""
    lead = _voice("tri", [(freq, step) for freq in melody], 52, 1)
    low = _voice("sq", [(freq, step * 4) for freq in bass], 22, 1)
    n = min(len(lead), len(low))
    return to_wav_small(lead[:n] + low[:n])


def stage_theme() -> bytes:  # E minor, driving
    melody = [330, 392, 494, 392, 330, 392, 587, 494, 440, 494, 587, 494, 392, 330, 294, 0]
    return _loop(melody, [82, 82, 98, 73])


def boss_theme() -> bytes:  # lower and closer together
    melody = [220, 233, 220, 196, 220, 262, 247, 220, 196, 208, 196, 175, 196, 220, 208, 0]
    return _loop(melody, [55, 55, 52, 49])


def title_theme() -> bytes:  # C major, rising
    melody = [262, 330, 392, 523, 392, 330, 392, 523, 587, 523, 392, 330, 392, 330, 262, 0]
    return _loop(melody, [131, 98, 110, 98])


def race_theme() -> bytes:  # G major, quick
    melody = [392, 494, 587, 494, 392, 494, 659, 587, 523, 587, 659, 587, 494, 392, 330, 0]
    return _loop(melody, [98, 123, 131, 147])


def results_theme() -> bytes:
    melody = [523, 659, 784, 659, 523, 659, 784, 1047, 784, 659, 523, 659, 784, 659, 523, 0]
    return _loop(melody, [131, 165, 196, 131])


def _sweep(kind: str, start: int, step: int, parts: int, hundredths: int) -> np.ndarray:
    n = RATE * hundredths // 100 // parts
    make = triangle if kind == "tri" else square
    return np.concatenate([make(max(40, start + step * k), n, k * 9000) for k in range(parts)])


def shoot() -> bytes:
    return to_wav_small(_shaped(_sweep("sq", 1100, -120, 6, 9), 26, RATE // 200, 1))


def explosion() -> bytes:
    n = RATE * 32 // 100
    return to_wav_small(
        _shaped(noise(n, 17), 62, 30, 1) // 2 + _shaped(square(62, n), 36, 30, 1) // 3
    )


def bomb() -> bytes:
    low = _sweep("sq", 180, -14, 10, 50)
    n = len(low)
    return to_wav_small(_shaped(noise(n, 23), 64, 30, 1) // 2 + _shaped(low, 40, 30, 1) // 3)


def grenade() -> bytes:
    return to_wav_small(_shaped(_sweep("tri", 520, -50, 6, 16), 44, RATE // 100, 1))


def grapple() -> bytes:
    click = _shaped(noise(RATE * 3 // 100, 29), 40, 10, 1) // 2
    return to_wav_small(np.concatenate([_shaped(_sweep("sq", 500, 90, 5, 10), 24, 40, 1), click]))


def engine() -> bytes:
    """Half a second that loops: a low square with a slower one under it."""
    n = RATE // 2
    return to_wav_small(square(88, n) * 20 // 100 + square(44, n) * 14 // 100)


def skid() -> bytes:
    n = RATE * 24 // 100
    return to_wav_small(
        _shaped(noise(n, 31), 40, 200, 2) // 2 + _shaped(triangle(1240, n), 18, 200, 2)
    )


def bump() -> bytes:
    n = RATE * 10 // 100
    return to_wav_small(
        _shaped(noise(n, 37), 50, 10, 1) // 2 + _shaped(square(70, n), 40, 10, 1) // 3
    )


def lap() -> bytes:
    return to_wav_small(np.concatenate([note("tri", f, 9, 50) for f in (523, 659, 1047)]))


def countdown() -> bytes:
    return to_wav_small(note("sq", 660, 14, 30))


def _small(make) -> bytes:  # noqa: ANN001 - one of the 16-bit effects above, made small
    with wave.open(io.BytesIO(make()), "rb") as w:
        return to_wav_small(
            np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.int64)
        )


SHMUP_FILES = {
    "music/stage_theme.wav": stage_theme,
    "music/boss_theme.wav": boss_theme,
    "music/title_theme.wav": title_theme,
    "sfx/shoot.wav": shoot,
    "sfx/explosion.wav": explosion,
    "sfx/powerup.wav": lambda: _small(powerup),
    "sfx/bomb.wav": bomb,
    "sfx/hit.wav": lambda: _small(hit),
}
GUN_FILES = {
    "music/stage_theme.wav": stage_theme,
    "music/boss_theme.wav": boss_theme,
    "sfx/shoot.wav": shoot,
    "sfx/explosion.wav": explosion,
    "sfx/grenade.wav": grenade,
    "sfx/grapple.wav": grapple,
    "sfx/jump.wav": lambda: _small(jump),
    "sfx/weapon_pickup.wav": lambda: _small(powerup),
}
RACE_FILES = {
    "music/race_theme.wav": race_theme,
    "music/results_theme.wav": results_theme,
    "sfx/engine.wav": engine,
    "sfx/skid.wav": skid,
    "sfx/bump.wav": bump,
    "sfx/pickup.wav": lambda: _small(coin),
    "sfx/lap.wav": lap,
    "sfx/countdown.wav": countdown,
}


# ---------------------------------------------------------- the samples of M17 (T17.17)
# *Green acre* (a farm) has more pictures than the arcade packs and four loops, one a season,
# so its loops are shorter: eight notes over two, 1.92 s. *Stone isle* (an isometric village)
# has the two loops and the eight sounds of the top-down sample, made small.


def _short_loop(melody: list[int], bass: list[int]) -> bytes:
    """A bar of eight melody notes of 24 hundredths over two bass notes; 0 is a rest."""
    lead = _voice("tri", [(freq, 24) for freq in melody], 52, 1)
    low = _voice("sq", [(freq, 96) for freq in bass], 20, 1)
    n = min(len(lead), len(low))
    return to_wav_small(lead[:n] + low[:n])


def spring_theme() -> bytes:  # C major, rising
    return _short_loop([392, 440, 523, 587, 659, 587, 523, 0], [131, 196])


def summer_theme() -> bytes:  # G major, bright
    return _short_loop([587, 494, 392, 494, 587, 784, 659, 0], [196, 147])


def autumn_theme() -> bytes:  # A minor, falling
    return _short_loop([659, 587, 523, 440, 523, 440, 392, 0], [110, 165])


def winter_theme() -> bytes:  # D minor, slow steps
    return _short_loop([294, 349, 440, 349, 294, 262, 294, 0], [147, 110])


def hoe() -> bytes:
    n = RATE * 9 // 100
    return to_wav_small(
        _shaped(noise(n, 41), 52, 10, 1) // 2 + _shaped(square(96, n), 36, 10, 1) // 3
    )


def watering() -> bytes:
    pour = _sweep("tri", 900, -60, 6, 26)
    n = len(pour)
    return to_wav_small(_shaped(noise(n, 43), 34, 400, 2) // 2 + _shaped(pour, 14, 400, 2))


def plant() -> bytes:
    return to_wav_small(np.concatenate([note("tri", 392, 5, 44), note("tri", 587, 7, 44)]))


def harvest() -> bytes:
    return to_wav_small(np.concatenate([note("tri", f, 6, 48) for f in (523, 659, 784)]))


def cluck() -> bytes:
    one = _shaped(_sweep("sq", 760, -70, 4, 6), 24, 20, 1)
    rest = np.zeros(RATE * 4 // 100, dtype=np.int64)
    return to_wav_small(np.concatenate([one, rest, one]))


def rooster() -> bytes:
    crow = [(587, 8), (784, 8), (784, 14), (988, 26)]
    return to_wav_small(np.concatenate([note("sq", f, length, 24) for f, length in crow]))


FARM_FILES = {
    "music/spring_theme.wav": spring_theme,
    "music/summer_days.wav": summer_theme,
    "music/autumn_leaves.wav": autumn_theme,
    "music/winter_snow.wav": winter_theme,
    "sfx/hoe.wav": hoe,
    "sfx/watering.wav": watering,
    "sfx/plant.wav": plant,
    "sfx/harvest.wav": harvest,
    "sfx/sell.wav": lambda: _small(coin),
    "sfx/hen_cluck.wav": cluck,
    "sfx/rooster.wav": rooster,
    "sfx/confirm.wav": lambda: _small(confirm),
}


def village_theme() -> bytes:  # C major pentatonic: the tune of the top-down sample, one bar
    melody = [523, 440, 392, 330, 392, 440, 523, 392, 330, 294, 262, 294, 330, 392, 440, 0]
    return _loop(melody, [131, 196, 110, 147])


def fight_theme() -> bytes:  # A minor: the battle of the top-down sample, one bar
    melody = [440, 440, 523, 440, 392, 330, 392, 440, 587, 523, 440, 392, 330, 392, 330, 0]
    return _loop(melody, [110, 110, 131, 98])


ISO_FILES = {
    "music/town_theme.wav": village_theme,
    "music/battle_theme.wav": fight_theme,
    "sfx/cursor_blip.wav": lambda: _small(blip),
    "sfx/confirm.wav": lambda: _small(confirm),
    "sfx/cancel.wav": lambda: _small(cancel),
    "sfx/hit.wav": lambda: _small(hit),
    "sfx/swing.wav": lambda: _small(swing),
    "sfx/coin.wav": lambda: _small(coin),
    "sfx/chest_open.wav": lambda: _small(chest_open),
    "sfx/step.wav": lambda: _small(step),
}
