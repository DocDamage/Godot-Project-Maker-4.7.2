"""What the tiles of a side-view tile sheet are, read from their pictures (T17.32).

Kenney's pixel platformer packs, pozak's and ansimuz's stage packs ship their tiles as one sheet
(often with the same tiles again as numbered files, ``tile_0001.png``) and no name says which
tile is the ground, a platform, a ladder or spikes. This module reads it off the pixels, one
cell at a time and then cells against cells:

* **Ground as a terrain.** A *fill* is an opaque cell that tiles with itself both ways. Every
  other mostly painted cell is compared with the fills along its four sides: a side **joins**
  the ground when its edge continues the fill's opposite edge (the seam within the noise of
  the cells' own neighbouring pixels), or continues a cell of the same surface beside it (a
  grass top beside a grass top). A cell whose bottom joins a fill and whose top does not is a
  surface piece (its top is the sky); which of its other sides join says whether it is the
  middle of a surface, its left or right end or a column one cell wide, and the same for the
  pieces under an overhang, the faces of a wall and the caps of a ledge one cell high. Each
  fill with the pieces that join it is one side-view terrain (``shape: side``): the cells'
  peering bits say where the ground goes on (Godot's *match sides* mode), so a room painted
  with it has its grass on top, its ends rounded and its inside filled.
* **The other kinds**, each only where its picture leaves no doubt: a **one-way platform** is a
  cell painted across its whole width in its top part and empty below, tiling sideways; a
  **ladder** has two rails from top to bottom with rungs between and tiles upwards; **spikes**
  are painted only in the lower part of the cell, on a base, with two teeth or more, in grey or
  white; **water** is blue and tiles sideways; a **coin** is a small round or upright gold shape
  in the middle of the cell. They become the tiles' collision (``ONE_WAY``, ``LADDER``) and
  custom data (``hazard``) as the side-view rooms read them (``builder/lib/side_tileset.gd``).
* Every other painted cell **stays unread** (a door, a flag, a key, a sign, a digit: their
  shapes are too alike to tell with confidence), and the sheet's note TILE-016 counts them.

Everything here is integer and float arithmetic on the pixels: the same sheet gives the same
answer on every machine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

ALPHA = 128
# a cell painted over less than this is empty
EMPTY = 0.02
OPAQUE = 0.98
EDGE_FULL = 0.9
# a seam fits within this much difference of colour (0..1), plus the cells' own noise
SEAM_TOL = 0.07
SEAM_NOISE = 1.5
ALPHA_AGREE = 0.9

# peering bits of the sides (as terrain.blocks.SIDE_KEYS): N, E, S, W
N, E, S, W = 1, 4, 16, 64
ALL = N | E | S | W

FILL = "fill"
ONE_WAY = "one_way"
LADDER = "ladder"
SPIKES = "spikes"
WATER = "water"
COIN = "coin"
KINDS = (FILL, ONE_WAY, LADDER, SPIKES, WATER, COIN)


@dataclass
class Cell:
    x: int
    y: int
    rgba: np.ndarray  # h x w x 4, uint8
    cover: float = 0.0
    alpha: np.ndarray = field(default_factory=lambda: np.zeros((0, 0), bool))
    # what was measured of the cell once (its edges, its colours), by key
    memo: dict[Any, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.x},{self.y}"


@dataclass
class SheetRead:
    """What was read of one sheet: ``kinds`` by cell key, the side-view terrains (each the
    peering mask of its cells by key and the surface), and how many painted cells stay unread."""

    kinds: dict[str, str] = field(default_factory=dict)
    terrains: list[tuple[str, dict[str, int]]] = field(default_factory=list)
    unread: int = 0
    painted: int = 0


def cells_of(
    rgba: np.ndarray, cw: int, ch: int, margin: tuple[int, int], sep: tuple[int, int]
) -> list[Cell]:
    """The cells of a sheet cut on its grid, row by row."""
    h, w = rgba.shape[:2]
    out: list[Cell] = []
    cols = (w - margin[0] + sep[0]) // (cw + sep[0])
    rows = (h - margin[1] + sep[1]) // (ch + sep[1])
    for cy in range(rows):
        for cx in range(cols):
            x0 = margin[0] + cx * (cw + sep[0])
            y0 = margin[1] + cy * (ch + sep[1])
            part = rgba[y0 : y0 + ch, x0 : x0 + cw]
            if part.shape[0] != ch or part.shape[1] != cw:
                continue
            mask = part[:, :, 3] >= ALPHA
            out.append(Cell(cx, cy, part, float(mask.mean()), mask))
    return out


# --------------------------------------------------------------------------- edges and seams


def _lines(cell: Cell, side: int) -> tuple[np.ndarray, np.ndarray]:
    a = cell.rgba
    if side == N:
        return a[0], a[1]
    if side == S:
        return a[-1], a[-2]
    if side == W:
        return a[:, 0], a[:, 1]
    return a[:, -1], a[:, -2]


def _facts(cell: Cell, side: int) -> tuple[np.ndarray, np.ndarray, float, float, bool]:
    """One edge of a cell, measured once: its colours (0..1) and painted mask, the cell's grain
    there (how much the edge differs from the line next to it), how much the edge differs
    from the line through the middle of the cell, and whether the two are painted apart."""
    key = ("side", side)
    found = cell.memo.get(key)
    if found is not None:
        return found  # type: ignore[no-any-return]
    line, inner = _lines(cell, side)
    edge = line[:, :3].astype(np.float32) / 255.0
    mask = line[:, 3] >= ALPHA
    both = mask & (inner[:, 3] >= ALPHA)
    grain = (
        float((np.abs(edge - inner[:, :3].astype(np.float32) / 255.0)[both]).mean())
        if both.any()
        else 0.0
    )
    a = cell.rgba
    middle = a[a.shape[0] // 2] if side in (N, S) else a[:, a.shape[1] // 2]
    mid_mask = middle[:, 3] >= ALPHA
    apart = bool(mask.sum()) and float((mask == mid_mask).mean()) < ALPHA_AGREE
    both_mid = mask & mid_mask
    border = (
        float((np.abs(edge - middle[:, :3].astype(np.float32) / 255.0)[both_mid]).mean())
        if both_mid.sum() >= 2
        else 0.0
    )
    found = (edge, mask, grain, border, apart)
    cell.memo[key] = found
    return found


def _edge(cell: Cell, side: int) -> tuple[np.ndarray, np.ndarray]:
    """The pixels of one edge (RGB floats 0..1) and their painted mask."""
    facts = _facts(cell, side)
    return facts[0], facts[1]


def _bordered(cell: Cell, side: int, tol: float) -> bool:
    """True when the edge is a line of its own (an outline round a block): it differs from the
    line through the middle of the cell more than a seam may. A surface piece has the same
    layers at its side as in its middle (the sky, the grass, the earth); an outlined block
    has its outline all along its side, and two of them side by side meet in a double line."""
    facts = _facts(cell, side)
    return facts[4] or facts[3] > tol


def _noise(cell: Cell, side: int) -> float:
    """How much the pixels near an edge differ from the line next to them: the cell's own
    grain there, which a seam may have too."""
    return _facts(cell, side)[2]


OPPOSITE = {N: S, S: N, E: W, W: E}


def fits(a: Cell, side: int, b: Cell) -> bool:
    """True when ``b`` laid on the ``side`` of ``a`` goes on without a seam: the two edges that
    meet are painted alike and of a colour within the cells' own noise."""
    ea, ma, ga, _ba, _pa = _facts(a, side)
    eb, mb, gb, _bb, _pb = _facts(b, OPPOSITE[side])
    agree = float((ma == mb).mean())
    if agree < ALPHA_AGREE:
        return False
    both = ma & mb
    if both.sum() < max(2, int(0.5 * max(ma.sum(), mb.sum()))):
        return False
    diff = float(np.abs(ea[both] - eb[both]).mean())
    tol = SEAM_TOL + SEAM_NOISE * min(ga, gb)
    if diff > tol:
        return False
    return not _bordered(a, side, tol) and not _bordered(b, OPPOSITE[side], tol)


def _repeats(cell: Cell, side: int) -> bool:
    return fits(cell, side, cell)


# --------------------------------------------------------------------------- one cell


def _rows_cover(cell: Cell) -> np.ndarray:
    return np.asarray(cell.alpha.mean(axis=1), dtype=np.float32)


def _cols_cover(cell: Cell) -> np.ndarray:
    return np.asarray(cell.alpha.mean(axis=0), dtype=np.float32)


def _hsv(cell: Cell) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Hue (degrees), saturation and value (0..1) of the painted pixels."""
    rgb = cell.rgba[:, :, :3][cell.alpha].astype(np.float32) / 255.0
    if rgb.size == 0:
        z = np.zeros(0, np.float32)
        return z, z, z
    mx = rgb.max(axis=1)
    mn = rgb.min(axis=1)
    d = mx - mn
    sat = np.where(mx > 0, d / np.maximum(mx, 1e-6), 0.0)
    r, g, b = rgb[:, 0], rgb[:, 1], rgb[:, 2]
    safe = np.maximum(d, 1e-6)
    hue = np.where(
        mx == r, (g - b) / safe % 6, np.where(mx == g, (b - r) / safe + 2, (r - g) / safe + 4)
    )
    return (hue * 60.0) % 360.0, sat, mx


def is_one_way(cell: Cell) -> bool:
    """Painted across its whole width in its upper part, empty in its lower part, tiling
    sideways: a plank to jump through."""
    rows = _rows_cover(cell)
    h = len(rows)
    lower = rows[int(h * 0.6) :]
    if lower.size == 0 or float(lower.mean()) > EMPTY:
        return False
    top = rows[: max(1, int(h * 0.5))]
    if float(top.max()) < 0.97 or float(top[: max(1, h // 4)].max()) < 0.97:
        return False
    return _repeats(cell, E)


def is_ladder(cell: Cell) -> bool:
    """Two rails from top to bottom with rungs between, tiling upwards."""
    if not (0.12 <= cell.cover <= 0.8):
        return False
    cols = _cols_cover(cell)
    w = len(cols)
    rails = cols >= 0.95
    runs: list[tuple[int, int]] = []
    x = 0
    while x < w:
        if rails[x]:
            start = x
            while x < w and rails[x]:
                x += 1
            runs.append((start, x - 1))
        else:
            x += 1
    if len(runs) != 2 or runs[1][0] - runs[0][1] < w // 4:
        return False
    between = cell.alpha[:, runs[0][1] + 1 : runs[1][0]]
    if between.size == 0:
        return False
    rung_rows = between.mean(axis=1)
    if float(rung_rows.max()) < 0.9 or float(rung_rows.min()) > 0.2:
        return False
    return _repeats(cell, S)


def is_spikes(cell: Cell) -> bool:
    """Painted only in the lower part, on a base, two teeth or more, grey or white."""
    rows = _rows_cover(cell)
    h = len(rows)
    if float(rows[: int(h * 0.3)].mean()) > EMPTY or float(rows[-1]) < 0.5:
        return False
    cols = cell.alpha.shape[1]
    tops = np.full(cols, h, dtype=np.int32)
    for x in range(cols):
        ys = np.nonzero(cell.alpha[:, x])[0]
        if ys.size:
            tops[x] = int(ys[0])
    painted = tops < h
    if painted.mean() < 0.7:
        return False
    # a tooth: a run of columns whose top rises above the middle between the highest tip and
    # the lowest top; two runs at least, and the tips a sixth of the cell above the base
    tip, base = int(tops[painted].min()), int(tops[painted].max())
    if base - tip < max(2, h // 6):
        return False
    level = (tip + base) / 2.0
    above = painted & (tops <= level)
    teeth = int(np.count_nonzero(above[1:] & ~above[:-1])) + int(above[0])
    if teeth < 2:
        return False
    _hue, sat, val = _hsv(cell)
    return bool(sat.size) and float(np.median(sat)) < 0.35 and float(np.median(val)) > 0.3


def is_water(cell: Cell) -> bool:
    """Blue, mostly painted, tiling sideways."""
    if cell.cover < 0.6:
        return False
    hue, sat, _val = _hsv(cell)
    if not hue.size:
        return False
    blue = (hue >= 180) & (hue <= 240) & (sat >= 0.3)
    return float(blue.mean()) >= 0.6 and _repeats(cell, E)


def is_coin(cell: Cell) -> bool:
    """A small gold shape alone in the middle of the cell, round or seen edge-on."""
    ys, xs = np.nonzero(cell.alpha)
    if ys.size == 0:
        return False
    h, w = cell.alpha.shape
    y0, y1, x0, x1 = int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())
    if y0 == 0 or x0 == 0 or y1 == h - 1 or x1 == w - 1:
        return False
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    if not (0.25 * h <= bh <= 0.8 * h) or not (0.3 <= bw / bh <= 1.25):
        return False
    if ys.size / (bw * bh) < 0.55:
        return False
    hue, sat, val = _hsv(cell)
    gold = (hue >= 30) & (hue <= 60) & (sat >= 0.4) & (val >= 0.55)
    return float(gold.mean()) >= 0.45


def is_fill(cell: Cell) -> bool:
    return cell.cover >= OPAQUE and _repeats(cell, E) and _repeats(cell, S)


def kind_of(cell: Cell) -> str | None:
    """The kind of one cell by its own picture, or None."""
    if cell.cover < EMPTY:
        return None
    if is_water(cell):
        return WATER
    if is_fill(cell):
        return FILL
    for kind, test in (
        (ONE_WAY, is_one_way),
        (LADDER, is_ladder),
        (SPIKES, is_spikes),
        (COIN, is_coin),
    ):
        if test(cell):
            return kind
    return None


# --------------------------------------------------------------------------- terrains


def _top_band(cell: Cell) -> np.ndarray:
    """The colour of a surface piece's surface: the mean of its upper rows (a third of the
    cell) without the dark ones (an outline above the grass is not the grass)."""
    h = cell.rgba.shape[0]
    band = cell.rgba[: max(1, h // 3)].reshape(-1, 4)
    painted = band[band[:, 3] >= ALPHA][:, :3].astype(np.float32) / 255.0
    light = painted[painted.max(axis=1) >= 0.35] if painted.size else painted
    if not light.size:
        return np.zeros(3, np.float32)
    return np.asarray(light.mean(axis=0))


def surface_of(colour: np.ndarray) -> str:
    """grass, snow, sand, stone, dirt, by the colour of a surface."""
    r, g, b = (float(v) for v in colour)
    mx, mn = max(r, g, b), min(r, g, b)
    sat = (mx - mn) / mx if mx > 0 else 0.0
    if mn > 0.75 and sat < 0.15:
        return "snow"
    if sat < 0.18:
        return "stone"
    if g >= r and g >= b:
        return "grass"
    if b > r and b > g:
        return "ice"
    if r > 0.6 and g > 0.5 and b < 0.55 and r - b > 0.25 and g > 0.75 * r:
        return "sand"
    return "dirt"


# a sheet gives this many terrains at most, from this many fills tried, each compared with this
# many of the fills alike to it
MAX_TERRAINS = 6
MAX_SEEDS = 16
MAX_ALIKE = 4
# a piece of a terrain is painted for this share at least in colours of its fill
SHARED_PALETTE = 0.65
# a piece of ground is painted nearly all over (a door or a sign in front of earth is not)
PIECE_COVER = 0.85
COLOUR_NEAR = 0.1


def _palette_share(cell: Cell, fill: Cell) -> float:
    """The share of a cell's painted pixels whose colour is within ``COLOUR_NEAR`` of one of
    the fill's colours."""
    colours = fill.memo.get("palette")
    if colours is None:
        colours = np.unique(fill.rgba[:, :, :3][fill.alpha].reshape(-1, 3), axis=0)[:256]
        fill.memo["palette"] = colours
    px = cell.rgba[:, :, :3][cell.alpha].reshape(-1, 3).astype(np.float32) / 255.0
    if not len(px) or not len(colours):
        return 0.0
    near = np.abs(px[:, None, :] - colours[None, :, :].astype(np.float32) / 255.0).max(axis=2)
    return float((near.min(axis=1) <= COLOUR_NEAR).mean())


def terrains(cells: list[Cell], fills: list[Cell]) -> list[tuple[str, dict[str, int]]]:
    """The side-view terrains of a sheet: for every fill (the first of alike ones), the cells
    whose sides join it, by the peering mask of each. A terrain needs a surface piece (a cell
    whose top is the sky and whose bottom joins the fill)."""
    out: list[tuple[str, dict[str, int]]] = []
    taken: set[str] = set()
    tried = 0
    for fill in fills:
        if fill.key in taken:
            continue
        if len(out) >= MAX_TERRAINS or tried >= MAX_SEEDS:
            break
        tried += 1
        same = [f for f in fills if f.key not in taken and fits(fill, E, f) and fits(fill, S, f)]
        members: dict[str, int] = {f.key: ALL for f in [fill, *same]}
        taken.update(members)
        alike = [fill, *same][:MAX_ALIKE]
        # first pass: the sides that join the fill itself
        joins: dict[str, int] = {}
        for c in cells:
            if c.key in members or c.key in taken or c.cover < PIECE_COVER:
                continue
            bits = 0
            for side in (N, E, S, W):
                if _edge(c, side)[1].mean() < EDGE_FULL:
                    continue  # ground goes on across a whole side, not across a rail's foot
                if any(fits(c, side, f) for f in alike):
                    bits |= side
            if bits and _palette_share(c, alike[0]) < SHARED_PALETTE:
                continue  # a door of wood beside earth of the same brown: another thing
            if bits:
                joins[c.key] = bits
        by_key = {c.key: c for c in cells}
        # second pass: a surface piece joins the pieces of its surface beside it
        surfaces = [by_key[k] for k, b in joins.items() if b & S and not b & N]
        if not surfaces:
            continue
        for k, bits in list(joins.items()):
            c = by_key[k]
            for side in (E, W):
                if bits & side:
                    continue
                level = bits & (N | S)
                if any(fits(c, side, o) for o in surfaces if (joins[o.key] & (N | S)) == level):
                    bits |= side
            joins[k] = bits
        for k, bits in joins.items():
            if bits == ALL:
                continue  # a fill that is not quite one: left out
            members[k] = bits
            taken.add(k)
        top = next((by_key[k] for k, b in joins.items() if b == E | S | W), surfaces[0])
        out.append((surface_of(_top_band(top)), members))
    return out


def read(rgba: np.ndarray, cell: tuple[int, int], margin: tuple[int, int] = (0, 0),
         sep: tuple[int, int] = (0, 0)) -> SheetRead:  # fmt: skip
    """The kinds of the cells of a sheet and its side-view terrains."""
    result = SheetRead()
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        return result
    cells = cells_of(rgba, cell[0], cell[1], margin, sep)
    fills: list[Cell] = []
    for c in cells:
        if c.cover < EMPTY:
            continue
        result.painted += 1
        kind = kind_of(c)
        if kind == FILL:
            fills.append(c)
        elif kind is not None:
            result.kinds[c.key] = kind
    result.terrains = terrains([c for c in cells if c.key not in result.kinds], fills)
    in_terrain = {k for _s, members in result.terrains for k in members}
    for c in cells:
        if c.cover >= EMPTY and c.key not in result.kinds and c.key not in in_terrain:
            result.unread += 1
    return result


def overrides(read_: SheetRead, set_names: list[str]) -> dict[str, dict[str, Any]]:
    """``tile_overrides`` of a read sheet: each terrain cell's peering in its set, each other
    kind's collision and custom data."""
    from rpggen.core.terrain import blocks, tiled_wang

    out: dict[str, dict[str, Any]] = {}
    for (_surface, members), name in zip(read_.terrains, set_names, strict=True):
        for key, bits in members.items():
            peering = tiled_wang.empty_peering()
            for side_key, bit in blocks.SIDE_KEYS:
                if bits & bit:
                    peering[side_key] = 0
            out[key] = {"terrain": {"set": name, "terrain": 0, "peering": peering},
                        "custom": {"side": "ground"}}  # fmt: skip
    for key, kind in read_.kinds.items():
        if kind == ONE_WAY:
            out[key] = {"collision": {"profile": "ONE_WAY"}, "custom": {"side": kind}}
        elif kind == LADDER:
            out[key] = {
                "collision": {"profile": "LADDER"},
                "custom": {"ladder": True},
            }
        elif kind == SPIKES:
            out[key] = {"collision": {"profile": "NONE"}, "custom": {"hazard": True}}
        else:  # water and coins are no ground to stand on
            out[key] = {"collision": {"profile": "NONE"}, "custom": {"side": kind}}
    return out
