"""What the rows of a character's sheet do, read from their frames (T17.33).

pozak's characters (``Character 120x120.png``) and the sheets of the *Platformer & Beat 'Em Up
Pack* come without animation names: their Aseprite sources carry no tags and nothing beside them
lists the rows. This module names them from what the frames do, as one would by watching them:

* **The rows that are one animation.** Frames run left to right and wrap onto the next row when
  a row is full; an empty row or a row that is not full ends an animation, and so does a row
  whose first frame does not go on from the last frame of the row before (a new pose).
* **Standing, the ground and the figure's size** are measured once over the whole sheet: the
  ground is the line most frames stand on, the figure's height the median height of the frames
  that stand on it.
* **An animation's name**, the first rule that holds:
  ``death`` (it ends lying down, or fading away), ``jump`` / ``fall`` (most frames off the
  ground, rising or falling), ``attack`` (a frame reaches out far beyond the figure, or paints
  a slash of colours the figure has not), ``crouch`` (lower than standing and nearly still),
  ``idle`` (nearly still), ``hurt`` (a few frames that are no cycle), ``walk`` (a cycle of
  steps; the second one, with the longer stride, ``run``).

Integer and float arithmetic on the pixels only: the same sheet gives the same names everywhere.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

ALPHA = 64
# a frame is painted over this share of its cell at least
EMPTY = 0.002
# consecutive frames of a still animation overlap this much (intersection over union)
STILL = 0.8
# the first frame of a row goes on from the last frame of the row before at least this much
GOES_ON = 0.45
# off the ground: the feet this share of the figure's height above the ground line
AIR = 0.1
# reaching out: wider than the standing figure by this factor
REACH = 1.35
# a slash: this share of a frame's pixels of colours the figure is not drawn in
SLASH = 0.08
# lying down: no higher than this share of the figure's height
LYING = 0.55
# fading away: the last frame paints this share of the first at most
FADED = 0.35
CROUCH = 0.8


@dataclass(frozen=True)
class Frame:
    """One painted frame: its mask's box (x0, y0, x1, y1, inclusive), area and the cell."""

    col: int
    row: int
    mask: np.ndarray
    box: tuple[int, int, int, int]
    area: int
    colours: frozenset[int]
    pixels: np.ndarray

    @property
    def width(self) -> int:
        return self.box[2] - self.box[0] + 1

    @property
    def height(self) -> int:
        return self.box[3] - self.box[1] + 1

    @property
    def bottom(self) -> int:
        return self.box[3]


def _quantize(rgb: np.ndarray) -> np.ndarray:
    q = (rgb.astype(np.int32) >> 4).reshape(-1, 3)
    return np.asarray(q[:, 0] * 256 + q[:, 1] * 16 + q[:, 2])


def frames_of(rgba: np.ndarray, cw: int, ch: int) -> dict[tuple[int, int], Frame]:
    """The painted frames of a sheet cut in cells of ``cw`` x ``ch``, by (column, row)."""
    out: dict[tuple[int, int], Frame] = {}
    h, w = rgba.shape[:2]
    for row in range(h // ch):
        for col in range(w // cw):
            found = frame_of(rgba[row * ch : (row + 1) * ch, col * cw : (col + 1) * cw], col, row)
            if found is not None:
                out[(col, row)] = found
    return out


def frame_of(part: np.ndarray, col: int = 0, row: int = 0) -> Frame | None:
    """One frame's picture measured, or None when it is (nearly) empty."""
    ch, cw = part.shape[:2]
    mask = part[:, :, 3] >= ALPHA
    area = int(mask.sum())
    if area < max(4, EMPTY * cw * ch):
        return None
    ys, xs = np.nonzero(mask)
    box = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
    colours = frozenset(int(c) for c in np.unique(_quantize(part[:, :, :3][mask])))
    return Frame(col, row, mask, box, area, colours, part)


def runs(images: list[np.ndarray]) -> list[list[Frame]]:
    """The animations of numbered frames exported one by one with empty frames between the
    animations (T17.33: the *black knight*'s ``CHARACTER1..168``): the runs between them."""
    out: list[list[Frame]] = []
    current: list[Frame] = []
    for i, image in enumerate(images):
        found = frame_of(image, i, 0) if image.ndim == 3 and image.shape[2] == 4 else None
        if found is None:
            if current:
                out.append(current)
            current = []
        else:
            current.append(found)
    if current:
        out.append(current)
    return out


def _iou(a: Frame, b: Frame) -> float:
    inter = int((a.mask & b.mask).sum())
    union = int((a.mask | b.mask).sum())
    return inter / union if union else 0.0


def _alike(a: Frame, b: Frame) -> float:
    """How alike two poses are, wherever they stand in their cells: the overlap of the masks
    laid with their feet and middles on each other."""
    ax, bx = (a.box[0] + a.box[2]) // 2, (b.box[0] + b.box[2]) // 2
    dy, dx = a.bottom - b.bottom, ax - bx
    shifted = np.roll(np.roll(b.mask, dy, axis=0), dx, axis=1)
    inter = int((a.mask & shifted).sum())
    union = int((a.mask | shifted).sum())
    return inter / union if union else 0.0


def sequences(frames: dict[tuple[int, int], Frame], columns: int) -> list[list[Frame]]:
    """The animations of a sheet: runs of frames left to right, wrapping onto the next row when
    a row is full and the next row's first frame goes on from it."""
    rows: dict[int, list[Frame]] = {}
    for (_col, row), f in sorted(frames.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        rows.setdefault(row, []).append(f)
    out: list[list[Frame]] = []
    current: list[Frame] = []
    last_row = -2
    for row in sorted(rows):
        line = sorted(rows[row], key=lambda f: f.col)
        full_before = bool(current) and last_row == row - 1 and len(current) % columns == 0
        if full_before and current and _alike(current[-1], line[0]) >= GOES_ON:
            current.extend(line)
        else:
            if current:
                out.append(current)
            current = list(line)
        last_row = row
    if current:
        out.append(current)
    return out


@dataclass(frozen=True)
class Figure:
    """The standing figure of a sheet: the ground line, its height and width."""

    ground: int
    height: float
    width: float
    colours: frozenset[int]


def figure(seqs: list[list[Frame]]) -> Figure | None:
    every = [f for s in seqs for f in s]
    if not every:
        return None
    bottoms = np.array([f.bottom for f in every])
    values, counts = np.unique(bottoms, return_counts=True)
    ground = int(values[int(np.argmax(counts))])
    standing = [f for f in every if abs(f.bottom - ground) <= 1]
    height = float(np.median([f.height for f in standing]))
    width = float(np.median([f.width for f in standing]))
    # the figure's own colours: those of the stillest animation (the one most alike throughout)
    still = max(seqs, key=lambda s: (_stillness(s), -seqs.index(s)))
    colours: set[int] = set()
    for f in still:
        colours |= f.colours
    return Figure(ground, max(height, 1.0), max(width, 1.0), frozenset(colours))


def _stillness(seq: list[Frame]) -> float:
    if len(seq) < 2:
        return 0.0
    return float(np.mean([_iou(a, b) for a, b in zip(seq, seq[1:], strict=False)]))


def _new_colour_share(f: Frame, fig: Figure) -> float:
    q = _quantize(f.pixels[:, :, :3][f.mask])
    if q.size == 0 or not fig.colours:
        return 0.0
    known = np.isin(q, np.fromiter(fig.colours, dtype=np.int64))
    return float((~known).mean())


def name_of(seq: list[Frame], fig: Figure) -> str:
    """What one animation does (see the module's text)."""
    n = len(seq)
    heights = np.array([f.height for f in seq], dtype=np.float32) / fig.height
    widths = np.array([f.width for f in seq], dtype=np.float32) / fig.width
    lift = np.array([fig.ground - f.bottom for f in seq], dtype=np.float32) / fig.height
    still = _stillness(seq)
    first, last = seq[0], seq[-1]
    lying = (heights <= LYING) & (widths >= 1.1)
    if n >= 3 and bool(lying[0]) and not bool(lying[-1]) and heights[-1] >= 0.8:
        return "get_up"
    if n >= 4 and (
        bool(lying[-min(3, n) :].any())
        and not bool(lying[0])
        or (last.area <= FADED * first.area and heights[0] >= 0.8)
    ):
        return "death"
    air = lift >= AIR
    if float(air.mean()) >= 0.5:
        top = int(np.argmax(lift))
        return "fall" if top == 0 and lift[-1] < lift[0] else "jump"
    # a swing reaches out in some frames, not in all (a cape flying in a run is in every one),
    # and so does a slash of new colours
    reach = float(widths.max()) >= REACH and float(widths.max()) >= 1.25 * float(np.median(widths))
    shares = [_new_colour_share(f, fig) for f in seq] if n >= 2 else [0.0]
    slash = max(shares) >= SLASH and max(shares) >= 3.0 * float(np.median(shares))
    if reach or slash:
        return "attack"
    if float(np.median(heights)) <= CROUCH and still >= STILL * 0.9:
        return "crouch"
    if still >= STILL:
        return "idle"
    cyclic = n >= 4 and _alike(first, last) >= 0.5
    if not cyclic and n <= 4:
        return "hurt"
    if not cyclic and n < 6:
        return "action"  # a few frames that go somewhere and do not come back: no name fits
    return "walk"


def names(seqs: list[list[Frame]], fig: Figure) -> list[str]:
    """Names of every animation of a sheet, unique (a second attack is ``attack_2``); of two
    walks the one whose frames reach wider (the longer stride) is ``run``, and a sheet whose
    first animation is still has it ``idle`` before any other."""
    raw = [name_of(s, fig) for s in seqs]
    walks = [i for i, n in enumerate(raw) if n == "walk"]
    if len(walks) >= 2:
        stride = {i: float(np.mean([f.width for f in seqs[i]])) for i in walks}
        widest = max(walks, key=lambda i: (stride[i], -i))
        raw[widest] = "run"
    if "idle" not in raw:
        stillest = max(range(len(seqs)), key=lambda i: (_stillness(seqs[i]), -i))
        if raw[stillest] in ("walk", "hurt", "crouch"):
            raw[stillest] = "idle"
    seen: dict[str, int] = {}
    out = []
    for n in raw:
        seen[n] = seen.get(n, 0) + 1
        out.append(n if seen[n] == 1 else f"{n}_{seen[n]}")
    return out


def cell_of(rgba: np.ndarray, named: tuple[int, int]) -> tuple[int, int]:
    """The frame size of a sheet whose name gives one (pozak's ``Character 160x160.png`` drawn at
    half that, 80 px): the smallest of the named size and its halves, thirds and quarters
    (16 px or more, dividing the sheet) whose cut lines cross no figure."""
    h, w = rgba.shape[:2]
    alpha = rgba[:, :, 3] >= ALPHA
    cw, ch = named
    best = (cw, ch)
    for k in (2, 3, 4):
        if cw % k or ch % k:
            continue
        sw, sh = cw // k, ch // k
        if sw < 16 or sh < 16 or w % sw or h % sh:
            continue
        lines = [alpha[:, x] for x in range(0, w, sw)] + [alpha[y, :] for y in range(0, h, sh)]
        crossed = sum(int(line.sum()) for line in lines)
        total = sum(line.size for line in lines)
        if total and crossed / total <= 0.001:
            best = (sw, sh)
    return best
