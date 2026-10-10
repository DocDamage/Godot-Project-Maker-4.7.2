"""The binary ``.aseprite`` / ``.ase`` file: its frames and its tags (T16.21).

Only what names animations is read: the header (size, frame count), each frame's duration and
the tags chunk (``0x2018``). Layers, cels and pixels are not decoded here; the pictures an
artist shipped beside the source are what a pack is made of. The format is public
(https://github.com/aseprite/aseprite/blob/main/docs/ase-file-specs.md) and little-endian.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path

FILE_MAGIC = 0xA5E0
FRAME_MAGIC = 0xF1FA
TAGS_CHUNK = 0x2018
HEADER_BYTES = 128
FRAME_HEADER_BYTES = 16
MAX_BYTES = 256 * 1024 * 1024
MAX_FRAMES = 20_000
DIRECTIONS = {0: "forward", 1: "reverse", 2: "pingpong", 3: "pingpong_reverse"}


class AsepriteError(ValueError):
    """The file is not an Aseprite file this reader understands."""


@dataclass(frozen=True)
class Tag:
    name: str
    first: int  # frame index, from 0
    last: int  # inclusive
    direction: str  # forward, reverse, pingpong, pingpong_reverse
    repeat: int  # 0: for ever

    @property
    def looped(self) -> bool:
        return self.repeat == 0

    def frames(self) -> list[int]:
        """The frame indexes in playing order."""
        forward = list(range(self.first, self.last + 1))
        if self.direction == "reverse":
            return forward[::-1]
        if self.direction == "pingpong":
            return forward + forward[-2:0:-1]
        if self.direction == "pingpong_reverse":
            back = forward[::-1]
            return back + back[-2:0:-1]
        return forward


@dataclass(frozen=True)
class AsepriteFile:
    width: int
    height: int
    durations_ms: list[int]  # one per frame
    tags: list[Tag] = field(default_factory=list)

    @property
    def frame_count(self) -> int:
        return len(self.durations_ms)


def _need(data: bytes, offset: int, count: int) -> None:
    if offset < 0 or offset + count > len(data):
        raise AsepriteError(f"the file ends at byte {len(data)}, {offset + count} were expected")


def _tags(data: bytes, offset: int, end: int, frame_count: int) -> list[Tag]:
    _need(data, offset, 10)
    (count,) = struct.unpack_from("<H", data, offset)
    offset += 10  # the count and eight reserved bytes
    tags: list[Tag] = []
    for _ in range(count):
        _need(data, offset, 19)
        first, last, direction, repeat = struct.unpack_from("<HHBH", data, offset)
        (length,) = struct.unpack_from("<H", data, offset + 17)
        offset += 19
        if offset + length > end:
            raise AsepriteError("a tag's name runs past its chunk")
        name = data[offset : offset + length].decode("utf-8", errors="replace")
        offset += length
        if first > last or last >= frame_count:
            raise AsepriteError(f"the tag {name!r} names frames the file does not have")
        tags.append(Tag(name, first, last, DIRECTIONS.get(direction, "forward"), repeat))
    return tags


def parse(data: bytes) -> AsepriteFile:
    """Read the frames and tags of an Aseprite file's bytes; ``AsepriteError`` when it is cut
    short or is no such file."""
    _need(data, 0, HEADER_BYTES)
    _size, magic, frame_count, width, height = struct.unpack_from("<IHHHH", data, 0)
    if magic != FILE_MAGIC:
        raise AsepriteError("not an Aseprite file")
    if not 0 < frame_count <= MAX_FRAMES or width == 0 or height == 0:
        raise AsepriteError(f"{frame_count} frames of {width} x {height}")
    durations: list[int] = []
    tags: list[Tag] = []
    offset = HEADER_BYTES
    for _ in range(frame_count):
        _need(data, offset, FRAME_HEADER_BYTES)
        frame_bytes, frame_magic, old_chunks, duration = struct.unpack_from("<IHHH", data, offset)
        (new_chunks,) = struct.unpack_from("<I", data, offset + 12)
        if frame_magic != FRAME_MAGIC or frame_bytes < FRAME_HEADER_BYTES:
            raise AsepriteError(f"frame {len(durations) + 1} does not start as a frame")
        _need(data, offset, frame_bytes)
        frame_end = offset + frame_bytes
        durations.append(duration or 100)
        chunk = offset + FRAME_HEADER_BYTES
        for _chunk in range(new_chunks or (0 if old_chunks == 0xFFFF else old_chunks)):
            if chunk + 6 > frame_end:
                raise AsepriteError(f"frame {len(durations)} has a chunk past its end")
            chunk_bytes, kind = struct.unpack_from("<IH", data, chunk)
            if chunk_bytes < 6 or chunk + chunk_bytes > frame_end:
                raise AsepriteError(f"frame {len(durations)} has a chunk of {chunk_bytes} bytes")
            if kind == TAGS_CHUNK:
                tags.extend(_tags(data, chunk + 6, chunk + chunk_bytes, frame_count))
            chunk += chunk_bytes
        offset = frame_end
    return AsepriteFile(width, height, durations, tags)


def read(path: Path) -> AsepriteFile:
    """``parse`` for a file. ``AsepriteError`` also for one that cannot be read or is too big."""
    try:
        if path.stat().st_size > MAX_BYTES:
            raise AsepriteError("the file is larger than 256 MB")
        return parse(path.read_bytes())
    except OSError as exc:
        raise AsepriteError(str(exc)) from exc


def write(
    width: int,
    height: int,
    durations_ms: list[int],
    tags: list[Tag],
) -> bytes:
    """The bytes of an Aseprite file with these frames and tags and nothing else (no layer, no
    cel): what the synthetic packs and the tests need. Aseprite opens it as empty frames."""
    reverse = {v: k for k, v in DIRECTIONS.items()}
    frames: list[bytes] = []
    for index, duration in enumerate(durations_ms):
        chunks = b""
        count = 0
        if index == 0 and tags:
            body = struct.pack("<H8x", len(tags))
            for tag in tags:
                name = tag.name.encode("utf-8")
                body += struct.pack("<HHBH6x3xB", tag.first, tag.last, reverse[tag.direction],
                                    tag.repeat, 0)  # fmt: skip
                body += struct.pack("<H", len(name)) + name
            chunks = struct.pack("<IH", 6 + len(body), TAGS_CHUNK) + body
            count = 1
        frames.append(
            struct.pack(
                "<IHHH2xI", FRAME_HEADER_BYTES + len(chunks), FRAME_MAGIC, count, duration, count
            )
            + chunks  # fmt: skip
        )
    body = b"".join(frames)
    header = struct.pack(
        "<IHHHHHIH", HEADER_BYTES + len(body), FILE_MAGIC, len(durations_ms), width, height, 32, 1,
        100,
    )  # fmt: skip
    return header.ljust(HEADER_BYTES, b"\0") + body
