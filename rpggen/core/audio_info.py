"""Audio facts: durations without third-party code (T11.03), and peaks and a loop guess from
the decoded samples through soundfile (libsndfile, T13.17).

Reads just enough of WAV, Ogg (Vorbis, Opus), MP3 and FLAC to tell how long a file is. The
classifier only needs "is this longer than about 20 s", so MP3 without a Xing header is estimated
from its first frame's bitrate. Anything unreadable gives ``None``; nothing here raises.
"""

from __future__ import annotations

import contextlib
import struct
import wave
from pathlib import Path
from typing import Any

READ_CAP = 256 * 1024
OGG_TAIL = 64 * 1024

_MP3_BITRATES = {  # (version family, layer) -> kbit/s by index 1..14
    ("1", 1): [32, 64, 96, 128, 160, 192, 224, 256, 288, 320, 352, 384, 416, 448],
    ("1", 2): [32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384],
    ("1", 3): [32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320],
    ("2", 1): [32, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256],
    ("2", 2): [8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160],
    ("2", 3): [8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160],
}
_MP3_RATES = {"1": [44100, 48000, 32000], "2": [22050, 24000, 16000], "2.5": [11025, 12000, 8000]}


def duration_seconds(path: Path) -> float | None:
    """Length in seconds of a WAV, OGG, MP3 or FLAC file; ``None`` when it cannot be told."""
    suffix = path.suffix.lower()
    try:
        if suffix in (".wav", ".wave"):
            return _wav(path)
        with path.open("rb") as handle:
            head = handle.read(READ_CAP)
            if suffix in (".ogg", ".oga", ".opus") or head.startswith(b"OggS"):
                return _ogg(handle, head)
            if suffix == ".flac" or head.startswith(b"fLaC"):
                return _flac(head)
            if suffix in (".mp3", ".mp2"):
                return _mp3(head, path.stat().st_size)
    except (OSError, ValueError, struct.error, IndexError, OverflowError):
        return None
    return None


def format_duration(seconds: float | None) -> str:
    """``3.2 s`` under ten seconds, ``0:42`` or ``2:05`` above; an unknown length is ``--``."""
    if seconds is None:
        return "--"
    if seconds < 10:
        return f"{seconds:.1f} s"
    whole = round(seconds)
    return f"{whole // 60}:{whole % 60:02d}"


WAVE_SAMPLE_FRAMES = 1024


def waveform(path: Path, bins: int = 40) -> list[float] | None:
    """Peak level (0 to 1) of ``bins`` evenly spaced slices of a WAV file, read with the standard
    ``wave`` module by sampling a short run of frames in each slice. Other formats and files that
    cannot be read give ``None``."""
    if path.suffix.lower() not in (".wav", ".wave"):
        return None
    try:
        with wave.open(str(path), "rb") as w:
            frames, width, channels = w.getnframes(), w.getsampwidth(), w.getnchannels()
            if frames <= 0 or width not in (1, 2, 3, 4) or channels <= 0:
                return None
            full = 128 if width == 1 else 1 << (8 * width - 1)
            step = width * channels
            peaks: list[float] = []
            for i in range(bins):
                w.setpos(frames * i // bins)
                data = w.readframes(min(WAVE_SAMPLE_FRAMES, max(1, frames // bins)))
                top = 0
                for at in range(0, len(data) - width + 1, step):
                    chunk = data[at : at + width]
                    if width == 1:
                        value = chunk[0] - 128
                    else:
                        value = int.from_bytes(chunk, "little", signed=True)
                    top = max(top, abs(value))
                peaks.append(min(1.0, top / full))
            return peaks
    except (wave.Error, OSError, EOFError, ValueError):
        return None


def _wav(path: Path) -> float | None:
    with contextlib.suppress(wave.Error, OSError, EOFError), wave.open(str(path), "rb") as w:
        rate = w.getframerate()
        return w.getnframes() / float(rate) if rate else None
    return None


# ------------------------------------------------------------------------------------- ogg


def _ogg(handle, head: bytes) -> float | None:  # type: ignore[no-untyped-def]
    if not head.startswith(b"OggS") or len(head) < 28:
        return None
    nsegs = head[26]
    packet = head[27 + nsegs : 27 + nsegs + 64]
    pre_skip = 0
    if packet[:7] == b"\x01vorbis":
        rate = struct.unpack_from("<I", packet, 12)[0]
    elif packet[:8] == b"OpusHead":
        rate = 48000
        pre_skip = struct.unpack_from("<H", packet, 10)[0]
    else:
        return None
    if rate <= 0:
        return None
    handle.seek(0, 2)
    size = handle.tell()
    base = max(0, size - OGG_TAIL)
    handle.seek(base)
    tail = handle.read(OGG_TAIL)
    at = len(tail)
    while True:
        at = tail.rfind(b"OggS", 0, at)
        if at < 0 or base + at == 0:  # no later page: only the first page is there
            return None
        if at + 14 <= len(tail) and tail[at + 4] == 0:
            granule = struct.unpack_from("<q", tail, at + 6)[0]
            if granule >= 0:
                break
        # a partial page or a false positive: look further back
    return max(0.0, (granule - pre_skip) / rate)


# ------------------------------------------------------------------------------------- flac


def _flac(head: bytes) -> float | None:
    if not head.startswith(b"fLaC") or len(head) < 26 or (head[4] & 0x7F) != 0:
        return None
    info = head[8:42]
    rate = (info[10] << 12) | (info[11] << 4) | (info[12] >> 4)
    total = ((info[13] & 0x0F) << 32) | int.from_bytes(info[14:18], "big")
    if rate <= 0 or total <= 0:
        return None
    return total / rate


# -------------------------------------------------------------------------------------- mp3


def _id3_size(head: bytes) -> int:
    if len(head) >= 10 and head[:3] == b"ID3":
        size = ((head[6] & 0x7F) << 21) | ((head[7] & 0x7F) << 14) | ((head[8] & 0x7F) << 7)
        size |= head[9] & 0x7F
        return 10 + size + (10 if head[5] & 0x10 else 0)
    return 0


def _frame(head: bytes, at: int) -> tuple[str, int, int, int, int, bool] | None:
    """(version, layer, bitrate bit/s, sample rate, samples per frame, mono) or None."""
    if at + 4 > len(head):
        return None
    word = int.from_bytes(head[at : at + 4], "big")
    if (word >> 21) & 0x7FF != 0x7FF:
        return None
    version_bits = (word >> 19) & 3
    layer_bits = (word >> 17) & 3
    bitrate_idx = (word >> 12) & 15
    rate_idx = (word >> 10) & 3
    if version_bits == 1 or layer_bits == 0 or bitrate_idx in (0, 15) or rate_idx == 3:
        return None
    version = {3: "1", 2: "2", 0: "2.5"}[version_bits]
    layer = 4 - layer_bits
    family = "1" if version == "1" else "2"
    bitrate = _MP3_BITRATES[(family, layer)][bitrate_idx - 1] * 1000
    rate = _MP3_RATES[version][rate_idx]
    if layer == 1:
        samples = 384
    elif layer == 2 or version == "1":
        samples = 1152
    else:
        samples = 576
    mono = ((word >> 6) & 3) == 3
    return version, layer, bitrate, rate, samples, mono


def _mp3(head: bytes, file_size: int) -> float | None:
    start = _id3_size(head)
    at = start
    limit = min(len(head) - 4, start + 8192)
    found = None
    while at < limit:
        if head[at] == 0xFF and (frame := _frame(head, at)) is not None:
            # a second frame header right after this one makes a false sync unlikely
            length = _frame_length(frame, head, at)
            if length and (_frame(head, at + length) is not None or at + length >= len(head) - 4):
                found = (at, frame)
                break
        at += 1
    if found is None:
        return None
    at, (version, layer, bitrate, rate, samples, mono) = found
    if layer == 3:
        side = (9 if mono else 17) if version != "1" else (17 if mono else 32)
        tag = at + 4 + side
        if head[tag : tag + 4] in (b"Xing", b"Info") and len(head) >= tag + 12:
            flags = struct.unpack_from(">I", head, tag + 4)[0]
            if flags & 1:
                frames = struct.unpack_from(">I", head, tag + 8)[0]
                if frames > 0:
                    return frames * samples / rate
    audio_bytes = max(0, file_size - at)
    return audio_bytes * 8 / bitrate if bitrate else None


def _frame_length(frame: tuple[str, int, int, int, int, bool], head: bytes, at: int) -> int:
    _version, layer, bitrate, rate, samples, _mono = frame
    padding = (head[at + 2] >> 1) & 1
    if layer == 1:
        return (12 * bitrate // rate + padding) * 4
    return samples // 8 * bitrate // rate + padding


# ------------------------------------------------------------- decoded audio (T13.17)

PEAK_BLOCK_FRAMES = 65536
LOOP_WINDOW_MS = 50
LOOP_MIN_START_S = 1.0
LOOP_MIN_LENGTH_S = 2.0
LOOP_CONTEXT_S = 0.4
LOOP_MAX_WINDOWS = 6000


def soundfile_module() -> Any | None:
    """The ``soundfile`` module (libsndfile), or None when it cannot be loaded."""
    try:
        import soundfile  # type: ignore[import-untyped]
    except (ImportError, OSError):  # OSError: the libsndfile library itself is missing
        return None
    return soundfile


def peaks(path: Path, columns: int = 96) -> list[tuple[float, float]] | None:
    """(lowest, highest) sample of ``columns`` equal slices of the file, each from -1 to 1, over
    the decoded samples (the channels averaged). WAV, OGG Vorbis, FLAC and MP3 through libsndfile;
    the file is read in blocks, so a long track never sits in memory at once. ``None`` when the
    file cannot be decoded: the caller draws a flat bar. Never raises."""
    sf = soundfile_module()
    if sf is None or columns <= 0:
        return None
    try:
        with sf.SoundFile(str(path)) as handle:
            frames = int(handle.frames)
            if frames <= 0:
                return None
            low = [0.0] * columns
            high = [0.0] * columns
            at = 0
            for block in handle.blocks(
                blocksize=PEAK_BLOCK_FRAMES, dtype="float32", always_2d=True
            ):
                mono = block.mean(axis=1)
                count = len(mono)
                if count == 0 or at >= frames:
                    break
                first = at * columns // frames
                last = min(columns - 1, (at + count - 1) * columns // frames)
                for column in range(first, last + 1):
                    start = max(0, -(-column * frames // columns) - at)
                    stop = min(count, -(-(column + 1) * frames // columns) - at)
                    if stop > start:
                        part = mono[start:stop]
                        low[column] = min(low[column], float(part.min()))
                        high[column] = max(high[column], float(part.max()))
                at += count
    except Exception:  # noqa: BLE001 - whatever libsndfile says, the card shows a flat bar
        return None
    return [(max(-1.0, lo), min(1.0, hi)) for lo, hi in zip(low, high, strict=True)]


def _envelope(path: Path, window_ms: int) -> tuple[Any, float] | None:
    """(RMS of every window as a numpy array, the window's length in seconds)."""
    import numpy

    sf = soundfile_module()
    if sf is None:
        return None
    try:
        with sf.SoundFile(str(path)) as handle:
            rate, frames = int(handle.samplerate), int(handle.frames)
            if rate <= 0 or frames <= 0:
                return None
            window = max(1, rate * window_ms // 1000)
            while frames // window > LOOP_MAX_WINDOWS:  # a very long track: coarser windows
                window *= 2
            values: list[float] = []
            for block in handle.blocks(blocksize=window * 256, dtype="float32", always_2d=True):
                mono = block.mean(axis=1)
                whole = len(mono) // window
                if whole:
                    cut = mono[: whole * window].reshape(whole, window)
                    values.extend(numpy.sqrt((cut * cut).mean(axis=1)).tolist())
    except Exception:  # noqa: BLE001
        return None
    return numpy.asarray(values, dtype="float64"), window / rate


def guess_loop(path: Path) -> tuple[int, int] | None:
    """A loop for a music track as (start ms, end ms), or None when the file cannot be decoded or
    is too short. Of all pairs of 50 ms windows at least two seconds apart, the first one after
    the first second, it takes the pairs whose surroundings sound most alike (the smallest
    difference of the RMS level over the 0.4 s after each window, or before it when the track
    ends there) and of those the pair furthest apart: jumping from the end to the start then
    continues the way the track itself went on."""
    import numpy

    found = _envelope(path, LOOP_WINDOW_MS)
    if found is None:
        return None
    env, seconds = found
    count = len(env)
    first = int(-(-LOOP_MIN_START_S // seconds))
    shortest = max(1, int(-(-LOOP_MIN_LENGTH_S // seconds)))
    context = max(2, round(LOOP_CONTEXT_S / seconds))
    if count < first + shortest or first < context:
        return None
    best: list[tuple[float, int, int]] = []  # (difference, start, lag) of every lag's best start
    for lag in range(shortest, count - first + 1):
        starts = numpy.arange(first, count - lag + 1)
        ends = starts + lag
        diff = numpy.abs(env[: count - lag] - env[lag:])  # diff[i] compares windows i and i + lag
        total = numpy.concatenate(([0.0], numpy.cumsum(diff)))
        ahead = numpy.minimum(starts + context, count - lag)  # the windows after both ends
        forward = (total[ahead] - total[starts]) / numpy.maximum(1, ahead - starts)
        backward = (total[starts] - total[starts - context]) / context
        value = numpy.where(ends + context <= count, forward, backward)
        index = int(numpy.argmin(value))
        best.append((float(value[index]), int(starts[index]), lag))
    if not best:
        return None
    smallest = min(item[0] for item in best)
    level = float(env.max()) if count else 0.0
    close = smallest + 0.02 * level + 1e-9
    _value, start, lag = max((item for item in best if item[0] <= close), key=lambda i: i[2])
    return round(start * seconds * 1000), round((start + lag) * seconds * 1000)
