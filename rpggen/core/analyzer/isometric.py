"""Measuring isometric tiles (T17.12).

A pack of isometric tiles is one picture a tile, and the diamond a tile stands on (its
*footprint*) is in no picture's size: the pictures of *Modular Roads* are 180 x 184 and its
diamond is 180 x 104. A **flat tile** says it: a ground tile whose outline is a diamond with,
under it, the side of the block it was drawn as. Its upper edges are the diamond's, its lower
edges the same diamond a block's side further down.

Two flat tiles laid side by side, the second half a tile to the right, meet without a gap when
the second lies half the diamond's height lower: then its upper edge goes on in one line where
the first one's ends. So the slope of a flat tile's upper edges gives the height, and laying
checks it: the side is taken off (the lower outline moved up by the height of the outermost
column, which is all side), two copies of the face that is left are laid at that height, and
the see-through and the doubled pixels along their seam are counted.

Laying alone does not find the height. Two whole blocks show no gap until the second has sunk
by its whole side (measured on *Modular Roads*: no open pixel from 104 up to 148), and where a
side begins cannot be told to the pixel, so the best height of two faces is two pixels off
(106 for a pack whose own Tiled settings say 104, where the slope gives 103.9).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

MIN_WIDTH = 16  # a smaller picture has no outline to measure
HOLES_MAX = 0.02  # the share of a flat tile's columns that may have a see-through pixel
CENTRE_TOLERANCE = 0.08  # how far from the middle the highest and the lowest point may lie
MIN_DROP = 0.125  # the diamond's half height as a share of its width, at least and at most
MAX_DROP = 0.6
MAX_MISFIT = 2.0  # open and doubled pixels a seam column that two laid faces may leave ...
MIN_MISFIT = 1.0  # ... for a wide tile; a narrow one may leave this many
MISFIT_WIDTH = 64  # ... and a pixel more for every so many pixels of width
STRAIGHT_MIN = 0.75  # how far an edge may lie from a straight line, on average, in pixels
STRAIGHT_WIDTH = 128  # ... and a pixel more for every so many pixels of width
PAINTED_ALPHA = 128  # a pixel fainter than this is the soft edge of a rendered tile
AGREE_PX = 2  # flat tiles of one pack give the same height within this
AGREE_SHARE = 0.5
WIDTH_SHARE = 0.25  # a width this share of the commonest one's flat tiles have is a ground's
TILE_BASE_MIN = 0.9  # a tile's base is as wide as the diamond, within these
TILE_BASE_MAX = 1.1


def _tolerance(width: int) -> int:
    """How many rows two corners that should lie level may differ by."""
    return 1 + width // 64


@dataclass(frozen=True, eq=False)
class FlatTile:
    """A picture that is one flat tile: a diamond with the side of its block under it."""

    box: tuple[int, int, int, int]  # x, y, w, h of the painted part
    side: int  # rows of the outermost columns: the block's side (1 for a tile with none)
    top: np.ndarray  # the first painted row of every column of the box, from its top
    bottom: np.ndarray  # the last painted row of the face (the side taken off)

    @property
    def width(self) -> int:
        return self.box[2]

    @property
    def face_height(self) -> int:
        """The rows of the face from its highest to its lowest point."""
        return int(self.bottom.max()) + 1


def painted(a: np.ndarray) -> np.ndarray:
    """The pixels of an RGBA picture that are part of the tile: at least half opaque. The
    soft edge a rendered tile has would make it two pixels wider than it lies on its grid."""
    return np.asarray(a[..., 3] >= PAINTED_ALPHA)


def outline(mask: np.ndarray) -> tuple[tuple[int, int, int, int], np.ndarray, np.ndarray] | None:
    """``(box, top, bottom)`` of the painted part of ``mask``: its bounding box and, for every
    column of the box, the first and the last painted row counted from the box's top. None for
    an empty picture."""
    ys, xs = np.nonzero(mask)
    if xs.size == 0:
        return None
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
    part = mask[y0 : y1 + 1, x0 : x1 + 1]
    top = part.argmax(axis=0)
    bottom = part.shape[0] - 1 - part[::-1].argmax(axis=0)
    return (x0, y0, x1 - x0 + 1, y1 - y0 + 1), top, bottom


def _straight(edge: np.ndarray, start: float, end: float, tolerance: float) -> bool:
    """True when ``edge`` runs from ``start`` to ``end`` as a straight line would."""
    if edge.size < 2:
        return True
    line = np.linspace(start, end, edge.size)
    return float(np.abs(edge - line).mean()) <= tolerance


def flat_tile(mask: np.ndarray) -> FlatTile | None:
    """The flat tile ``mask`` (painted pixels) is, or None: its painted part has no hole, its
    highest and its lowest point lie in the middle, its outermost columns begin at one height,
    and its upper and its lower edges are the straight edges of one diamond."""
    found = outline(mask)
    if found is None:
        return None
    box, top, bottom = found
    _x, _y, w, h = box
    if w < MIN_WIDTH:
        return None
    part = mask[box[1] : box[1] + h, box[0] : box[0] + w]
    if float((part.sum(axis=0) != bottom - top + 1).mean()) > HOLES_MAX:
        return None
    tolerance = _tolerance(w)
    middle = (w - 1) / 2
    apex = float(np.nonzero(top == top.min())[0].mean())
    low = float(np.nonzero(bottom == bottom.max())[0].mean())
    if abs(apex - middle) > w * CENTRE_TOLERANCE or abs(low - middle) > w * CENTRE_TOLERANCE:
        return None
    if abs(int(top[0]) - int(top[-1])) > tolerance:
        return None
    if abs(int(bottom[0]) - int(bottom[-1])) > tolerance:
        return None
    drop = (int(top[0]) + int(top[-1])) / 2  # rows from the highest point to the side corners
    rise = (h - 1) - (int(bottom[0]) + int(bottom[-1])) / 2  # ... and on to the lowest point
    if not w * MIN_DROP <= drop <= w * MAX_DROP or abs(drop - rise) > tolerance + 1:
        return None
    half = int(round(apex))
    low_half = int(round(low))
    straight = max(STRAIGHT_MIN, w / STRAIGHT_WIDTH)
    if not (
        _straight(top[: half + 1], float(top[0]), 0.0, straight)
        and _straight(top[half:], 0.0, float(top[-1]), straight)
        and _straight(bottom[: low_half + 1], float(bottom[0]), h - 1.0, straight)
        and _straight(bottom[low_half:], h - 1.0, float(bottom[-1]), straight)
    ):
        return None
    side = int(round(((bottom[0] - top[0] + 1) + (bottom[-1] - top[-1] + 1)) / 2))
    face_bottom = np.maximum(bottom - (side - 1), top)
    return FlatTile(box, side, top, face_bottom)


def lay(tile: FlatTile, height: int) -> tuple[int, int]:
    """``(open, doubled)`` pixels along the seam of two copies of a flat tile's face, the
    second half the tile's width to the right and half of ``height`` down: the see-through
    pixels between the first one's lower edge and the second one's upper edge, and the pixels
    both paint."""
    dx, dy = tile.width // 2, height // 2
    lower = tile.bottom[dx:].astype(np.int64)
    upper = tile.top[: tile.width - dx].astype(np.int64) + dy
    gap = upper - lower - 1
    return int(np.clip(gap, 0, None).sum()), int(np.clip(-gap, 0, None).sum())


def edge_slope(tile: FlatTile) -> float:
    """How steeply the two upper edges of a flat tile fall, in rows a column: half the
    diamond's height over half its width. The outer tenth of an edge is left out (a rounded
    corner, the single pixel of the tip)."""
    w = tile.width
    apex = float(np.nonzero(tile.top == tile.top.min())[0].mean())
    slopes: list[float] = []
    for first, last in ((0, int(apex)), (int(np.ceil(apex)), w - 1)):
        cut = max(1, (last - first) // 10)
        columns = np.arange(first + cut, last - cut + 1)
        if columns.size >= 2:
            slopes.append(abs(float(np.polyfit(columns, tile.top[columns], 1)[0])))
    return sum(slopes) / len(slopes) if slopes else tile.face_height / w


def diamond_height(tile: FlatTile) -> tuple[int, float] | None:
    """``(height, misfit)`` of the diamond a flat tile stands on: the height its edges' slope
    gives a diamond as wide as the tile, and the open and doubled pixels a seam column that
    two of its faces laid side by side at that height leave. None when they do not meet there
    (the picture is no tile of a grid)."""
    height = int(round(tile.width * edge_slope(tile)))
    if height < 2:
        return None
    seam = max(1, tile.width - tile.width // 2)
    misfit = sum(lay(tile, height)) / seam
    allowed = min(MAX_MISFIT, max(MIN_MISFIT, tile.width / MISFIT_WIDTH))
    return (height, round(misfit, 4)) if misfit <= allowed else None


@dataclass(frozen=True)
class Diamond:
    """The diamond of a pack, measured from its flat tiles."""

    width: int
    height: int
    slope: float  # rows a column of the diamond's edges: half its height over half its width
    side: int  # the rows of block under the diamond that the pack's usual flat tile has
    tiles: int  # how many flat tiles agreed


def measure(tiles: list[FlatTile], width: int | None = None) -> Diamond | None:
    """The diamond the flat tiles of a pack stand on, or None when they do not agree on one.
    ``width`` is the diamond's width when the pack says it (tiles of another width are left
    out); else it is the widest that a fair share of the flat tiles have: a pack's small flat
    things (a slab, a rug, the top of a post) are diamonds too, and narrower than its ground."""
    if not tiles:
        return None
    if width is None:
        counts: dict[int, int] = {}
        for tile in tiles:
            counts[tile.width] = counts.get(tile.width, 0) + 1
        fair = max(2, int(max(counts.values()) * WIDTH_SHARE))
        near = {w: counts[w] + counts.get(w - 1, 0) + counts.get(w + 1, 0) for w in counts}
        wide = [w for w in counts if near[w] >= fair]
        if not wide:
            return None
        widest = max(wide)
        width = max((w for w in wide if widest - w <= 1), key=lambda w: (counts[w], -w))
    same = [t for t in tiles if abs(t.width - width) <= 1]
    measured = [(t, diamond_height(t)) for t in same]
    heights = sorted(found[0] for _t, found in measured if found is not None)
    if not heights:
        return None
    height = heights[(len(heights) - 1) // 2]
    agreeing = [
        t for t, found in measured if found is not None and abs(found[0] - height) <= AGREE_PX
    ]
    if len(agreeing) < max(1, int(len(heights) * AGREE_SHARE)):
        return None
    slopes = sorted(edge_slope(t) for t in agreeing)
    slope = slopes[(len(slopes) - 1) // 2]
    height = int(round(width * slope))
    sides = sorted(t.box[3] - height for t in agreeing)
    side = max(0, sides[(len(sides) - 1) // 2])
    return Diamond(width, height, round(slope, 6), side, len(agreeing))


def base_width(mask: np.ndarray, rows: int) -> int:
    """How wide the painted part of ``mask`` is in its lowest ``rows`` rows: what a picture
    stands on. 0 for an empty picture."""
    found = outline(mask)
    if found is None:
        return 0
    x, y, w, h = found[0]
    band = mask[max(y, y + h - max(1, rows)) : y + h, x : x + w]
    columns = np.nonzero(band.any(axis=0))[0]
    return int(columns[-1] - columns[0] + 1) if columns.size else 0


def stands_on(base: int, width: int) -> tuple[int, int]:
    """How many diamonds a thing with a base ``base`` pixels wide stands on, as ``(columns,
    rows)`` of the grid: a block of ``k`` by ``m`` diamonds is ``(k + m) / 2`` diamonds wide
    on the screen, and the guess is the squarest block that wide."""
    if width <= 0 or base <= width * TILE_BASE_MAX:
        return (1, 1)
    halves = max(2, round(2 * base / width))
    return ((halves + 1) // 2, halves // 2)
