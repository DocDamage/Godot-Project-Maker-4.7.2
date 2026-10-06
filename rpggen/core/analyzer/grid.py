from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

# All tunable constants of the algorithm live here (T2.05). Record any tuning in
# IMPLEMENTATION_NOTES.md.
GRID_CONSTANTS: dict[str, Any] = {
    "SIZES": [8, 12, 16, 24, 32, 48, 64, 96, 128],
    "MARGINS": [0, 1, 2],
    "SEPARATIONS": [0, 1, 2],
    "GUTTER_EMPTY_MIN": 0.98,  # mean empty ratio required on gutter and margin lines
    "REMAINDER_DIVISOR": 4,  # leftover pixels must be <= cell // 4
    "W_BOUNDARY": 0.55,
    "W_REMAINDER": 0.15,
    "W_SEPARATION": 0.15,
    "W_HALF": 0.15,
    "REMAINDER_PARTIAL": 0.5,
    "HALF_RATIO": 0.35,
    "MAX_MULTIPLE": 8,  # largest k tried by the half-boundary penalty (spec: 2)
    "W_SCORE": 0.60,
    "W_CELL": 0.20,
    "W_PRIOR": 0.12,
    "W_SIZE": 0.08,
    "NON_SQUARE_TOP": 3,  # candidates kept per axis when square=False
    "SQUARE_TOP_MS": 3,  # (margin, separation) options kept per axis per size when square=True
    "MAX_CANDIDATES": 5,
    "SIZE_TERM": {16: 1.0, 32: 1.0, 48: 0.9, 24: 0.7, 64: 0.7, 8: 0.5, 12: 0.4, 96: 0.4, 128: 0.4},
}


@dataclass(frozen=True)
class GridCandidate:
    cell: tuple[int, int]
    margin: tuple[int, int]
    separation: tuple[int, int]
    score: float  # 0..1
    nonempty_cells: int
    total_cells: int


@dataclass(frozen=True)
class _AxisCandidate:
    c: int
    m: int
    s: int
    n: int
    score: float


class _Axis:
    """Per-axis line statistics (lines are columns for axis "x" and rows for axis "y")."""

    def __init__(self, a: np.ndarray, mask: np.ndarray, axis: str) -> None:
        if axis == "x":
            arr, msk = a.transpose(1, 0, 2), mask.T
        else:
            arr, msk = a, mask
        self.length = arr.shape[0]
        self.empty = ~msk.any(axis=1)
        self.any_occupied = bool(msk.any())
        a16 = arr.astype(np.int16)
        diff = np.abs(a16[1:] - a16[:-1]).sum(axis=2)  # summed over the 4 channels
        either = msk[1:] | msk[:-1]
        # pair index j is the pair of lines (j, j + 1)
        self.pair_sum = (diff * either).sum(axis=1).astype(np.float64)
        self.pair_cnt = either.sum(axis=1).astype(np.float64) * 4.0

    def _mean(self, idx: np.ndarray) -> float:
        if len(idx) == 0:
            return 0.0
        cnt = self.pair_cnt[idx].sum()
        return float(self.pair_sum[idx].sum() / cnt) if cnt > 0 else 0.0

    def strength(self, boundaries: list[int], inside: np.ndarray) -> float:
        """clip((B - I) / (B + I + eps) * 2, 0, 1); boundaries are first lines of cells."""
        if not self.any_occupied or not boundaries:
            return 0.0
        b = self._mean(np.array([i - 1 for i in boundaries], dtype=np.int64))
        i_mean = self._mean(inside)
        return float(np.clip((b - i_mean) / (b + i_mean + 1e-6) * 2.0, 0.0, 1.0))


def _starts(n: int, c: int, m: int, s: int) -> list[int]:
    return [m + k * (c + s) for k in range(n)]


def _inside_pairs(starts: list[int], c: int) -> np.ndarray:
    idx: list[int] = []
    for st in starts:
        idx.extend(range(st, st + c - 1))  # pair (i, i+1) with both lines in the cell
    return np.array(idx, dtype=np.int64)


def _score_axis(ax: _Axis, c: int, m: int, s: int) -> _AxisCandidate | None:
    K = GRID_CONSTANTS
    length = ax.length
    if c > length:
        return None
    usable = length - 2 * m + s
    n = usable // (c + s)
    if n < 1:
        return None
    remainder = usable - n * (c + s)
    if remainder > c // K["REMAINDER_DIVISOR"]:
        return None
    starts = _starts(n, c, m, s)
    if s > 0 and n >= 2:
        gutters = [st + c + j for st in starts[:-1] for j in range(s)]
        if float(ax.empty[gutters].mean()) < K["GUTTER_EMPTY_MIN"]:
            return None
    if m > 0 and float(ax.empty[:m].mean()) < K["GUTTER_EMPTY_MIN"]:
        return None
    inside = _inside_pairs(starts, c)
    boundaries = starts[1:]
    boundary = ax.strength(boundaries, inside)
    half = 0.0
    if s == 0:
        # A grid of size c is suspect when a larger valid size k*c exists whose boundaries are the
        # strong ones: the boundaries c has in between (the "odd" ones for k = 2) are weak.
        # The spec only describes k = 2; k >= 2 is a tuning (see IMPLEMENTATION_NOTES.md).
        for k in range(2, K["MAX_MULTIPLE"] + 1):
            big = k * c
            if big not in K["SIZES"] or (length - 2 * m) // big < 1 or len(boundaries) < k:
                continue
            shared = [b for idx, b in enumerate(boundaries, start=1) if idx % k == 0]
            others = [b for idx, b in enumerate(boundaries, start=1) if idx % k != 0]
            weak = (
                shared
                and others
                and (ax.strength(others, inside) < K["HALF_RATIO"] * ax.strength(shared, inside))
            )
            if weak:
                half = 1.0
                break
    score = (
        K["W_BOUNDARY"] * boundary
        + K["W_REMAINDER"] * (1.0 if remainder == 0 else K["REMAINDER_PARTIAL"])
        + K["W_SEPARATION"] * (1.0 if s > 0 else 0.0)
        + K["W_HALF"] * (1.0 - half)
    )
    return _AxisCandidate(c, m, s, n, score)


def _axis_candidates(ax: _Axis) -> list[_AxisCandidate]:
    K = GRID_CONSTANTS
    out: list[_AxisCandidate] = []
    for c in K["SIZES"]:
        for m in K["MARGINS"]:
            for s in K["SEPARATIONS"]:
                cand = _score_axis(ax, c, m, s)
                if cand is not None:
                    out.append(cand)
    return out


def _sat(mask: np.ndarray) -> np.ndarray:
    sat = np.zeros((mask.shape[0] + 1, mask.shape[1] + 1), dtype=np.int64)
    sat[1:, 1:] = mask.astype(np.int64).cumsum(axis=0).cumsum(axis=1)
    return sat


def _cell_counts(sat: np.ndarray, xs: _AxisCandidate, ys: _AxisCandidate) -> np.ndarray:
    x0 = np.array(_starts(xs.n, xs.c, xs.m, xs.s))
    y0 = np.array(_starts(ys.n, ys.c, ys.m, ys.s))
    x1, y1 = x0 + xs.c, y0 + ys.c
    return sat[np.ix_(y1, x1)] - sat[np.ix_(y0, x1)] - sat[np.ix_(y1, x0)] + sat[np.ix_(y0, x0)]


def _size_term(c: int) -> float:
    return GRID_CONSTANTS["SIZE_TERM"].get(c, 0.4)


def _combine(
    sat: np.ndarray,
    xs: _AxisCandidate,
    ys: _AxisCandidate,
    pack_prior: dict[int, float] | None,
) -> GridCandidate:
    K = GRID_CONSTANTS
    counts = _cell_counts(sat, xs, ys)
    area = xs.c * ys.c
    total = int(counts.size)
    aligned = int(((counts == 0) | (counts == area)).sum())
    cell_term = aligned / total
    prior = 0.0
    if pack_prior:
        prior = max(pack_prior.get(xs.c, 0.0), pack_prior.get(ys.c, 0.0))
    size_term = (_size_term(xs.c) + _size_term(ys.c)) / 2.0
    final = (
        K["W_SCORE"] * (xs.score + ys.score) / 2.0
        + K["W_CELL"] * cell_term
        + K["W_PRIOR"] * prior
        + K["W_SIZE"] * size_term
    )
    return GridCandidate(
        cell=(xs.c, ys.c),
        margin=(xs.m, ys.m),
        separation=(xs.s, ys.s),
        score=round(float(final), 6),
        nonempty_cells=int((counts > 0).sum()),
        total_cells=total,
    )


def detect_grid(
    a: np.ndarray,
    mask: np.ndarray,
    *,
    square: bool = True,
    pack_prior: dict[int, float] | None = None,
) -> list[GridCandidate]:
    """Up to 5 grid candidates sorted by score descending (ties: larger cell first)."""
    K = GRID_CONSTANTS
    ax_x, ax_y = _Axis(a, mask, "x"), _Axis(a, mask, "y")
    cands_x, cands_y = _axis_candidates(ax_x), _axis_candidates(ax_y)
    sat = _sat(mask)
    pairs: list[tuple[_AxisCandidate, _AxisCandidate]] = []
    if square:
        for c in K["SIZES"]:
            top_x = sorted((x for x in cands_x if x.c == c), key=lambda x: -x.score)[
                : K["SQUARE_TOP_MS"]
            ]
            top_y = sorted((y for y in cands_y if y.c == c), key=lambda y: -y.score)[
                : K["SQUARE_TOP_MS"]
            ]
            pairs.extend((x, y) for x in top_x for y in top_y)
    else:
        top_x = sorted(cands_x, key=lambda x: -x.score)[: K["NON_SQUARE_TOP"]]
        top_y = sorted(cands_y, key=lambda y: -y.score)[: K["NON_SQUARE_TOP"]]
        pairs = [(x, y) for x in top_x for y in top_y]
    seen: set[tuple[tuple[int, int], tuple[int, int], tuple[int, int]]] = set()
    out: list[GridCandidate] = []
    for xs, ys in pairs:
        cand = _combine(sat, xs, ys, pack_prior)
        key = (cand.cell, cand.margin, cand.separation)
        if key in seen:
            continue
        seen.add(key)
        out.append(cand)
    out.sort(key=lambda g: (-g.score, -g.cell[0], -g.cell[1]))
    return out[: K["MAX_CANDIDATES"]]


def confidence(candidates: list[GridCandidate]) -> float:
    """Catalog confidence of the top candidate: score * min(1, 0.5 + (top - second) * 2)."""
    if not candidates:
        return 0.0
    top = candidates[0].score
    second = candidates[1].score if len(candidates) > 1 else 0.0
    return round(top * min(1.0, 0.5 + (top - second) * 2.0), 6)


@dataclass(frozen=True)
class GridReadout:
    cols: int
    rows: int
    nonempty: int
    remainder: tuple[int, int]  # pixels left over horizontally and vertically


def grid_readout(
    mask: np.ndarray,
    cell: tuple[int, int],
    margin: tuple[int, int],
    separation: tuple[int, int],
) -> GridReadout:
    """Size of the grid a (cell, margin, separation) triple makes on an image.

    The margin is applied on both sides of an axis; ``remainder`` is what is left over after the
    last whole cell (ASSET-003 when it is not zero).
    """
    h, w = mask.shape
    (cw, ch), (mx, my), (sx, sy) = cell, margin, separation
    if cw < 1 or ch < 1:
        return GridReadout(0, 0, 0, (w, h))
    usable_w = w - 2 * mx + sx
    usable_h = h - 2 * my + sy
    cols = max(0, usable_w // (cw + sx))
    rows = max(0, usable_h // (ch + sy))
    remainder = (max(0, usable_w - cols * (cw + sx)), max(0, usable_h - rows * (ch + sy)))
    if cols == 0 or rows == 0:
        return GridReadout(cols, rows, 0, remainder)
    xs = _AxisCandidate(cw, mx, sx, cols, 0.0)
    ys = _AxisCandidate(ch, my, sy, rows, 0.0)
    counts = _cell_counts(_sat(mask), xs, ys)
    return GridReadout(cols, rows, int((counts > 0).sum()), remainder)
