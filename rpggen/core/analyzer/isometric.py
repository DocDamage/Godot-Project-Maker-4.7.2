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
BOUND_SLACK = 1e-6  # a height on the very end of what a staircase allows is not taken


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


def _upper_edges(tile: FlatTile) -> tuple[float, list[np.ndarray]]:
    """``(apex, edges)`` of a flat tile: the column its highest point lies in, and the columns
    of its two upper edges. The outer tenth of an edge is left out (a rounded corner, the
    single pixel of the tip)."""
    w = tile.width
    apex = float(np.nonzero(tile.top == tile.top.min())[0].mean())
    edges: list[np.ndarray] = []
    for first, last in ((0, int(apex)), (int(np.ceil(apex)), w - 1)):
        cut = max(1, (last - first) // 10)
        columns = np.arange(first + cut, last - cut + 1)
        if columns.size >= 2:
            edges.append(columns)
    return apex, edges


def slope_bounds(tile: FlatTile) -> tuple[float, float]:
    """``(above, below)``: the slopes the upper edges of a flat tile can have as pixels, both
    ends left out. An edge is a staircase, and a staircase is the picture of a straight line
    only when no two of its steps lie a whole row further apart or nearer than the line puts
    them; the apex counts as a step, since the two edges meet in the tile's top row. The first
    is not less than the second when the edges are no such staircase (a rendered tile's soft
    edge, a blunt tip): then the pixels say nothing sure."""
    apex, edges = _upper_edges(tile)
    above, below = 0.0, float("inf")
    for columns in edges:
        run = np.concatenate(([0.0], np.abs(columns - apex)))
        fall = np.concatenate(([0.0], (tile.top[columns] - tile.top.min()).astype(np.float64)))
        runs = run[None, :] - run[:, None]
        falls = fall[None, :] - fall[:, None]
        apart = runs > 0
        above = max(above, float(((falls[apart] - 1.0) / runs[apart]).max()))
        below = min(below, float(((falls[apart] + 1.0) / runs[apart]).min()))
    return above, below


def edge_slope(tile: FlatTile) -> float:
    """How steeply the two upper edges of a flat tile fall, in rows a column: half the
    diamond's height over half its width. A line is fitted to each edge. On a short edge the
    fit can be a slope the staircase cannot have (``slope_bounds``; its few steps weigh on the
    fit: a diamond 32 x 18 is fitted as 18.85 high, where its pixels allow 17.8 to 18.3), and
    then the slope of the nearest whole height they do allow is taken instead."""
    w = tile.width
    _apex, edges = _upper_edges(tile)
    slopes = [abs(float(np.polyfit(columns, tile.top[columns], 1)[0])) for columns in edges]
    if not slopes:
        return tile.face_height / w
    fitted = sum(slopes) / len(slopes)
    above, below = slope_bounds(tile)
    if not above < below or above < fitted < below:
        return fitted
    possible = [
        h
        for h in range(int(np.floor(w * above)), int(np.ceil(w * below)) + 1)
        if w * above + BOUND_SLACK < h < w * below - BOUND_SLACK
    ]
    return min(possible, key=lambda h: (abs(h - w * fitted), h)) / w if possible else fitted


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


@dataclass(frozen=True)
class Base:
    """The foot of a picture that stands on a whole block of ground, whatever is on it."""

    width: int  # of the painted part
    slope: float  # rows a column of the two lower edges
    side: int  # rows of the outermost columns: the block's side


def block_base(mask: np.ndarray) -> Base | None:
    """The foot of a picture whose lower outline is the lower half of a diamond, as wide as
    the picture: two straight edges from the side corners down to a lowest point in the
    middle, the outermost columns equally high. What stands on the block (a house, a tree) is
    not looked at; a flat tile has such a foot too. None for a picture that has none (a tree
    on its trunk, a wall on one edge of its diamond)."""
    found = outline(mask)
    if found is None:
        return None
    box, top, bottom = found
    _x, _y, w, h = box
    if w < MIN_WIDTH:
        return None
    tolerance = _tolerance(w)
    low = float(np.nonzero(bottom == bottom.max())[0].mean())
    if abs(low - (w - 1) / 2) > w * CENTRE_TOLERANCE:
        return None
    if abs(int(bottom[0]) - int(bottom[-1])) > tolerance:
        return None
    drop = (h - 1) - (int(bottom[0]) + int(bottom[-1])) / 2
    if not w * MIN_DROP <= drop <= w * MAX_DROP:
        return None
    middle = int(round(low))
    straight = max(STRAIGHT_MIN, w / STRAIGHT_WIDTH)
    if not (
        _straight(bottom[: middle + 1], float(bottom[0]), h - 1.0, straight)
        and _straight(bottom[middle:], h - 1.0, float(bottom[-1]), straight)
    ):
        return None
    sides = (int(bottom[0] - top[0]) + 1, int(bottom[-1] - top[-1]) + 1)
    if abs(sides[0] - sides[1]) > tolerance + 1:
        return None
    slopes = []
    for first, last in ((0, int(low)), (int(np.ceil(low)), w - 1)):
        cut = max(1, (last - first) // 10)
        columns = np.arange(first + cut, last - cut + 1)
        if columns.size >= 2:
            slopes.append(abs(float(np.polyfit(columns, bottom[columns], 1)[0])))
    if not slopes:
        return None
    return Base(w, sum(slopes) / len(slopes), int(round(sum(sides) / 2)))


EDGE_SIDES = ("n", "e", "s", "w")  # by the grid: upper right, lower right, lower left, upper left
EDGE_NEAR = 0.25  # a foot this far from the middle of its diamond, of a whole diamond ...
EDGE_FAR = 0.6  # ... and no further than this, lies along that side
EDGE_SHARE = 0.5  # this share of a piece's columns must stand along one side ...
EDGE_LENGTH = 0.7  # ... over this much of the side's length


def edge_side(
    columns: np.ndarray, foot: np.ndarray, middle: tuple[float, float], diamond: tuple[int, int]
) -> str | None:
    """The side of its diamond a thin piece stands along (a wall segment, a fence), or None.
    ``foot`` is the lowest painted row of each of ``columns``, ``middle`` the middle of the
    diamond the piece stands on, as deep as the foot of the pack's ground block, and
    ``diamond`` its size. The foot is counted in the grid's own coordinates (east and south,
    the diamond a square from -0.5 to 0.5): a piece along a side keeps to a narrow band at
    that side for most of its columns and runs most of the side's length. A flat tile's foot
    is two sides at once, a tree's is in the middle, a wall with a doorway has its foot
    wherever the doorway is not."""
    if columns.size < 2 or min(diamond) <= 0:
        return None
    u = (columns - middle[0]) / (diamond[0] / 2.0)
    v = (foot - middle[1]) / (diamond[1] / 2.0)
    east, south = (u + v) / 2.0, (v - u) / 2.0
    found: list[str] = []
    for side, across, along in (
        ("n", -south, east),
        ("e", east, south),
        ("s", south, east),
        ("w", -east, south),
    ):
        on = (across >= EDGE_NEAR) & (across <= EDGE_FAR) & (np.abs(along) <= EDGE_FAR)
        length = float(np.ptp(along[on])) if on.any() else 0.0
        share = float(on.mean())
        if share >= EDGE_SHARE and length >= EDGE_LENGTH:
            found.append(side)
    # the end of a wall is at two sides, and the arch of a doorway may lie over a third: a
    # foot that runs the length of two sides (a flat tile, a corner of walls) is none
    return found[0] if len(found) == 1 else None


FACE_SHARE = 0.8  # the part of a diamond, from its middle, that is looked at for its colour
FACE_STEP = 24  # a pixel this near the face's usual colour, in every channel, is of that colour
FACE_PLAIN = 0.995  # a face is plain when this share of it is of one colour: nothing is drawn on it
GRASS_HUES = (60.0, 170.0)  # from yellow green to blue green, in degrees ...
GRASS_SATURATION = 0.15  # ... and not grey
WATER_HUES = (170.0, 260.0)
FACE_PLAIN_TAG = "plain"
FACE_GRASS = "grass"


def face_colour(
    rgba: np.ndarray, middle: tuple[float, float], diamond: tuple[int, int]
) -> str | None:
    """What the top of a flat tile is by its colour: ``"grass"`` for a face of one green,
    ``"plain"`` for a face of one other colour that is not the blue of water, None for a face
    with something drawn on it (a road, a river, a pattern of slabs) or none at all. The face
    is the diamond round ``middle`` without its rim."""
    ys, xs = np.mgrid[0 : rgba.shape[0], 0 : rgba.shape[1]]
    inside = (
        np.abs(xs - middle[0]) / (diamond[0] / 2.0) + np.abs(ys - middle[1]) / (diamond[1] / 2.0)
        <= FACE_SHARE
    ) & (rgba[..., 3] >= PAINTED_ALPHA)
    face = rgba[inside][:, :3].astype(np.int16)
    if face.shape[0] < MIN_WIDTH:
        return None
    usual = np.median(face, axis=0)
    if float((np.abs(face - usual).max(axis=1) <= FACE_STEP).mean()) < FACE_PLAIN:
        return None
    r, g, b = (float(v) / 255.0 for v in usual)
    high, low = max(r, g, b), min(r, g, b)
    if high - low < 1e-6:
        return FACE_PLAIN_TAG
    if high == r:
        hue = 60.0 * (((g - b) / (high - low)) % 6)
    elif high == g:
        hue = 60.0 * ((b - r) / (high - low) + 2)
    else:
        hue = 60.0 * ((r - g) / (high - low) + 4)
    saturation = (high - low) / high
    if saturation >= GRASS_SATURATION and GRASS_HUES[0] <= hue <= GRASS_HUES[1]:
        return FACE_GRASS
    if saturation >= GRASS_SATURATION and WATER_HUES[0] < hue <= WATER_HUES[1]:
        return None
    return FACE_PLAIN_TAG


SIDE_REACH = 0.42  # how far from the middle of a diamond, of a whole one, a side is sampled
SIDE_STEPS = ((0, -1), (1, 0), (0, 1), (-1, 0))  # n, e, s, w by the grid: east and south


def open_sides(
    rgba: np.ndarray, middle: tuple[float, float], diamond: tuple[int, int]
) -> list[str] | None:
    """The sides of a flat tile on which its own surface runs out to the edge: the sides
    whose middle, a little inside, has the colour of the tile's middle (a road that goes on,
    where the other sides are verge). None when a point to look at is not painted."""
    points = [(0.0, 0.0), *((dx * SIDE_REACH, dy * SIDE_REACH) for dx, dy in SIDE_STEPS)]
    colours = []
    for east, south in points:
        x = int(round(middle[0] + (east - south) * diamond[0] / 2.0))
        y = int(round(middle[1] + (east + south) * diamond[1] / 2.0))
        if not (0 <= y < rgba.shape[0] and 0 <= x < rgba.shape[1]):
            return None
        if rgba[y, x, 3] < PAINTED_ALPHA:
            return None
        colours.append(rgba[y, x, :3].astype(np.int16))
    return [
        side
        for side, colour in zip(EDGE_SIDES, colours[1:], strict=True)
        if int(np.abs(colour - colours[0]).max()) <= FACE_STEP
    ]


def turned_sides(sides: list[str], quarters: int) -> list[str]:
    """``sides`` a number of quarter turns clockwise round the diamond, in the order n, e, s, w."""
    moved = {EDGE_SIDES[(EDGE_SIDES.index(side) + quarters) % 4] for side in sides}
    return [side for side in EDGE_SIDES if side in moved]


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
