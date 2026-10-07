"""Audio durations without third-party code (T11.03).

Reads just enough of WAV, Ogg (Vorbis, Opus), MP3 and FLAC to tell how long a file is. The
classifier only needs "is this longer than about 20 s", so MP3 without a Xing header is estimated
from its first frame's bitrate. Anything unreadable gives ``None``; nothing here raises.
"""

from __future__ import annotations

import contextlib
import struct
import wave
from pathlib import Path

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
