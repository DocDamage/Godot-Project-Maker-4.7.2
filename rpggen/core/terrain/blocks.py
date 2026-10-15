"""Terrain blocks inside sheets (T17.31).

Real packs keep their terrains as blocks inside larger mixed sheets (Kenney *Tiny Farm*,
EmanuelleDev *Farm RPG*, LimeZu *Modern Farm*), not as whole sheets of one layout
(``blob.py``). A block is found by **edge matching**: the cells of a terrain over another
surface (or over nothing) meet seamlessly where the map they make would be one surface, and
not where the terrain ends. The seams are compared pixel for pixel, the edges of every cell of
the sheet read once (``_Sheet``).

The layouts, tried in this order on every sheet of tiles (cells already taken by a block are
not tried again):

* ``blob47_godot_12x4`` and ``blob47_12x4``: the 47-tile blob in Godot's template or in the
  masks' order (``blob.py``), as a window of 12 x 4 cells anywhere in the sheet (*Farm RPG*
  repeats Godot's template down its sheets of grass, water, paths and soil);
* ``corners16_4x4``, ``corners16_drawn_4x4`` and ``sides16_drawn_4x4``: the 16 corner tiles in
  the order of their bits or in any order for art over nothing, and the 16 edge tiles of a
  terrain that joins at its sides (a path, a fence), as a window of 4 x 4;
* ``rpg13_3x3``: a block of 3 x 3 (the terrain's middle, its four edges, its four outer
  corners) and its four inner corners wherever they lie near it (LimeZu puts them beside the
  block in a cross, others in a 2 x 2); ``minimal9_3x3`` the same block without them;
* ``strips``: the 1-wide ends and middles of a terrain laid in a column and in a row, and its
  single piece (*Tiny Farm*'s beds of soil): a terrain that joins at its sides.

Each block is a terrain of its own: a terrain set of one terrain, ``mode`` by what the block
has (``corners_and_sides``, ``corners`` or ``sides``), the peering bits of a side or corner
where the terrain does not go on ``-1``: nothing. Godot paints such a terrain over plain tiles
and over empty cells alike (the probe of T17.31), so one block is read the same whether it is
drawn over another ground or over transparency (``over`` says which). Plain variants of the
terrain's middle (the same surface, tiling with it) are its middle's variants with a lower
probability; groups of plain tiles that tile with each other are a terrain set of their own
(``shape`` ``plain``), so that a ground is painted with its variants.
"""

from __future__ import annotations

import colorsys
import hashlib
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from rpggen.core.terrain import blob
from rpggen.core.terrain import rpgmaker_a2 as a2
from rpggen.core.terrain.tiled_wang import empty_peering

# A seam fits when its pixels (RGBA, 0..255, a transparent pixel all 0) differ on average no
# more than SEAM_FLOOR, or than SEAM_RATIO times the difference of neighbouring pixels inside
# the two cells (drawn art has grain).
SEAM_FLOOR = 10.0
SEAM_RATIO = 2.0
# Where a terrain ends, the seam a continuation would have must differ this many times more
# than the seams inside the block.
END_CONTRAST = 2.0
END_FLOOR = 12.0
PAINTED = 0.5  # share of a cell's pixels that are painted for the cell to count as drawn
EMPTY = 0.02  # ... and at most this share for an empty one
OPAQUE_ALPHA = 230
VARIANT_PROBABILITY = 0.35
PLAIN_SPREAD = 0.35  # the most uneven a plain tile may be (sum of channel deviations, 0..1)
PLAIN_COLOUR = 0.07  # two plain tiles are of one surface within this mean colour distance
# A tile of one flat colour has no variants: two flat tiles of near colours laid at random are a
# checkerboard, not a ground that varies.
PLAIN_MIN_SPREAD = 0.03
PLAIN_SEAM_RATIO = 3.0
PLAIN_GROUP_COLOUR = 0.035  # the tones of the plain tiles of one ground differ at most this
MAX_PLAIN_CELLS = 256
NEAR = 4  # cells round a 3x3 block where its inner corners are looked for
CORNER_KEYS = (
    ("top_left_corner", 1),
    ("top_right_corner", 2),
    ("bottom_right_corner", 4),
    ("bottom_left_corner", 8),
)
SIDE_KEYS = (("top_side", 1), ("right_side", 4), ("bottom_side", 16), ("left_side", 64))

RPG13 = "rpg13_3x3"
MINIMAL9 = "minimal9_3x3"
RPG2X3 = "rpgmaker_2x3"
STRIPS = "strips"
SIDES16_DRAWN = "sides16_drawn_4x4"
PLAIN = "plain"
LAYOUTS = (
    blob.BLOB47_GODOT,
    blob.BLOB47,
    blob.CORNERS16,
    blob.CORNERS16_DRAWN,
    SIDES16_DRAWN,
    RPG13,
    MINIMAL9,
    RPG2X3,
    STRIPS,
    PLAIN,
)

# masks of the 3x3 block by its place (bits N=1, NE=2, E=4, SE=8, S=16, SW=32, W=64, NW=128)
_BLOCK3 = {
    (0, 0): 28,
    (1, 0): 124,
    (2, 0): 112,
    (0, 1): 31,
    (1, 1): 255,
    (2, 1): 241,
    (0, 2): 7,
    (1, 2): 199,
    (2, 2): 193,
}
_INNER = {"ne": 253, "se": 247, "sw": 223, "nw": 127}


@dataclass
class Block:
    """One terrain found in a sheet."""

    layout: str
    mode: str  # corners_and_sides | corners | sides
    # ((column, row) in the sheet, what the tile is: an 8-bit mask, corner bits or side bits)
    cells: list[tuple[tuple[int, int], int]]
    centre: tuple[int, int] | None
    over: str = "ground"  # ground | nothing
    surface: str = "other"
    shape: str = "area"  # area | any | path | plain
    variants: list[tuple[int, int]] = field(default_factory=list)
    # an RPG Maker block of 2 x 3 cells: the cell of its top left corner (its 47 tiles are
    # composed into an atlas of their own, ``rpgmaker_a2``)
    a2: tuple[int, int] | None = None
    picture: Any = None  # the six cells of such a block (a PIL image), to compose them

    @property
    def origin(self) -> tuple[int, int]:
        return min((c for c, _m in self.cells), key=lambda c: (c[1], c[0]))


# --------------------------------------------------------------------------- the sheet


class _Sheet:
    """The cells of a sheet and their edges, read once."""

    def __init__(self, rgba: np.ndarray, cw: int, ch: int) -> None:
        self.cw, self.ch = cw, ch
        self.rows, self.cols = rgba.shape[0] // ch, rgba.shape[1] // cw
        px = rgba[: self.rows * ch, : self.cols * cw].astype(np.int16)
        px[px[..., 3] == 0] = 0
        cells = px.reshape(self.rows, ch, self.cols, cw, 4).transpose(0, 2, 1, 3, 4)
        self.cells = cells
        self.top = cells[:, :, 0, :, :].astype(np.float32)
        self.bottom = cells[:, :, -1, :, :].astype(np.float32)
        self.left = cells[:, :, :, 0, :].astype(np.float32)
        self.right = cells[:, :, :, -1, :].astype(np.float32)
        alpha = cells[..., 3]
        self.painted = (alpha > 0).mean(axis=(2, 3))
        self.opaque = (alpha >= OPAQUE_ALPHA).mean(axis=(2, 3))
        grain_h = np.zeros((self.rows, self.cols), dtype=np.float32)
        grain_v = np.zeros((self.rows, self.cols), dtype=np.float32)
        for r in range(self.rows):  # a row of cells at a time: a large sheet stays small
            row = cells[r].astype(np.float32)
            if cw > 1:
                grain_h[r] = np.abs(np.diff(row, axis=2)).mean(axis=(1, 2, 3))
            if ch > 1:
                grain_v[r] = np.abs(np.diff(row, axis=1)).mean(axis=(1, 2, 3))
        self.grain_h, self.grain_v = grain_h, grain_v
        self.digest = [
            [
                hashlib.sha1(np.ascontiguousarray(cells[r, c]).tobytes()).digest()
                for c in range(self.cols)
            ]
            for r in range(self.rows)
        ]
        self.means = np.zeros((self.rows, self.cols, 3), dtype=np.float64)
        self.spreads = np.zeros((self.rows, self.cols), dtype=np.float64)
        for r in range(self.rows):
            flat = cells[r].reshape(self.cols, -1, 4).astype(np.float64)
            painted = flat[..., 3] > 0
            count = np.maximum(painted.sum(axis=1), 1)[:, None]
            self.means[r] = (flat[..., :3] * painted[..., None]).sum(axis=1) / count / 255.0
            self.spreads[r] = (flat[..., :3] / 255.0).std(axis=1).sum(axis=1)
        self.used = np.zeros((self.rows, self.cols), dtype=bool)

    def inside(self, c: tuple[int, int]) -> bool:
        return 0 <= c[0] < self.cols and 0 <= c[1] < self.rows

    def drawn(self, c: tuple[int, int]) -> bool:
        return bool(self.painted[c[1], c[0]] >= PAINTED)

    def empty(self, c: tuple[int, int]) -> bool:
        return bool(self.painted[c[1], c[0]] <= EMPTY)

    def same(self, a: tuple[int, int], b: tuple[int, int]) -> bool:
        return self.digest[a[1]][a[0]] == self.digest[b[1]][b[0]]

    def h_diff(self, a: tuple[int, int], b: tuple[int, int]) -> float:
        """How the right edge of ``a`` meets the left edge of ``b``."""
        return float(np.abs(self.right[a[1], a[0]] - self.left[b[1], b[0]]).mean())

    def v_diff(self, a: tuple[int, int], b: tuple[int, int]) -> float:
        """How the bottom edge of ``a`` meets the top edge of ``b``."""
        return float(np.abs(self.bottom[a[1], a[0]] - self.top[b[1], b[0]]).mean())

    def h_fits(self, a: tuple[int, int], b: tuple[int, int]) -> bool:
        limit = max(
            SEAM_FLOOR, SEAM_RATIO * max(self.grain_h[a[1], a[0]], self.grain_h[b[1], b[0]])
        )
        return self.h_diff(a, b) <= limit

    def v_fits(self, a: tuple[int, int], b: tuple[int, int]) -> bool:
        limit = max(
            SEAM_FLOOR, SEAM_RATIO * max(self.grain_v[a[1], a[0]], self.grain_v[b[1], b[0]])
        )
        return self.v_diff(a, b) <= limit

    def self_tiles(self, c: tuple[int, int]) -> bool:
        return self.h_fits(c, c) and self.v_fits(c, c)

    def tiles_closely(self, c: tuple[int, int]) -> bool:
        """Laid beside itself a plain tile's seams are as smooth as its own neighbouring pixels
        (within PLAIN_SEAM_RATIO; the measure of the plain ground of a farm): a gradient that
        looks plain is no ground to lay everywhere."""
        h = self.h_diff(c, c) <= PLAIN_SEAM_RATIO * max(float(self.grain_h[c[1], c[0]]), 1.0)
        v = self.v_diff(c, c) <= PLAIN_SEAM_RATIO * max(float(self.grain_v[c[1], c[0]]), 1.0)
        return h and v

    def even_to_its_edge(self, c: tuple[int, int]) -> bool:
        """True when a cell's border is of the colour of its inside: the middle of a terrain,
        not a patch drawn in the middle of another ground (which tiles with itself too)."""
        cell = self.cells[c[1], c[0]].astype(np.float64)
        h, w = cell.shape[:2]
        bh, bw = max(1, h // 8), max(1, w // 8)
        border = np.concatenate(
            [
                cell[:bh].reshape(-1, 4),
                cell[-bh:].reshape(-1, 4),
                cell[:, :bw].reshape(-1, 4),
                cell[:, -bw:].reshape(-1, 4),
            ]
        )
        inside = cell[h // 4 : h - h // 4, w // 4 : w - w // 4].reshape(-1, 4)
        if not len(inside):
            return True
        far = np.abs(border.mean(axis=0) - inside.mean(axis=0))[:3].mean() / 255.0
        return bool(far <= 2 * PLAIN_COLOUR)

    def across(self, c: tuple[int, int], vertical: bool) -> tuple[float, float, float]:
        """For a piece one cell wide: how its two long edges differ from each other, and how
        each differs from its own middle line (a strip has the same border on both sides and
        its own surface between)."""
        cell = self.cells[c[1], c[0]].astype(np.float32)
        if vertical:
            a, b, mid = cell[:, 0], cell[:, -1], cell[:, cell.shape[1] // 2]
        else:
            a, b, mid = cell[0], cell[-1], cell[cell.shape[0] // 2]
        return (
            float(np.abs(a - b).mean()),
            float(np.abs(a - mid).mean()),
            float(np.abs(b - mid).mean()),
        )

    def mean_colour(self, c: tuple[int, int]) -> np.ndarray:
        """The mean colour of a cell's painted pixels (0..1)."""
        return np.asarray(self.means[c[1], c[0]])

    def middle_colour(self, c: tuple[int, int]) -> np.ndarray:
        """The mean colour of the painted pixels of a cell's inner half (what its surface is,
        without the edge drawn round it)."""
        cell = self.cells[c[1], c[0]]
        h, w = cell.shape[:2]
        inside = cell[h // 4 : h - h // 4, w // 4 : w - w // 4].reshape(-1, 4)
        painted = inside[inside[:, 3] > 0]
        if not len(painted):
            return self.mean_colour(c)
        return np.asarray(painted[:, :3].mean(axis=0) / 255.0, dtype=np.float64)

    def spread(self, c: tuple[int, int]) -> float:
        """The sum of the standard deviations of a cell's colour channels (0..1)."""
        return float(self.spreads[c[1], c[0]])


# --------------------------------------------------------------------------- what a block is


def surface_of(colour: np.ndarray, words: set[str]) -> str:
    """The surface a terrain's middle is, by its colour and the words of its sheet."""
    r, g, b = (float(v) for v in colour)
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    hue = h * 360.0
    if v < 0.22:
        found = "dark"  # a hole, the dark of a cave: no surface to walk on
    elif s < 0.18:
        found = "snow" if v > 0.85 else "stone"
    elif 170 <= hue <= 260:
        # a clear blue is water; a dull or dark one is the rock of a cave
        found = "water" if s >= 0.3 and v >= 0.45 else "stone"
    elif 60 <= hue < 170:
        found = "grass"
    elif hue < 65 or hue > 330:
        found = "sand" if v >= 0.7 and 25 <= hue < 65 else "dirt"
    else:
        found = "other"
    if words & {"soil", "tilled", "farmland", "furrow", "field"}:
        if found in ("dirt", "sand", "stone", "other"):
            return "soil"
        if found == "water" or words & {"wet", "watered"}:
            return "soil_wet"
    road_words = {"path", "paths", "road", "roads", "brick", "cobble", "pavement", "street"}
    if words & road_words and found not in ("water", "grass"):
        return "path"
    if words & {"cliff", "cliffs", "rock", "rocks", "cave", "caves", "mountain"} and found in (
        "stone",
        "dirt",
        "other",
    ):
        return "rock"
    return found


def _mask_entry(mask: int, set_name: str) -> dict[str, Any]:
    return a2.peering_for_mask(mask, set_name)


def _bits_entry(bits: int, keys: tuple[tuple[str, int], ...], set_name: str) -> dict[str, Any]:
    peering = empty_peering()
    for key, bit in keys:
        if bits & bit:
            peering[key] = 0
    return {"set": set_name, "terrain": 0, "peering": peering}


def entries(block: Block, set_name: str) -> dict[str, dict[str, Any]]:
    """``tile_overrides`` of a block: ``"x,y" -> {terrain, probability?}``."""
    out: dict[str, dict[str, Any]] = {}
    for (cx, cy), what in block.cells:
        if block.mode == "corners_and_sides":
            terrain = _mask_entry(what, set_name)
        elif block.mode == "corners":
            terrain = _bits_entry(what, CORNER_KEYS, set_name)
        else:
            terrain = _bits_entry(what, SIDE_KEYS, set_name)
        out[f"{cx},{cy}"] = {"terrain": terrain}
    full = _full_entry(block, set_name)
    # T17.33: the middle is most of a ground (VARIANTS_SHARE of it for all its variants
    # together), so the variants are details here and there, never a patchwork
    share = (
        min(VARIANT_PROBABILITY, VARIANTS_SHARE / (1.0 - VARIANTS_SHARE) / len(block.variants))
        if block.variants
        else VARIANT_PROBABILITY
    )
    for cx, cy in block.variants:
        out[f"{cx},{cy}"] = {"terrain": full, "probability": round(share, 4)}
    return out


VARIANTS_SHARE = 0.15  # of a ground's cells, its variants' together at most


def _full_entry(block: Block, set_name: str) -> dict[str, Any]:
    if block.mode == "corners_and_sides":
        return _mask_entry(255, set_name)
    if block.mode == "corners":
        return _bits_entry(15, CORNER_KEYS, set_name)
    return _bits_entry(1 | 4 | 16 | 64, SIDE_KEYS, set_name)


def terrain_set(block: Block, set_name: str, index: int) -> dict[str, Any]:
    """The TileSetDef terrain set of a block (02_SCHEMAS §4.6 with the keys of T17.31)."""
    out = a2.terrain_set_def(set_name, index)
    out["mode"] = block.mode
    out["terrains"][0]["name"] = block.surface
    out.update(
        {
            "surface": block.surface,
            "over": block.over,
            "shape": block.shape,
            "layout": block.layout,
        }
    )
    return out


# --------------------------------------------------------------------------- finding blocks


def packed(
    rgba: np.ndarray, cw: int, ch: int, margin: tuple[int, int], sep: tuple[int, int]
) -> np.ndarray:
    """The cells of a sheet cut with a margin and a separation, laid side by side without them
    (a cell keeps its column and row)."""
    if margin == (0, 0) and sep == (0, 0):
        return rgba
    cols = max(0, (rgba.shape[1] - 2 * margin[0] + sep[0]) // (cw + sep[0]))
    rows = max(0, (rgba.shape[0] - 2 * margin[1] + sep[1]) // (ch + sep[1]))
    out = np.zeros((rows * ch, cols * cw, 4), dtype=rgba.dtype)
    for r in range(rows):
        y = margin[1] + r * (ch + sep[1])
        for c in range(cols):
            x = margin[0] + c * (cw + sep[0])
            out[r * ch : (r + 1) * ch, c * cw : (c + 1) * cw] = rgba[y : y + ch, x : x + cw]
    return out


def find(rgba: np.ndarray, cw: int, ch: int, words: set[str] | None = None) -> list[Block]:
    """Every terrain block of a sheet of ``cw`` x ``ch`` cells (``rgba``: H x W x 4, uint8; a
    sheet with a margin or a separation is ``packed`` first), in the order they were found."""
    if cw < 2 or ch < 2 or rgba.shape[0] < ch or rgba.shape[1] < cw:
        return []
    sheet = _Sheet(rgba, cw, ch)
    words = words or set()
    found: list[Block] = []
    found += _blob_windows(sheet)
    found += _square_windows(sheet)
    found += _blocks2x3(sheet)
    found += _blocks3(sheet)
    found += _strips(sheet)
    for b in found:
        if b.centre is not None:
            b.variants = _variants(sheet, b.centre)
    found += _plain_groups(sheet)
    for b in found:
        ref = b.centre or ((b.a2[0] + 1, b.a2[1]) if b.a2 else b.cells[0][0])
        b.surface = surface_of(sheet.middle_colour(ref), words)
    return found


def _take(sheet: _Sheet, cells: list[tuple[tuple[int, int], int]]) -> None:
    for (cx, cy), _w in cells:
        sheet.used[cy, cx] = True


def _free(sheet: _Sheet, x0: int, y0: int, w: int, h: int) -> bool:
    return not bool(sheet.used[y0 : y0 + h, x0 : x0 + w].any())


def _over(sheet: _Sheet, cells: list[tuple[int, int]]) -> str:
    """``nothing`` when the outer edges of a block's tiles are mostly transparent."""
    edge_alpha = []
    for c in cells:
        cell = sheet.cells[c[1], c[0]][..., 3]
        edge_alpha.append(
            float(np.concatenate([cell[0], cell[-1], cell[:, 0], cell[:, -1]]).astype(bool).mean())
        )
    return "nothing" if min(edge_alpha) < 0.5 else "ground"


def _judge_window(
    sheet: _Sheet,
    x0: int,
    y0: int,
    table: list[tuple[tuple[int, int], dict[str, Any]]],
    key: str = "",
) -> tuple[float, float]:
    """``(confidence, contrast)`` of a layout laid at ``(x0, y0)`` (``blob._judge`` on the edges
    the sheet has read)."""
    coords = [(x0 + c[0], y0 + c[1]) for c, _e in table]
    ys = np.array([c[1] for c in coords])
    xs = np.array([c[0] for c in coords])
    right, left = sheet.right[ys, xs], sheet.left[ys, xs]
    bottom, top = sheet.bottom[ys, xs], sheet.top[ys, xs]
    dh = np.abs(right[:, None] - left[None, :]).mean(axis=(2, 3))
    dv = np.abs(bottom[:, None] - top[None, :]).mean(axis=(2, 3))
    gh = sheet.grain_h[ys, xs]
    gv = sheet.grain_v[ys, xs]
    lim_h = np.maximum(SEAM_FLOOR, SEAM_RATIO * np.maximum(gh[:, None], gh[None, :]))
    lim_v = np.maximum(SEAM_FLOOR, SEAM_RATIO * np.maximum(gv[:, None], gv[None, :]))
    exp_h, oth_h, exp_v, oth_v = _pairs(table, key)
    fitting = float(dh[exp_h].sum() + dv[exp_v].sum())
    expected = int(exp_h.sum() + exp_v.sum())
    other = float(dh[oth_h].sum() + dv[oth_v].sum())
    others = int(oth_h.sum() + oth_v.sum())
    matched = int((dh[exp_h] <= lim_h[exp_h]).sum() + (dv[exp_v] <= lim_v[exp_v]).sum())
    confidence = matched / expected if expected else 0.0
    contrast = 1.0
    if expected and others and other > 0:
        contrast = (fitting / expected) / (other / others)
    return confidence, contrast


_PAIRS: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = {}


def _pairs(
    table: list[tuple[tuple[int, int], dict[str, Any]]], key: str = ""
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Which pairs of a layout's tiles must fit side by side and which must not; a fixed
    layout's (``key``) are worked out once."""
    if key and key in _PAIRS:
        return _PAIRS[key]
    n = len(table)
    exp_h = np.zeros((n, n), dtype=bool)
    oth_h = np.zeros((n, n), dtype=bool)
    exp_v = np.zeros((n, n), dtype=bool)
    oth_v = np.zeros((n, n), dtype=bool)
    for i, (_c, ea) in enumerate(table):
        for j, (_d, eb) in enumerate(table):
            for side_a, side_b, exp, oth in (
                ("right", "left", exp_h, oth_h),
                ("bottom", "top", exp_v, oth_v),
            ):
                da, db = ea[side_a], eb[side_b]
                if da is None or db is None:
                    continue
                if da == db:
                    exp[i, j] = True
                else:
                    oth[i, j] = True
    if key:
        _PAIRS[key] = (exp_h, oth_h, exp_v, oth_v)
    return exp_h, oth_h, exp_v, oth_v


_TABLES: dict[str, list[tuple[tuple[int, int], dict[str, Any]]]] = {}


def _table(layout: str) -> list[tuple[tuple[int, int], dict[str, Any]]]:
    if layout not in _TABLES:
        _TABLES[layout] = blob._tile_table(layout)
    return _TABLES[layout]


def _accept(sheet: _Sheet, confidence: float, contrast: float) -> bool:
    return contrast <= blob.CONTRAST_LIMIT and confidence >= 0.6


def _blob_windows(sheet: _Sheet) -> list[Block]:
    """The 47-tile blobs of the sheet, in Godot's template or in the masks' order."""
    out: list[Block] = []
    if sheet.cols < 12 or sheet.rows < 4:
        return out
    drawn = sheet.painted >= PAINTED
    empty = sheet.painted <= EMPTY
    for layout, hole in ((blob.BLOB47_GODOT, (10, 1)), (blob.BLOB47, (11, 3))):
        table = _table(layout)
        for y0 in range(sheet.rows - 3):
            for x0 in range(sheet.cols - 11):
                if not empty[y0 + hole[1], x0 + hole[0]] or not _free(sheet, x0, y0, 12, 4):
                    continue
                cells = [(x0 + c[0], y0 + c[1]) for c, _e in table]
                if sum(bool(drawn[c[1], c[0]]) for c in cells) < blob.MIN_FILLED * 47:
                    continue
                if len({sheet.digest[c[1]][c[0]] for c in cells}) < blob.MIN_DISTINCT * 47:
                    continue
                confidence, contrast = _judge_window(sheet, x0, y0, table, layout)
                if not _accept(sheet, confidence, contrast):
                    continue
                masks = blob._blob_cells(layout)
                tiles = [
                    ((x0 + c[0], y0 + c[1]), m) for c, m in masks if drawn[y0 + c[1], x0 + c[0]]
                ]
                centre = next(((x0 + c[0], y0 + c[1]) for c, m in masks if m == 255), None)
                _take(sheet, [((x0 + x, y0 + y), 0) for x in range(12) for y in range(4)])
                if centre is None or not sheet.drawn(centre):
                    continue  # a ring round a hole: the layout, but no terrain of its own
                b = Block(layout, "corners_and_sides", tiles, centre, shape="any")
                b.over = _over(sheet, [c for c, _m in tiles])
                out.append(b)
    return out


def _corner_bits(sheet: _Sheet, c: tuple[int, int]) -> int:
    alpha = sheet.cells[c[1], c[0]][..., 3]
    return (
        (1 if alpha[0, 0] else 0)
        | (2 if alpha[0, -1] else 0)
        | (4 if alpha[-1, -1] else 0)
        | (8 if alpha[-1, 0] else 0)
    )


def _side_bits(sheet: _Sheet, c: tuple[int, int]) -> int:
    alpha = sheet.cells[c[1], c[0]][..., 3]
    h, w = alpha.shape
    return (
        (1 if alpha[0, w // 2] else 0)
        | (4 if alpha[h // 2, -1] else 0)
        | (16 if alpha[-1, w // 2] else 0)
        | (64 if alpha[h // 2, 0] else 0)
    )


def _sides_edges(bits: int) -> dict[str, Any]:
    return {
        "top": (bool(bits & 1),),
        "right": (bool(bits & 4),),
        "bottom": (bool(bits & 16),),
        "left": (bool(bits & 64),),
    }


def _square_windows(sheet: _Sheet) -> list[Block]:
    """The 16-tile corner sets (in the order of their bits, or drawn over nothing in any
    order) and the 16-tile edge sets drawn over nothing, as windows of 4 x 4 cells."""
    out: list[Block] = []
    if sheet.cols < 4 or sheet.rows < 4:
        return out
    fixed = _table(blob.CORNERS16)
    for y0 in range(sheet.rows - 3):
        for x0 in range(sheet.cols - 3):
            if not _free(sheet, x0, y0, 4, 4):
                continue
            cells = [(x0 + i % 4, y0 + i // 4) for i in range(16)]
            drawn = [sheet.drawn(c) for c in cells]
            painted = [not sheet.empty(c) for c in cells]
            if sum(painted) < 15 or len({sheet.digest[c[1]][c[0]] for c in cells}) < 15:
                continue
            found: Block | None = None
            corners = [_corner_bits(sheet, c) for c in cells]
            sides = [_side_bits(sheet, c) for c in cells]
            if len(set(corners)) == 16:
                table = [
                    ((i % 4, i // 4), blob._corner_edges(bits)) for i, bits in enumerate(corners)
                ]
                conf, contrast = _judge_window(sheet, x0, y0, table)
                if _accept(sheet, conf, contrast):
                    found = Block(
                        blob.CORNERS16_DRAWN,
                        "corners",
                        list(zip(cells, corners, strict=True)),
                        None,
                    )
            if found is None and len(set(sides)) == 16:
                table = [((i % 4, i // 4), _sides_edges(bits)) for i, bits in enumerate(sides)]
                conf, contrast = _judge_window(sheet, x0, y0, table)
                if _accept(sheet, conf, contrast):
                    found = Block(
                        SIDES16_DRAWN,
                        "sides",
                        list(zip(cells, sides, strict=True)),
                        None,
                        shape="path",
                    )
            if found is None and all(drawn[1:]):
                conf, contrast = _judge_window(sheet, x0, y0, fixed, blob.CORNERS16)
                if _accept(sheet, conf, contrast) and conf >= blob.ACCEPT_RATIO:
                    found = Block(
                        blob.CORNERS16, "corners", [(c, i) for i, c in enumerate(cells)], None
                    )
            if found is None:
                continue
            full = 15 if found.mode == "corners" else 1 | 4 | 16 | 64
            found.centre = next((c for c, what in found.cells if what == full), None)
            found.cells = [(c, w) for c, w in found.cells if not sheet.empty(c) or w]
            found.over = _over(sheet, [c for c, _w in found.cells])
            if found.mode == "corners":
                found.shape = "any"
            _take(sheet, [(c, 0) for c in cells])
            out.append(found)
    return out


def _region_colour(cells: list[np.ndarray]) -> np.ndarray:
    painted = [c[..., :3][c[..., 3] > 0] for c in cells]
    joined = (
        np.concatenate([p for p in painted if len(p)]) if any(len(p) for p in painted) else None
    )
    return np.zeros(3) if joined is None else np.asarray(joined.mean(axis=0) / 255.0)


def _edged(
    sheet: _Sheet, c: tuple[int, int], middle: np.ndarray, *strips: tuple[slice, slice]
) -> bool:
    """True when every strip of a cell has another colour than the terrain's middle."""
    pixels = sheet.cells[c[1], c[0]]
    return all(
        float(np.abs(_region_colour([pixels[s]]) - middle).mean()) >= PLAIN_COLOUR for s in strips
    )


def _blocks2x3(sheet: _Sheet) -> list[Block]:
    """Blocks of RPG Maker's 2 x 3 layout (``rpgmaker_2x3``) inside a sheet: a cell that shows
    the terrain as an island (or nothing), the cell of its inner corners beside it, and under
    them a 2 x 2 patch of the terrain with its whole edge round it. The 47 tiles are composed
    of the quarters of the six cells (``rpgmaker_a2``), as for a sheet that is all A2."""
    out: list[Block] = []
    if sheet.cw != sheet.ch or sheet.cw % 2:
        return out
    q = sheet.cw // 2
    for y0 in range(sheet.rows - 2):
        for x0 in range(sheet.cols - 1):
            if not _free(sheet, x0, y0, 2, 3):
                continue
            tl, tr = (x0, y0 + 1), (x0 + 1, y0 + 1)
            bl, br = (x0, y0 + 2), (x0 + 1, y0 + 2)
            corner = (x0 + 1, y0)
            if not all(sheet.drawn(c) for c in (tl, tr, bl, br, corner)):
                continue
            if len({sheet.digest[c[1]][c[0]] for c in (tl, tr, bl, br, corner)}) < 5:
                continue
            seams = (
                sheet.h_fits(tl, tr),
                sheet.h_fits(bl, br),
                sheet.v_fits(tl, bl),
                sheet.v_fits(tr, br),
            )
            if not all(seams):
                continue
            # its middle (the quarters at the middle of the patch) is one surface, painted all
            # over, and its edge differs
            cell = sheet.cells
            quarters = [
                cell[tl[1], tl[0]][q:, q:],
                cell[tr[1], tr[0]][q:, :q],
                cell[bl[1], bl[0]][:q, q:],
                cell[br[1], br[0]][:q, :q],
            ]
            inside = np.concatenate([part.reshape(-1, 4) for part in quarters])
            if (inside[:, 3] >= OPAQUE_ALPHA).mean() < 0.95:
                continue
            if float((inside[:, :3] / 255.0).std(axis=0).sum()) > PLAIN_SPREAD:
                continue
            middle = _region_colour(quarters)
            rim = _region_colour(
                [cell[tl[1], tl[0]][:2], cell[bl[1], bl[0]][-2:], cell[tl[1], tl[0]][:, :2]]
            )
            if float(np.abs(middle - rim).mean()) < PLAIN_COLOUR:
                continue

            # every cell of the patch has the edge on its two outer sides (a part of a 3x3
            # block has it on one side or none)
            top, bottom = (slice(0, 2), slice(None)), (slice(-2, None), slice(None))
            left, right = (slice(None), slice(0, 2)), (slice(None), slice(-2, None))
            if not (
                _edged(sheet, tl, middle, top, left)
                and _edged(sheet, tr, middle, top, right)
                and _edged(sheet, bl, middle, bottom, left)
                and _edged(sheet, br, middle, bottom, right)
            ):
                continue
            # the cell of the inner corners is the middle at its middle, the edge at its corners
            c = cell[corner[1], corner[0]]
            at_middle = _region_colour([c[q // 2 : q + q // 2, q // 2 : q + q // 2]])
            if float(np.abs(at_middle - middle).mean()) > PLAIN_COLOUR:
                continue
            block = Block(
                RPG2X3,
                "corners_and_sides",
                [((x0 + dx, y0 + dy), 0) for dy in range(3) for dx in range(2)],
                None,
            )
            block.shape = "any"
            block.a2 = (x0, y0)
            block.over = _over(sheet, [tl, br])
            _take(sheet, block.cells)
            out.append(block)
    return out


def _end_ok(inner: list[float], ends: list[float]) -> bool:
    """The seams where a terrain ends differ clearly more than the seams inside it."""
    if not ends:
        return False
    base = max(float(np.mean(inner)) if inner else 0.0, 1.0)
    clear = sum(1 for e in ends if e >= max(END_FLOOR, END_CONTRAST * base))
    return clear >= len(ends) - 1


def _blocks3(sheet: _Sheet) -> list[Block]:
    """Blocks of 3 x 3 cells round a middle that tiles with itself, with their inner corners
    when they are near."""
    out: list[Block] = []
    for cy in range(1, sheet.rows - 1):
        for cx in range(1, sheet.cols - 1):
            if not _free(sheet, cx - 1, cy - 1, 3, 3):
                continue
            c = (cx, cy)
            if not sheet.drawn(c) or not sheet.self_tiles(c) or not sheet.even_to_its_edge(c):
                continue
            at = {(dx, dy): (cx + dx - 1, cy + dy - 1) for dx in range(3) for dy in range(3)}
            if not all(sheet.drawn(at[k]) for k in at):
                continue
            ring = [at[k] for k in at if k != (1, 1)]
            if any(sheet.same(r, c) for r in ring):
                continue
            if len({sheet.digest[r[1]][r[0]] for r in ring}) < 8:
                continue
            inner: list[float] = []
            ok = True
            for y in range(3):
                for x in range(2):
                    a, b = at[(x, y)], at[(x + 1, y)]
                    ok = ok and sheet.h_fits(a, b)
                    inner.append(sheet.h_diff(a, b))
            for y in range(2):
                for x in range(3):
                    a, b = at[(x, y)], at[(x, y + 1)]
                    ok = ok and sheet.v_fits(a, b)
                    inner.append(sheet.v_diff(a, b))
            if not ok:
                continue
            # the edges repeat along the block's sides
            tm, bm, ml, mr = at[(1, 0)], at[(1, 2)], at[(0, 1)], at[(2, 1)]
            if not (sheet.h_fits(tm, tm) and sheet.h_fits(bm, bm)):
                continue
            if not (sheet.v_fits(ml, ml) and sheet.v_fits(mr, mr)):
                continue
            # and the terrain ends round it: the middle laid outside a side would not fit
            ends = [
                sheet.v_diff(c, at[(0, 0)]),
                sheet.v_diff(c, tm),
                sheet.v_diff(c, at[(2, 0)]),
                sheet.v_diff(at[(0, 2)], c),
                sheet.v_diff(bm, c),
                sheet.v_diff(at[(2, 2)], c),
                sheet.h_diff(c, ml),
                sheet.h_diff(mr, c),
            ]
            if not _end_ok(inner, ends):
                continue
            cells = [(at[k], _BLOCK3[k]) for k in sorted(at, key=lambda k: (k[1], k[0]))]
            blocked = {at[k] for k in at}
            corners = _inner_corners(sheet, at, blocked)
            layout = MINIMAL9
            if corners is not None:
                layout = RPG13
                cells += [(corners[n], _INNER[n]) for n in ("ne", "se", "sw", "nw")]
            block = Block(layout, "corners_and_sides", cells, c)
            block.over = _over(sheet, [at[(0, 0)], at[(2, 2)]])
            _take(sheet, cells)
            out.append(block)
    return out


def _inner_corners(
    sheet: _Sheet, at: dict[tuple[int, int], tuple[int, int]], blocked: set[tuple[int, int]]
) -> dict[str, tuple[int, int]] | None:
    """The four inner corners of a 3x3 block, each the cell near it whose four seams fit: on
    the two sides where the terrain goes on the middle, on the other two the edge it meets."""
    c = at[(1, 1)]
    tm, bm, ml, mr = at[(1, 0)], at[(1, 2)], at[(0, 1)], at[(2, 1)]
    xs = range(max(0, at[(0, 0)][0] - NEAR), min(sheet.cols, at[(2, 2)][0] + NEAR + 1))
    ys = range(max(0, at[(0, 0)][1] - NEAR), min(sheet.rows, at[(2, 2)][1] + NEAR + 1))
    tests = {
        # notch -> the four seams it has, (cell first, how), and which tile is beside it
        "ne": lambda k: (
            sheet.h_diff(c, k),
            sheet.v_diff(k, c),
            sheet.v_diff(mr, k),
            sheet.h_diff(k, tm),
        ),
        "nw": lambda k: (
            sheet.h_diff(k, c),
            sheet.v_diff(k, c),
            sheet.v_diff(ml, k),
            sheet.h_diff(tm, k),
        ),
        "se": lambda k: (
            sheet.h_diff(c, k),
            sheet.v_diff(c, k),
            sheet.v_diff(k, mr),
            sheet.h_diff(k, bm),
        ),
        "sw": lambda k: (
            sheet.h_diff(k, c),
            sheet.v_diff(c, k),
            sheet.v_diff(k, ml),
            sheet.h_diff(bm, k),
        ),
    }
    limit_of = max(
        SEAM_FLOOR, SEAM_RATIO * float(max(sheet.grain_h[c[1], c[0]], sheet.grain_v[c[1], c[0]]))
    )
    found: dict[str, tuple[int, int]] = {}
    for notch, test in tests.items():
        best: tuple[float, tuple[int, int]] | None = None
        for y in ys:
            for x in xs:
                k = (x, y)
                if k in blocked or sheet.used[y, x] or not sheet.drawn(k) or sheet.same(k, c):
                    continue
                if k in found.values():
                    continue
                diffs = test(k)
                limit = max(
                    limit_of, SEAM_RATIO * float(max(sheet.grain_h[y, x], sheet.grain_v[y, x]))
                )
                if max(diffs) > limit:
                    continue
                score = float(sum(diffs))
                if best is None or score < best[0]:
                    best = (score, k)
        if best is None:
            return None
        found[notch] = best[1]
    return found


def _strips(sheet: _Sheet) -> list[Block]:
    """A terrain one cell wide: its ends and middle laid in a column, in a row, and its single
    piece, of one surface (``sides``: N 1, E 4, S 16, W 64)."""
    runs: dict[str, list[tuple[tuple[int, int], tuple[int, int], tuple[int, int]]]] = {
        "v": [],
        "h": [],
    }
    for y in range(sheet.rows):
        for x in range(sheet.cols):
            for way in ("v", "h"):
                if way == "v" and y + 2 >= sheet.rows:
                    continue
                if way == "h" and x + 2 >= sheet.cols:
                    continue
                cells = (
                    [(x, y + i) for i in range(3)] if way == "v" else [(x + i, y) for i in range(3)]
                )
                if any(sheet.used[c[1], c[0]] or not sheet.drawn(c) for c in cells):
                    continue
                first, mid, last = cells
                if sheet.same(first, mid) or sheet.same(mid, last) or sheet.same(first, last):
                    continue
                if way == "v":
                    inner = [sheet.v_diff(first, mid), sheet.v_diff(mid, last)]
                    fits = (
                        sheet.v_fits(first, mid)
                        and sheet.v_fits(mid, last)
                        and sheet.v_fits(mid, mid)
                    )
                    ends = [sheet.v_diff(mid, first), sheet.v_diff(last, mid)]
                else:
                    inner = [sheet.h_diff(first, mid), sheet.h_diff(mid, last)]
                    fits = (
                        sheet.h_fits(first, mid)
                        and sheet.h_fits(mid, last)
                        and sheet.h_fits(mid, mid)
                    )
                    ends = [sheet.h_diff(mid, first), sheet.h_diff(last, mid)]
                if not fits:
                    continue
                base = max(END_FLOOR, END_CONTRAST * max(float(np.mean(inner)), 1.0))
                if not all(e >= base for e in ends):
                    continue
                # one cell wide: a border on both long sides, its own surface between
                _apart, near_a, near_b = sheet.across(mid, way == "v")
                if min(near_a, near_b) < base:
                    continue
                runs[way].append((first, mid, last))
    out: list[Block] = []
    for first, mid, last in runs["v"]:
        if any(sheet.used[c[1], c[0]] for c in (first, mid, last)):
            continue
        colour = sheet.mean_colour(mid)
        across = [
            r
            for r in runs["h"]
            if not any(sheet.used[c[1], c[0]] for c in r)
            and float(np.abs(sheet.mean_colour(r[1]) - colour).mean()) <= PLAIN_COLOUR
        ]
        if not across:
            continue
        left, hmid, right = across[0]
        pieces = [(first, 16), (mid, 1 | 16), (last, 1), (left, 4), (hmid, 4 | 64), (right, 64)]
        single = _single(sheet, first, last, left, right, {c for c, _w in pieces})
        if single is not None:
            pieces.append((single, 0))
        block = Block(STRIPS, "sides", pieces, None, shape="path")
        block.over = _over(sheet, [first, last])
        _take(sheet, pieces)
        out.append(block)
    return out


def _single(
    sheet: _Sheet,
    top: tuple[int, int],
    bottom: tuple[int, int],
    left: tuple[int, int],
    right: tuple[int, int],
    taken: set[tuple[int, int]],
) -> tuple[int, int] | None:
    """The piece of a strip that joins nowhere: its top edge like the top end's, its bottom like
    the bottom end's, its left like the left end's and its right like the right end's."""
    best: tuple[float, tuple[int, int]] | None = None
    for y in range(sheet.rows):
        for x in range(sheet.cols):
            k = (x, y)
            if k in taken or sheet.used[y, x] or not sheet.drawn(k):
                continue
            diffs = (
                float(np.abs(sheet.top[y, x] - sheet.top[top[1], top[0]]).mean()),
                float(np.abs(sheet.bottom[y, x] - sheet.bottom[bottom[1], bottom[0]]).mean()),
                float(np.abs(sheet.left[y, x] - sheet.left[left[1], left[0]]).mean()),
                float(np.abs(sheet.right[y, x] - sheet.right[right[1], right[0]]).mean()),
            )
            if max(diffs) > SEAM_FLOOR * 2:
                continue
            if best is None or sum(diffs) < best[0]:
                best = (sum(diffs), k)
    return best[1] if best else None


def _is_plain(sheet: _Sheet, c: tuple[int, int]) -> bool:
    return (
        bool(sheet.opaque[c[1], c[0]] >= 0.98)
        and sheet.tiles_closely(c)
        and PLAIN_MIN_SPREAD <= sheet.spread(c) <= PLAIN_SPREAD
    )


def _tile_together(sheet: _Sheet, a: tuple[int, int], b: tuple[int, int]) -> bool:
    return sheet.h_fits(a, b) and sheet.h_fits(b, a) and sheet.v_fits(a, b) and sheet.v_fits(b, a)


def _variants(sheet: _Sheet, centre: tuple[int, int]) -> list[tuple[int, int]]:
    """Plain cells of the sheet that are the middle of a terrain once more: of its surface and
    tiling with it every way."""
    if not sheet.self_tiles(centre) or sheet.spread(centre) < PLAIN_MIN_SPREAD:
        return []
    colour = sheet.mean_colour(centre)
    alpha_like = sheet.opaque[centre[1], centre[0]]
    out = []
    for y in range(sheet.rows):
        for x in range(sheet.cols):
            k = (x, y)
            if sheet.used[y, x] or k == centre or sheet.same(k, centre) or not sheet.drawn(k):
                continue
            if abs(float(sheet.opaque[y, x]) - float(alpha_like)) > 0.05:
                continue
            if float(np.abs(sheet.mean_colour(k) - colour).mean()) > PLAIN_COLOUR:
                continue
            if not sheet.tiles_closely(k) or not _tile_together(sheet, centre, k):
                continue
            out.append(k)
    # T17.33: a variant shows no seam of its own and has the middle's grain
    grain = _grain(sheet, centre)
    out = [
        k
        for k in out
        if _seam_ratio(sheet, k) <= max(SEAMLESS_RATIO, _seam_ratio(sheet, centre))
        and max(_grain(sheet, k), grain) / min(_grain(sheet, k), grain) <= GRAIN_RATIO
    ]
    for k in out:
        sheet.used[k[1], k[0]] = True
    return out


# T17.33: laid beside itself a tile of a plain ground shows no seam (its edges differ from each
# other at most this much more than its neighbouring pixels do), and its variants are of the
# grain of its middle (CuteSCKR's grass: two coarse tiles among two fine ones made a draughts
# board, and a seam of 1.3 times the grain was a line between every two tiles)
SEAMLESS_RATIO = 1.25
GRAIN_RATIO = 1.3


def _seam_ratio(sheet: _Sheet, c: tuple[int, int]) -> float:
    h = sheet.h_diff(c, c) / max(float(sheet.grain_h[c[1], c[0]]), 1.0)
    v = sheet.v_diff(c, c) / max(float(sheet.grain_v[c[1], c[0]]), 1.0)
    return max(float(h), float(v))


def _grain(sheet: _Sheet, c: tuple[int, int]) -> float:
    return max(1.0, (float(sheet.grain_h[c[1], c[0]]) + float(sheet.grain_v[c[1], c[0]])) / 2.0)


def _seamless(sheet: _Sheet, group: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """The tiles of a group of plain tiles that lie together without a seam: the smoothest
    first (it is the middle), then those whose own seams are as smooth and whose grain is its
    grain. A group whose every tile shows a seam keeps its smoothest alone."""
    ranked = sorted(group, key=lambda c: (round(_seam_ratio(sheet, c), 6), c[1], c[0]))
    best = ranked[0]
    grain = _grain(sheet, best)
    kept = [best]
    for c in ranked[1:]:
        if _seam_ratio(sheet, c) > SEAMLESS_RATIO:
            continue
        g = _grain(sheet, c)
        if max(g, grain) / min(g, grain) > GRAIN_RATIO:
            continue
        kept.append(c)
    return kept


def _plain_groups(sheet: _Sheet) -> list[Block]:
    """Plain tiles not in any block that tile with each other: each group is a terrain of
    middles only (``shape`` ``plain``), the ground's variants."""
    plain = []
    for y in range(sheet.rows):
        for x in range(sheet.cols):
            if not sheet.used[y, x] and _is_plain(sheet, (x, y)):
                plain.append((x, y))
            if len(plain) >= MAX_PLAIN_CELLS:
                break
        if len(plain) >= MAX_PLAIN_CELLS:
            break
    seen_digest: set[bytes] = set()
    unique = []
    for c in plain:
        d = sheet.digest[c[1]][c[0]]
        if d not in seen_digest:
            seen_digest.add(d)
            unique.append(c)
    out: list[Block] = []
    left = list(unique)
    while left:
        first = left.pop(0)
        colour = sheet.mean_colour(first)
        group = [first]
        rest = []
        for k in left:
            # laid at random among each other they must look one ground: of one tone, and
            # tiling with every tile of the group
            near = float(np.abs(sheet.mean_colour(k) - colour).mean()) <= PLAIN_GROUP_COLOUR
            if near and all(_tile_together(sheet, m, k) for m in group):
                group.append(k)
            else:
                rest.append(k)
        left = rest
        if len(group) < 2:
            continue
        # the smoothest is the ground's middle, alone when every other tile shows a seam
        group = _seamless(sheet, group)
        b = Block(PLAIN, "corners_and_sides", [(group[0], 255)], group[0], shape="plain")
        b.variants = group[1:]
        b.over = "ground"
        for k in group:
            sheet.used[k[1], k[0]] = True
        out.append(b)
    return out
