"""The binary ``.aseprite`` / ``.ase`` file: its frames, its tags and its pictures (T16.21).

``parse`` reads only what names animations: the header (size, frame count), each frame's
duration and the tags chunk (``0x2018``); the pictures an artist shipped beside the source are
what a pack is made of. ``render`` draws the frames of a source that has no export beside it:
the layers, the cels (raw, zlib-compressed and linked) in RGBA, grayscale and indexed colour,
put over each other as Aseprite does with the *normal* blend mode. Not drawn as Aseprite draws
them, and said in ``Picture.inexact``: another blend mode (drawn as normal), a tile map layer
(left out), the opacity of a group (not applied). The format is public
(https://github.com/aseprite/aseprite/blob/main/docs/ase-file-specs.md) and little-endian.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

FILE_MAGIC = 0xA5E0
FRAME_MAGIC = 0xF1FA
OLD_PALETTE_CHUNKS = (0x0004, 0x0011)  # 0 to 255 and 0 to 63 a channel
LAYER_CHUNK = 0x2004
CEL_CHUNK = 0x2005
TAGS_CHUNK = 0x2018
PALETTE_CHUNK = 0x2019
HEADER_BYTES = 128
FRAME_HEADER_BYTES = 16
MAX_BYTES = 256 * 1024 * 1024
MAX_FRAMES = 20_000
MAX_PIXELS = 64 * 1024 * 1024  # of all frames together: a strip nobody could use is not drawn
PIXEL_BYTES = {32: 4, 16: 2, 8: 1}  # the colour depth: RGBA, grayscale with alpha, indexed
LAYER_VISIBLE, LAYER_BACKGROUND, LAYER_REFERENCE = 1, 8, 64
LAYER_OPACITY_VALID = 1  # a flag of the header
LAYER_IMAGE, LAYER_GROUP, LAYER_TILEMAP = 0, 1, 2
CEL_RAW, CEL_LINKED, CEL_COMPRESSED = 0, 1, 2
CEL_HEADER_BYTES = 16
BACKDROP_NAMES = frozenset({"bg", "background", "backdrop", "back", "fond", "fondo"})
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


@dataclass(frozen=True)
class _Header:
    frame_count: int
    width: int
    height: int
    depth: int
    flags: int
    transparent: int  # the palette index that is see-through (indexed colour only)


def _walk(data: bytes) -> tuple[_Header, list[int], list[list[tuple[int, int, int]]]]:
    """The header, each frame's duration and each frame's chunks as ``(kind, start, end)`` of
    their contents; ``AsepriteError`` when the file is cut short or is no such file."""
    _need(data, 0, HEADER_BYTES)
    _size, magic, frame_count, width, height, depth, flags = struct.unpack_from("<IHHHHHI", data, 0)
    if magic != FILE_MAGIC:
        raise AsepriteError("not an Aseprite file")
    if not 0 < frame_count <= MAX_FRAMES or width == 0 or height == 0:
        raise AsepriteError(f"{frame_count} frames of {width} x {height}")
    durations: list[int] = []
    chunks: list[list[tuple[int, int, int]]] = []
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
        chunks.append([])
        chunk = offset + FRAME_HEADER_BYTES
        for _chunk in range(new_chunks or (0 if old_chunks == 0xFFFF else old_chunks)):
            if chunk + 6 > frame_end:
                raise AsepriteError(f"frame {len(durations)} has a chunk past its end")
            chunk_bytes, kind = struct.unpack_from("<IH", data, chunk)
            if chunk_bytes < 6 or chunk + chunk_bytes > frame_end:
                raise AsepriteError(f"frame {len(durations)} has a chunk of {chunk_bytes} bytes")
            chunks[-1].append((kind, chunk + 6, chunk + chunk_bytes))
            chunk += chunk_bytes
        offset = frame_end
    return _Header(frame_count, width, height, depth, flags, data[28]), durations, chunks


def parse(data: bytes) -> AsepriteFile:
    """Read the frames and tags of an Aseprite file's bytes; ``AsepriteError`` when it is cut
    short or is no such file."""
    header, durations, chunks = _walk(data)
    tags: list[Tag] = []
    for frame in chunks:
        for kind, start, end in frame:
            if kind == TAGS_CHUNK:
                tags.extend(_tags(data, start, end, header.frame_count))
    return AsepriteFile(header.width, header.height, durations, tags)


def read(path: Path) -> AsepriteFile:
    """``parse`` for a file. ``AsepriteError`` also for one that cannot be read or is too big."""
    try:
        if path.stat().st_size > MAX_BYTES:
            raise AsepriteError("the file is larger than 256 MB")
        return parse(path.read_bytes())
    except OSError as exc:
        raise AsepriteError(str(exc)) from exc


# --------------------------------------------------------------------------- the pictures


@dataclass(frozen=True)
class Layer:
    name: str
    visible: bool = True
    opacity: int = 255
    kind: int = LAYER_IMAGE  # LAYER_IMAGE, LAYER_GROUP or LAYER_TILEMAP
    level: int = 0  # how deep in groups: a layer belongs to the group before it one level up
    blend: int = 0  # 0: normal
    background: bool = False
    reference: bool = False  # a picture to draw from: never part of the sprite


@dataclass(frozen=True)
class Cel:
    """What one layer shows in one frame: a picture at a place, or the cel of another frame."""

    frame: int
    layer: int
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    pixels: bytes = b""  # row by row, in the file's colour depth
    opacity: int = 255
    link: int | None = None  # the frame whose cel of this layer is shown again
    compressed: bool = True  # how ``write`` stores it; a cel that was read is always unpacked
    z: int = 0  # moves the cel before or behind other layers in its frame


@dataclass(frozen=True)
class Picture:
    """The frames of a source, drawn: one RGBA ``PIL.Image`` of the sprite's size per frame."""

    file: AsepriteFile
    frames: list[Any]
    inexact: list[str] = field(default_factory=list)  # what is not drawn as Aseprite draws it
    backdrop: str | None = None  # the layer left out as the artist's backdrop, by its name


def _layer(data: bytes, start: int, end: int, opacity_valid: bool) -> Layer:
    if end - start < 18:
        raise AsepriteError("a layer chunk is cut short")
    flags, kind, level, _w, _h, blend, opacity = struct.unpack_from("<HHHHHHB", data, start)
    (length,) = struct.unpack_from("<H", data, start + 16)
    name = data[start + 18 : min(end, start + 18 + length)].decode("utf-8", errors="replace")
    background = bool(flags & LAYER_BACKGROUND)
    return Layer(
        name,
        bool(flags & LAYER_VISIBLE),
        opacity if opacity_valid and not background else 255,
        kind,
        level,
        blend,
        background,
        bool(flags & LAYER_REFERENCE),
    )


def _cel(data: bytes, start: int, end: int, frame: int, pixel_bytes: int) -> Cel | None:
    """The cel of a chunk; None for a kind that is not drawn (a tile map)."""
    if end - start < CEL_HEADER_BYTES + 2:
        raise AsepriteError(f"a cel of frame {frame + 1} is cut short")
    layer, x, y, opacity, kind, z = struct.unpack_from("<HhhBHh", data, start)
    body = start + CEL_HEADER_BYTES
    if kind == CEL_LINKED:
        (link,) = struct.unpack_from("<H", data, body)
        return Cel(frame, layer, x, y, opacity=opacity, link=link, z=z)
    if kind not in (CEL_RAW, CEL_COMPRESSED):
        return None
    if end - body < 4:
        raise AsepriteError(f"a cel of frame {frame + 1} is cut short")
    width, height = struct.unpack_from("<HH", data, body)
    size = width * height * pixel_bytes
    if width * height > MAX_PIXELS:
        raise AsepriteError(f"a cel of {width} x {height}")
    raw = data[body + 4 : end]
    if kind == CEL_COMPRESSED:
        try:
            raw = zlib.decompressobj().decompress(raw, size + 1)  # never more than a cel holds
        except zlib.error as exc:
            raise AsepriteError(f"a cel of frame {frame + 1} cannot be unpacked: {exc}") from exc
    if len(raw) != size:
        raise AsepriteError(
            f"a cel of frame {frame + 1} has {len(raw)} bytes for {width} x {height} pixels"
        )
    return Cel(frame, layer, x, y, width, height, raw, opacity, z=z)


def _palette(data: bytes, chunks: list[list[tuple[int, int, int]]]) -> Any:
    """The colours of an indexed file as a 256 x 4 array (a colour no chunk names is
    see-through): the palette chunks, and the two older kinds when a file has none of those."""
    import numpy

    colours = numpy.zeros((256, 4), dtype=numpy.uint8)
    found = False
    for frame in chunks:
        for kind, start, end in frame:
            if kind != PALETTE_CHUNK or end - start < 20:
                continue
            _count, first, last = struct.unpack_from("<III", data, start)
            offset = start + 20
            for index in range(first, last + 1):
                if offset + 6 > end:
                    raise AsepriteError("a palette is cut short")
                flags, r, g, b, a = struct.unpack_from("<HBBBB", data, offset)
                offset += 6
                if flags & 1:  # the colour has a name
                    if offset + 2 > end:
                        raise AsepriteError("a palette is cut short")
                    offset += 2 + struct.unpack_from("<H", data, offset)[0]
                if index < 256:
                    colours[index] = (r, g, b, a)
            found = True
    if found:
        return colours
    for frame in chunks:
        for kind, start, end in frame:
            if kind not in OLD_PALETTE_CHUNKS or end - start < 2:
                continue
            (packets,) = struct.unpack_from("<H", data, start)
            offset, index = start + 2, 0
            for _ in range(packets):
                if offset + 2 > end:
                    raise AsepriteError("a palette is cut short")
                index += data[offset]
                count = data[offset + 1] or 256
                offset += 2
                if offset + 3 * count > end:
                    raise AsepriteError("a palette is cut short")
                for _colour in range(count):
                    r, g, b = data[offset : offset + 3]
                    if kind == 0x0011:  # six bits a channel
                        r, g, b = ((v << 2) | (v >> 4) for v in (r, g, b))
                    if index < 256:
                        colours[index] = (r, g, b, 255)
                    index += 1
                    offset += 3
            found = True
    if not found:
        raise AsepriteError("indexed colours and no palette")
    return colours


def _rgba(cel: Cel, depth: int, palette: Any, transparent: int, background: bool) -> Any:
    """The pixels of a cel as a ``height x width x 4`` array of whole numbers."""
    import numpy

    raw = numpy.frombuffer(cel.pixels, dtype=numpy.uint8)
    if depth == 32:
        out = raw.reshape(cel.height, cel.width, 4)
    elif depth == 16:
        gray = raw.reshape(cel.height, cel.width, 2)
        out = gray[..., [0, 0, 0, 1]]
    else:
        index = raw.reshape(cel.height, cel.width)
        out = palette[index]
        if not background:  # on the background layer the see-through index is a colour
            out = numpy.where((index == transparent)[..., None], 0, out)
    return out.astype(numpy.int32)


def _times(a: Any, b: Any) -> Any:
    """Two values of 0 to 255 multiplied as fractions, rounded as Aseprite rounds (MUL_UN8)."""
    t = a * b + 0x80
    return ((t >> 8) + t) >> 8


def _over(back: Any, front: Any, opacity: int) -> Any:
    """``front`` drawn over ``back`` (the normal blend mode), in whole numbers as Aseprite
    computes it, so that a picture comes out as its own export."""
    import numpy

    front_alpha = _times(front[..., 3], opacity)
    back_alpha = back[..., 3]
    alpha = front_alpha + back_alpha - _times(back_alpha, front_alpha)
    step = (front[..., :3] - back[..., :3]) * front_alpha[..., None]
    # C divides towards zero, Python towards minus infinity
    share = numpy.sign(step) * (numpy.abs(step) // numpy.maximum(alpha, 1)[..., None])
    mixed = numpy.concatenate([back[..., :3] + share, alpha[..., None]], axis=-1)
    alone = numpy.concatenate([front[..., :3], front_alpha[..., None]], axis=-1)
    out = numpy.where((front[..., 3] == 0)[..., None], back, mixed)
    return numpy.where((back_alpha == 0)[..., None], alone, out)


def _shown(layers: list[Layer]) -> list[bool]:
    """Whether each layer is drawn: a picture layer that is visible, in visible groups only."""
    shown: list[bool] = []
    groups: list[bool] = []  # the visibility of the groups a layer lies in, outermost first
    for layer in layers:
        del groups[layer.level :]
        visible = layer.visible and all(groups)
        shown.append(visible and layer.kind == LAYER_IMAGE and not layer.reference)
        if layer.kind == LAYER_GROUP:
            groups.append(layer.visible)
    return shown


def _backdrop(
    layers: list[Layer], shown: list[bool], cels: dict[tuple[int, int], Cel], header: _Header
) -> int | None:
    """The layer an artist draws an animation against: in a file of several frames, the lowest
    layer that is drawn, with other layers over it, when its name says background (``BG``,
    ``gif bg``) and every cel of it fills the sprite with opaque pixels. It is switched off
    for an export, and a sprite with it has no see-through pixel at all. Aseprite's own
    *Background* layer is not one: that is the picture's ground, and it is exported."""
    used = sorted({layer for (_frame, layer) in cels if layer < len(shown) and shown[layer]})
    if len(used) < 2 or header.frame_count < 2 or layers[used[0]].background:
        return None
    lowest = used[0]
    words = "".join(c if c.isalpha() else " " for c in layers[lowest].name.casefold()).split()
    if BACKDROP_NAMES.isdisjoint(words):
        return None
    pixel_bytes = PIXEL_BYTES[header.depth]
    for (_frame, layer), cel in sorted(cels.items()):
        if layer != lowest or cel.link is not None:
            continue
        covers = (
            cel.x <= 0
            and cel.y <= 0
            and cel.x + cel.width >= header.width
            and cel.y + cel.height >= header.height
        )
        if header.depth == 8:
            opaque = header.transparent not in cel.pixels
        else:
            opaque = cel.pixels[pixel_bytes - 1 :: pixel_bytes].count(255) == cel.width * cel.height
        if not covers or not opaque:
            return None
    return lowest


def render(data: bytes, *, keep_backdrop: bool = False) -> Picture:
    """Draw every frame of an Aseprite file's bytes. ``AsepriteError`` for a file that is cut
    short, has a cel that cannot be unpacked, a colour depth this reader does not know, or
    more pixels than a strip may have. The layer an animation is drawn against (``_backdrop``)
    is left out, and ``Picture.backdrop`` names it, unless ``keep_backdrop``."""
    import numpy
    from PIL import Image

    header, durations, chunks = _walk(data)
    pixel_bytes = PIXEL_BYTES.get(header.depth)
    if pixel_bytes is None:
        raise AsepriteError(f"a colour depth of {header.depth} bits")
    if header.frame_count * header.width * header.height > MAX_PIXELS:
        raise AsepriteError(
            f"{header.frame_count} frames of {header.width} x {header.height} are too many pixels"
        )
    tags: list[Tag] = []
    layers: list[Layer] = []
    cels: dict[tuple[int, int], Cel] = {}
    inexact: set[str] = set()
    opacity_valid = bool(header.flags & LAYER_OPACITY_VALID)
    for frame, frame_chunks in enumerate(chunks):
        for kind, start, end in frame_chunks:
            if kind == TAGS_CHUNK:
                tags.extend(_tags(data, start, end, header.frame_count))
            elif kind == LAYER_CHUNK:
                layers.append(_layer(data, start, end, opacity_valid))
            elif kind == CEL_CHUNK:
                cel = _cel(data, start, end, frame, pixel_bytes)
                if cel is not None:
                    cels[(frame, cel.layer)] = cel
    shown = _shown(layers)
    for layer, drawn in zip(layers, shown, strict=True):
        if drawn and layer.blend != 0:
            inexact.add("a blend mode other than normal is drawn as normal")
        if layer.kind == LAYER_TILEMAP and layer.visible:
            inexact.add("a tile map layer is left out")
        if layer.kind == LAYER_GROUP and layer.visible and layer.opacity != 255:
            inexact.add("the opacity of a group is not applied")
    palette = _palette(data, chunks) if header.depth == 8 else None
    behind = None if keep_backdrop else _backdrop(layers, shown, cels, header)
    if behind is not None:
        shown[behind] = False
    frames: list[Any] = []
    for frame in range(header.frame_count):
        canvas = numpy.zeros((header.height, header.width, 4), dtype=numpy.int32)
        order = sorted(
            (cel for (at, _layer_index), cel in cels.items() if at == frame),
            key=lambda c: (c.layer + c.z, c.z),
        )
        for cel in order:
            if cel.layer >= len(layers):
                raise AsepriteError(f"a cel of frame {frame + 1} is on a layer the file lacks")
            if not shown[cel.layer]:
                continue
            layer = layers[cel.layer]
            seen = {frame}
            while cel.link is not None:  # a linked cel shows the cel of another frame
                linked = cels.get((cel.link, cel.layer))
                if linked is None or cel.link in seen:
                    raise AsepriteError(f"a linked cel of frame {frame + 1} links to nothing")
                seen.add(cel.link)
                cel = linked
            # the part of the cel that lies on the sprite
            left, top = max(0, cel.x), max(0, cel.y)
            right = min(header.width, cel.x + cel.width)
            bottom = min(header.height, cel.y + cel.height)
            if right <= left or bottom <= top:
                continue
            pixels = _rgba(cel, header.depth, palette, header.transparent, layer.background)
            part = pixels[top - cel.y : bottom - cel.y, left - cel.x : right - cel.x]
            opacity = int(_times(cel.opacity, layer.opacity))
            canvas[top:bottom, left:right] = _over(canvas[top:bottom, left:right], part, opacity)
        canvas[canvas[..., 3] == 0] = 0  # nothing to see has no colour: the same bytes always
        frames.append(Image.fromarray(canvas.astype(numpy.uint8), "RGBA"))
    file = AsepriteFile(header.width, header.height, durations, tags)
    return Picture(
        file, frames, sorted(inexact), layers[behind].name if behind is not None else None
    )


def render_file(path: Path) -> Picture:
    """``render`` for a file. ``AsepriteError`` also for one that cannot be read or is too big."""
    try:
        if path.stat().st_size > MAX_BYTES:
            raise AsepriteError("the file is larger than 256 MB")
        return render(path.read_bytes())
    except OSError as exc:
        raise AsepriteError(str(exc)) from exc


def _text(text: str) -> bytes:
    raw = text.encode("utf-8")
    return struct.pack("<H", len(raw)) + raw


def _chunk(kind: int, body: bytes) -> bytes:
    return struct.pack("<IH", 6 + len(body), kind) + body


def write(
    width: int,
    height: int,
    durations_ms: list[int],
    tags: list[Tag],
    *,
    depth: int = 32,
    layers: list[Layer] | None = None,
    cels: list[Cel] | None = None,
    palette: list[tuple[int, int, int, int]] | None = None,
    transparent: int = 0,
) -> bytes:
    """The bytes of an Aseprite file with these frames and tags, for the synthetic packs and
    the tests. With nothing else it has no layer and no cel, and Aseprite opens it as empty
    frames; ``layers``, ``cels`` (their pixels in the colour ``depth``) and ``palette`` make it
    a file with pictures."""
    reverse = {v: k for k, v in DIRECTIONS.items()}
    frames: list[bytes] = []
    for index, duration in enumerate(durations_ms):
        chunks = b""
        count = 0
        if index == 0:
            for layer in layers or []:
                flags = (
                    (LAYER_VISIBLE if layer.visible else 0)
                    | (LAYER_BACKGROUND if layer.background else 0)
                    | (LAYER_REFERENCE if layer.reference else 0)
                )
                chunks += _chunk(
                    LAYER_CHUNK,
                    struct.pack("<HHHHHHB3x", flags, layer.kind, layer.level, 0, 0, layer.blend,
                                layer.opacity) + _text(layer.name),
                )  # fmt: skip
                count += 1
            if palette:
                body = struct.pack("<III8x", len(palette), 0, len(palette) - 1)
                body += b"".join(struct.pack("<HBBBB", 0, *colour) for colour in palette)
                chunks += _chunk(PALETTE_CHUNK, body)
                count += 1
        if index == 0 and tags:
            body = struct.pack("<H8x", len(tags))
            for tag in tags:
                body += struct.pack("<HHBH6x3xB", tag.first, tag.last, reverse[tag.direction],
                                    tag.repeat, 0)  # fmt: skip
                body += _text(tag.name)
            chunks += _chunk(TAGS_CHUNK, body)
            count += 1
        for cel in cels or []:
            if cel.frame != index:
                continue
            kind = CEL_LINKED if cel.link is not None else CEL_RAW
            if cel.link is None and cel.compressed:
                kind = CEL_COMPRESSED
            body = struct.pack("<HhhBHh5x", cel.layer, cel.x, cel.y, cel.opacity, kind, cel.z)
            if cel.link is not None:
                body += struct.pack("<H", cel.link)
            else:
                pixels = zlib.compress(cel.pixels, 6) if cel.compressed else cel.pixels
                body += struct.pack("<HH", cel.width, cel.height) + pixels
            chunks += _chunk(CEL_CHUNK, body)
            count += 1
        frames.append(
            struct.pack(
                "<IHHH2xI", FRAME_HEADER_BYTES + len(chunks), FRAME_MAGIC, count, duration, count
            )
            + chunks  # fmt: skip
        )
    body = b"".join(frames)
    header = struct.pack(
        "<IHHHHHIH", HEADER_BYTES + len(body), FILE_MAGIC, len(durations_ms), width, height, depth,
        1, 100,
    )  # fmt: skip
    if depth == 8:
        header = header.ljust(28, b"\0") + struct.pack("<B3xH", transparent, len(palette or []))
    return header.ljust(HEADER_BYTES, b"\0") + body
