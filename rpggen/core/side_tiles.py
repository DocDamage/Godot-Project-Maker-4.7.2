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
DOOR = "door"
KEY = "key"
FLAG = "flag"
SLOPE_UP = "slope_up"
SLOPE_DOWN = "slope_down"
KINDS = (FILL, ONE_WAY, LADDER, SPIKES, WATER, COIN, DOOR, KEY, FLAG, SLOPE_UP, SLOPE_DOWN)


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
    # cells of a terrain laid only where nothing else fits (a second surface on the same earth)
    alternates: set[str] = field(default_factory=set)
    cell: tuple[int, int] = (0, 0)
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
    if border > 0.0:
        # an outline is a line of its own all along the side: the edge differs from every line
        # a little way in too. A surface piece's bottom row of earth is the earth above it,
        # though its middle row may still be the grass (T17.33: Kenney's grass tops)
        border = min(border, _near_border(cell, side, edge, mask))
    found = (edge, mask, grain, border, apart)
    cell.memo[key] = found
    return found


def _near_border(cell: Cell, side: int, edge: np.ndarray, mask: np.ndarray) -> float:
    """How little the edge differs from the lines 2 to a quarter of the cell in from it (an
    outline of 1 or 2 px differs from all of them)."""
    a = cell.rgba
    size = a.shape[0] if side in (N, S) else a.shape[1]
    best = 1.0
    for k in range(2, max(3, size // 4 + 1)):
        if side == N:
            line = a[k]
        elif side == S:
            line = a[-1 - k]
        elif side == W:
            line = a[:, k]
        else:
            line = a[:, -1 - k]
        both = mask & (line[:, 3] >= ALPHA)
        if both.sum() < 2:
            continue
        diff = float((np.abs(edge - line[:, :3].astype(np.float32) / 255.0)[both]).mean())
        best = min(best, diff)
    return best


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
    if cell.cover < 0.12:
        return False
    cols = _cols_cover(cell)
    if cell.cover > 0.8:
        spans = _runs(cols >= 0.95)
        if len(spans) == 1 and spans[0][1] - spans[0][0] + 1 >= len(cols) // 2:
            return _ladder_on_backdrop(cell, spans[0])
        return False
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
    if len(runs) == 1 and runs[0][1] - runs[0][0] + 1 >= w // 2:
        return _ladder_on_backdrop(cell, runs[0])
    if len(runs) != 2 or runs[1][0] - runs[0][1] < w // 4:
        return False
    between = cell.alpha[:, runs[0][1] + 1 : runs[1][0]]
    if between.size == 0:
        return False
    rung_rows = between.mean(axis=1)
    if float(rung_rows.max()) < 0.9 or float(rung_rows.min()) > 0.2:
        return False
    return _repeats(cell, S)


# a rung differs from the backdrop between the rails by this much of value (0..1) at least
RUNG_CONTRAST = 0.2


def _runs(flags: np.ndarray) -> list[tuple[int, int]]:
    """The runs of True in a row of flags, as (first, last)."""
    out: list[tuple[int, int]] = []
    i, n = 0, len(flags)
    while i < n:
        if flags[i]:
            j = i
            while j < n and flags[j]:
                j += 1
            out.append((i, j - 1))
            i = j
        else:
            i += 1
    return out


def _ladder_on_backdrop(cell: Cell, span: tuple[int, int]) -> bool:
    """A ladder drawn over a backdrop (T17.33, Kenney's pixel platformer): its columns are
    painted from top to bottom between see-through margins, the outer columns (the rails) keep
    one value down the cell, and between them rows of another value (the rungs) cross the
    backdrop twice or more; it tiles upwards."""
    x0, x1 = span
    width = x1 - x0 + 1
    rail = max(1, width // 6)
    rgb = cell.rgba[:, :, :3].astype(np.float32) / 255.0
    value = rgb.max(axis=2)
    inner = value[:, x0 + rail + 1 : x1 - rail]
    if inner.shape[1] < 2:
        return False
    rows = inner.mean(axis=1)
    lo, hi = float(rows.min()), float(rows.max())
    if hi - lo < RUNG_CONTRAST:
        return False
    # the rows are of two kinds, rungs and the backdrop between them; a rung crosses the whole
    # backdrop (its row is of one value from rail to rail), and each kind comes twice or more
    even = inner.std(axis=1) <= 0.5 * RUNG_CONTRAST
    if float(even.mean()) < 0.8:
        return False  # a window, a handle, panels: no ladder
    light = rows >= (lo + hi) / 2.0
    inside = 0
    for kind in (light, ~light):
        runs = [r for r in _runs(kind) if r[1] - r[0] + 1 <= len(rows) // 3]
        if len(runs) < 2:
            return False
        inside += sum(1 for r in runs if r[0] > 0 and r[1] < len(rows) - 1)
    if inside < 3:
        return False  # a frame round a pane (its bars at the cell's edges): no rungs
    rails = np.concatenate([value[:, x0 : x0 + rail], value[:, x1 - rail + 1 : x1 + 1]], axis=1)
    rail_rows = rails.mean(axis=1)
    if float(rail_rows.std()) >= 0.5 * float(rows.std()):
        return False  # the sides change down the cell as the middle does (bricks): no rails
    # it tiles upwards: its top row is its bottom row again (the rungs make every line near an
    # edge differ from it, so the seam is compared as it is)
    return _rows_meet(cell, cell)


def _rows_meet(upper: Cell, lower: Cell) -> bool:
    """True when ``upper``'s bottom row is ``lower``'s top row again: painted alike, of colours
    within a seam's difference."""
    a = upper.rgba[-1].astype(np.float32) / 255.0
    b = lower.rgba[0].astype(np.float32) / 255.0
    pa, pb = a[:, 3] >= ALPHA / 255.0, b[:, 3] >= ALPHA / 255.0
    if float((pa == pb).mean()) < ALPHA_AGREE or not (pa & pb).any():
        return False
    return float(np.abs(a[:, :3] - b[:, :3])[pa & pb].mean()) <= SEAM_TOL


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


def _gold_share(cell: Cell) -> float:
    hue, sat, val = _hsv(cell)
    if not hue.size:
        return 0.0
    return float(((hue >= 25) & (hue <= 65) & (sat >= 0.35) & (val >= 0.5)).mean())


def _enclosed(inside: np.ndarray) -> np.ndarray:
    """The pixels of ``inside`` (a mask) that no path of ``inside`` pixels joins to the border."""
    h, w = inside.shape
    seen = np.zeros_like(inside)
    stack = [(y, x) for y in range(h) for x in (0, w - 1) if inside[y, x]]
    stack += [(y, x) for x in range(w) for y in (0, h - 1) if inside[y, x]]
    while stack:
        y, x = stack.pop()
        if seen[y, x]:
            continue
        seen[y, x] = True
        for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if 0 <= ny < h and 0 <= nx < w and inside[ny, nx] and not seen[ny, nx]:
                stack.append((ny, nx))
    return np.asarray(inside & ~seen)


def is_key(cell: Cell) -> bool:
    """A key (T17.33): a gold shape alone in the cell, long one way, whose bow at one end rings
    a hole (see-through or painted dark)."""
    if not (0.08 <= cell.cover <= 0.6) or _gold_share(cell) < 0.3:
        return False
    ys, xs = np.nonzero(cell.alpha)
    y0, y1, x0, x1 = int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())
    bh, bw = y1 - y0 + 1, x1 - x0 + 1
    if not (bw >= 1.4 * bh or bh >= 1.4 * bw):
        return False
    rgb = cell.rgba[y0 : y1 + 1, x0 : x1 + 1, :3].astype(np.float32) / 255.0
    mx, mn = rgb.max(axis=2), rgb.min(axis=2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    hue_ok = (rgb[:, :, 0] >= rgb[:, :, 2] + 0.2) & (rgb[:, :, 1] >= 0.5 * rgb[:, :, 0])
    gold = cell.alpha[y0 : y1 + 1, x0 : x1 + 1] & hue_ok & (sat >= 0.35) & (mx >= 0.5)
    holes = _enclosed(~gold)
    if not holes.any():
        return False
    hy, hx = np.nonzero(holes)
    along = hx if bw >= bh else hy
    length = bw if bw >= bh else bh
    middle = float(along.mean()) / length
    return middle <= 0.4 or middle >= 0.6  # the hole is in the bow, at one end


def _pole(cell: Cell) -> tuple[int, int] | None:
    """The columns of a thin pole from the top of the cell down most of it, or None."""
    cols = _cols_cover(cell)
    w = len(cols)
    for start, end in _runs(cols >= 0.9):
        if end - start + 1 <= max(1, w // 3) and float(cell.alpha[0, start : end + 1].max()):
            return start, end
    return None


def is_flag(cell: Cell) -> bool:
    """A flag (T17.33): a thin pole from the top of the cell down, and a cloth of a strong colour
    beside it hanging from its top part, nothing beside the pole below the cloth."""
    if not (0.1 <= cell.cover <= 0.85):
        return False
    pole = _pole(cell)
    if pole is None:
        return False
    h, w = cell.alpha.shape
    cloth = cell.alpha.copy()
    cloth[:, pole[0] : pole[1] + 1] = False
    if float(cloth.mean()) < 0.12:
        return False
    ys, xs = np.nonzero(cloth)
    if int(ys.max()) > 0.85 * h:
        return False  # something stands beside the pole at its foot: a lamp, a sign
    near = xs.min() <= pole[1] + 2 if xs.min() > pole[1] else xs.max() >= pole[0] - 2
    if not near:
        return False
    rgb = cell.rgba[:, :, :3][cloth].astype(np.float32) / 255.0
    mx, mn = rgb.max(axis=1), rgb.min(axis=1)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    return float((sat >= 0.45).mean()) >= 0.5


def _just_a_pole(cell: Cell) -> bool:
    """A cell of nothing but a thin pole from top to bottom (the foot of a flag)."""
    pole = _pole(cell)
    if pole is None:
        return False
    rest = cell.alpha.copy()
    rest[:, pole[0] : pole[1] + 1] = False
    return (
        float(rest.mean()) <= EMPTY
        and float(_cols_cover(cell)[pole[0] : pole[1] + 1].max()) >= 0.95
    )


def _door_box(stack: list[Cell]) -> bool:
    """A door (T17.33): an upright block one to three cells high (``stack``, top first)
    standing on the bottom of the last, its top in the open inside the first, painted over its
    whole box, half a cell wide or more; never blue (a pipe), not one picture repeated upwards
    (a pillar, a trunk)."""
    h, w = stack[-1].alpha.shape
    alpha = np.concatenate([c.alpha for c in stack], axis=0)
    rgba = np.concatenate([c.rgba for c in stack], axis=0)
    ys, xs = np.nonzero(alpha)
    if ys.size == 0:
        return False
    y0, y1, x0, x1 = int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())
    bh, bw = y1 - y0 + 1, x1 - x0 + 1
    if y1 != alpha.shape[0] - 1 or y0 < 1 or y0 >= h:
        return False
    if len(stack) == 1 and y0 > 0.15 * h:
        return False
    if bw < 0.45 * w or bh < 1.4 * bw:
        return False
    box = alpha[y0 : y1 + 1, x0 : x1 + 1]
    if float(box.mean()) < 0.85 or float(alpha.sum()) > 1.05 * float(box.sum()):
        return False
    if float(alpha[-1, x0 : x1 + 1].mean()) < 0.9:
        return False
    if any(not _rows_meet(a, b) for a, b in zip(stack, stack[1:], strict=False)):
        return False  # two things one over the other, not one door across cells
    # its sides are straight below its top (which may be round): every row of its lower three
    # quarters is painted across (two things stacked narrow where they meet: hay bales)
    lower = box[int(0.25 * bh) :]
    if float(lower.mean(axis=1).min()) < 0.9:
        return False
    rgb = rgba[:, :, :3][alpha].astype(np.float32) / 255.0
    mx, mn = rgb.max(axis=1), rgb.min(axis=1)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    blue = (rgb[:, 2] >= rgb[:, 0] + 0.1) & (rgb[:, 2] >= rgb[:, 1]) & (sat >= 0.3)
    if float(blue.mean()) >= 0.3:
        return False
    # a door is of one material inside its frame, broken by panels, a window or a handle: its
    # rows are not all one colour (a plain pillar) and not striped all over (bricks)
    value = mx.reshape(-1)
    return float(value.std()) >= 0.04


def slope_of(alpha: np.ndarray) -> str | None:
    """``up`` (rising to the right, ``/``) or ``down`` (``\\``) when a picture's painted part is
    the ground under a slope (T17.33): in every column it is painted from a top that runs in a
    straight line from near one bottom corner to near the other top corner, down to the bottom;
    None otherwise."""
    h, w = alpha.shape
    if h < 4 or w < 4:
        return None
    tops = np.full(w, h, dtype=np.float32)
    for x in range(w):
        ys = np.nonzero(alpha[:, x])[0]
        if ys.size:
            tops[x] = float(ys[0])
            if float(alpha[int(ys[0]) :, x].mean()) < 0.9:
                return None  # not ground down to the bottom under its top
    xs = np.arange(w, dtype=np.float32)
    painted = tops < h
    if painted.mean() < 0.8:
        return None
    slope, cut = np.polyfit(xs[painted], tops[painted], 1)
    rise = -float(slope) * w  # how far the top rises across the cell, in px
    if abs(rise) < 0.6 * h:
        return None
    resid = np.abs(tops[painted] - (slope * xs[painted] + cut))
    if float(resid.mean()) > 0.08 * h:
        return None
    low = max(float(tops[painted][0]), float(tops[painted][-1]))
    if low < 0.6 * h:
        return None  # the lower end of the slope stands near the cell's bottom
    return "up" if rise > 0 else "down"


def corner_under(rgba: np.ndarray) -> str | None:
    """Which slope a piece of earth goes under (T17.33, Kenney's ``grassCorner_left``): the
    surface goes on in one of its top corners, of another colour than its middle; ``up`` when
    that corner is the left one (it lies under the foot of a ``/``), ``down`` for the right."""
    if rgba.ndim != 3 or rgba.shape[2] != 4 or float((rgba[:, :, 3] >= ALPHA).mean()) < OPAQUE:
        return None
    h, w = rgba.shape[:2]
    q = max(1, min(h, w) // 4)
    rgb = rgba[:, :, :3].astype(np.float32) / 255.0
    middle = rgb[h // 3 : 2 * h // 3, w // 3 : 2 * w // 3].reshape(-1, 3).mean(axis=0)
    left = float(np.abs(rgb[:q, :q].reshape(-1, 3).mean(axis=0) - middle).mean())
    right = float(np.abs(rgb[:q, w - q :].reshape(-1, 3).mean(axis=0) - middle).mean())
    if max(left, right) < 0.08 or abs(left - right) < 0.05:
        return None
    return "up" if left > right else "down"


def slope_collision(slope: str, w: int, h: int) -> dict[str, Any]:
    """The collision of a slope one tile wide and high: a triangle under its diagonal."""
    points = [[0, h], [w, 0], [w, h]] if slope == "up" else [[0, 0], [w, h], [0, h]]
    return {"profile": "CUSTOM", "polygon": points}


def is_fill(cell: Cell) -> bool:
    return cell.cover >= OPAQUE and _repeats(cell, E) and _repeats(cell, S)


def kind_of(cell: Cell) -> str | None:
    """The kind of one cell by its own picture, or None."""
    if cell.cover < EMPTY:
        return None
    if is_water(cell):
        return WATER
    if cell.cover >= OPAQUE and is_ladder(cell):
        return LADDER  # rails and rungs over a backdrop tile both ways like earth: first
    if is_fill(cell):
        return FILL
    for kind, test in (
        (ONE_WAY, is_one_way),
        (LADDER, is_ladder),
        (SPIKES, is_spikes),
        (COIN, is_coin),
        (KEY, is_key),
        (FLAG, is_flag),
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
SHARED_PALETTE = 0.3  # T17.33: a rock face round a dark inside shares little of its colours
# a piece of ground is painted nearly all over (a door or a sign in front of earth is not)
PIECE_COVER = 0.45  # T17.33: an edge piece is painted half over (its outside is the air)
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


def terrains(
    cells: list[Cell], fills: list[Cell], alternates: set[str] | None = None
) -> list[tuple[str, dict[str, int]]]:
    """The side-view terrains of a sheet: for every fill (the first of alike ones), the cells
    whose sides join it, by the peering mask of each. A terrain needs a surface piece (a cell
    whose top is the sky and whose bottom joins the fill)."""
    out: list[tuple[str, dict[str, int]]] = []
    taken: set[str] = set()
    alternates = alternates if alternates is not None else set()
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
        # T17.33: the face of a wall joins the faces of its wall above and below it
        # (*Gothicvania*'s cave walls: each piece meets the dark inside on one side only)
        faces = {k: b for k, b in joins.items() if (b & (E | W)) in (E, W)}
        for k, bits in list(faces.items()):
            c = by_key[k]
            for side in (N, S):
                if bits & side:
                    continue
                if any(
                    fits(c, side, by_key[o])
                    for o, ob in faces.items()
                    if o != k and (ob & (E | W)) == (bits & (E | W))
                ):
                    bits |= side
            joins[k] = bits
        # second pass: a surface piece joins the pieces of its surface beside it
        surfaces = [by_key[k] for k, b in joins.items() if b & S and not b & N]
        if not surfaces:
            continue
        for k, bits in list(joins.items()):
            c = by_key[k]
            if bits & N and (bits & (E | W)) in (E, W):
                continue  # a wall's face (above): no surface beside it
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
        # one earth under several surfaces (Kenney's grass, sand and snow tops on one dirt): the
        # surface of the first piece in the sheet's order is the terrain's, the pieces of the
        # others stay its members at probability 0 (read, never laid by chance among the first)
        surface_by: dict[str, str] = {}
        for k, bits in members.items():
            if bits != ALL and not bits & N:
                surface_by[k] = surface_of(_top_band(by_key[k]))
        order = sorted(surface_by, key=lambda k: (by_key[k].y, by_key[k].x))
        main = surface_by[order[0]] if order else ""
        top = next((by_key[k] for k, b in joins.items() if b == E | S | W), surfaces[0])
        if main:
            mains = [by_key[k] for k in order if surface_by[k] == main and members[k] == E | S | W]
            top = mains[0] if mains else by_key[order[0]]
            alternates.update(k for k, s in surface_by.items() if s != main)
        out.append((surface_of(_top_band(top)), members))
    return out


def _doors_and_poles(cells: list[Cell], kinds: dict[str, str]) -> None:
    """What takes two cells of a sheet (T17.33): a door a cell or two high, and the pole under a
    flag (its foot, the cells below the cloth)."""
    by_xy = {(c.x, c.y): c for c in cells}
    # the top of a ladder: its rails rise from the bottom of the cell above a ladder and go on
    # into it without a seam
    for c in sorted(cells, key=lambda c: (-c.y, c.x)):
        below = by_xy.get((c.x, c.y + 1))
        if c.key in kinds or c.cover < EMPTY or below is None or kinds.get(below.key) != LADDER:
            continue
        if float(_rows_cover(c)[-1]) >= 0.5 and _rows_meet(c, below):
            kinds[c.key] = LADDER
    for c in cells:
        if c.key in kinds or c.cover < EMPTY:
            continue
        for high in (3, 2, 1):
            stack = [by_xy.get((c.x, c.y - k)) for k in range(high - 1, -1, -1)]
            cells_ = [s for s in stack if s is not None and s.key not in kinds and s.cover >= EMPTY]
            if len(cells_) == high and _door_box(cells_):
                for s in cells_:
                    kinds[s.key] = DOOR
                break
    for c in sorted(cells, key=lambda c: (c.y, c.x)):
        if c.key in kinds or c.cover < EMPTY:
            continue
        above = by_xy.get((c.x, c.y - 1))
        if above is not None and kinds.get(above.key) == FLAG and _just_a_pole(c):
            kinds[c.key] = FLAG


def read(rgba: np.ndarray, cell: tuple[int, int], margin: tuple[int, int] = (0, 0),
         sep: tuple[int, int] = (0, 0)) -> SheetRead:  # fmt: skip
    """The kinds of the cells of a sheet and its side-view terrains."""
    result = SheetRead(cell=(int(cell[0]), int(cell[1])))
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
    _doors_and_poles(cells, result.kinds)
    result.terrains = terrains(
        [c for c in cells if c.key not in result.kinds], fills, result.alternates
    )
    in_terrain = {k for _s, members in result.terrains for k in members}
    # the sides of hills (T17.33): ground under a diagonal, of the colours of a fill
    for c in cells:
        if c.cover < EMPTY or c.key in result.kinds or c.key in in_terrain or not fills:
            continue
        slope = slope_of(c.alpha)
        if slope is not None and any(
            _palette_share(c, f) >= SHARED_PALETTE for f in fills[:MAX_ALIKE]
        ):
            result.kinds[c.key] = SLOPE_UP if slope == "up" else SLOPE_DOWN
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
            if key in read_.alternates:
                out[key]["probability"] = 0.0
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
        elif kind in (SLOPE_UP, SLOPE_DOWN):
            slope = "up" if kind == SLOPE_UP else "down"
            out[key] = {
                "collision": slope_collision(slope, read_.cell[0], read_.cell[1]),
                "custom": {"side": kind, "slope": slope},
            }
        else:  # water and coins are no ground to stand on
            out[key] = {"collision": {"profile": "NONE"}, "custom": {"side": kind}}
    return out
