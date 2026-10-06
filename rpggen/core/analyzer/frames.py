from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from rpggen.core.analyzer.grid import GridCandidate

FRAME_CONSTANTS = {
    "STRIP_MIN_FRAMES": 2,
    "STRIP_MAX_FRAMES": 32,
    "STRIP_MIN_NONEMPTY": 0.75,
    "STRIP_MAX_VARIATION": 0.4,  # bbox width/height may vary by at most 40% of the frame size
    "STRIP_CLEAN_BOUNDARIES": 0.5,  # fraction of frame boundaries that must not cut art
    "SHEET_MIN_COLS": 3,
    "SHEET_MAX_COLS": 12,
    "SHEET_MIN_FRAME": 8,
    "SHEET_MAX_FRAME": 256,
    "SHEET_CLEAN_BOUNDARIES": 0.8,
    "SHEET_MIN_ROW_FRAMES": 2,
    "MIRROR_DECISIVE": 0.05,  # best mirror IoU must beat the runner-up by this much
    "DIRECTION_CONFIDENCE": 0.5,
    "DEFAULT_DIRECTION_CONFIDENCE": 0.4,
}
DEFAULT_DIRECTIONS = ["down", "left", "right", "up"]  # RPG Maker row order


@dataclass(frozen=True)
class StripInfo:
    axis: Literal["x", "y"]
    frames: int
    frame: tuple[int, int]


@dataclass(frozen=True)
class SheetLayout:  # directional character sheet
    frame: tuple[int, int]
    cols: int
    rows: int
    row_directions: list[str] | None  # e.g. ["down", "left", "right", "up"] when inferable
    direction_confidence: float = 0.0


Rect = tuple[int, int, int, int]


# --------------------------------------------------------------------------- helpers


def frame_rects(frame: tuple[int, int], cols: int, rows: int) -> list[Rect]:
    """Row-major pixel rects of a regular frame grid without margins."""
    fw, fh = frame
    return [(c * fw, r * fh, fw, fh) for r in range(rows) for c in range(cols)]


def frame_bboxes(mask: np.ndarray, rects: list[Rect]) -> list[Rect | None]:
    """Per-frame bbox of occupied pixels, relative to the frame's top-left (None when empty)."""
    out: list[Rect | None] = []
    for x, y, w, h in rects:
        sub = mask[y : y + h, x : x + w]
        ys, xs = np.nonzero(sub)
        if len(xs) == 0:
            out.append(None)
        else:
            out.append(
                (
                    int(xs.min()),
                    int(ys.min()),
                    int(xs.max() - xs.min() + 1),
                    int(ys.max() - ys.min() + 1),
                )
            )
    return out


def baseline_y(mask: np.ndarray, rects: list[Rect]) -> int:
    """Median over non-empty frames of the lowest occupied row, relative to the frame top."""
    lows = [b[1] + b[3] - 1 for b in frame_bboxes(mask, rects) if b is not None]
    if not lows:
        return 0
    return int(np.median(lows))


def _line_empty(mask: np.ndarray, axis: str) -> np.ndarray:
    """Per column (axis "x") or per row (axis "y"): True when the line holds no occupied pixel."""
    return ~mask.any(axis=0) if axis == "x" else ~mask.any(axis=1)


def _clean_ratio(empty: np.ndarray, size: int, strict: bool) -> float:
    """Fraction of internal frame boundaries that do not cut through art.

    strict: both lines next to the boundary must be empty. Otherwise one empty line is enough
    (art may touch the bottom or right edge of a frame, as feet do).
    """
    boundaries = list(range(size, len(empty), size))
    if not boundaries:
        return 0.0
    ok = 0
    for b in boundaries:
        before, after = bool(empty[b - 1]), bool(empty[b])
        if (before and after) if strict else (before or after):
            ok += 1
    return ok / len(boundaries)


# --------------------------------------------------------------------------- strips


def detect_strip(mask: np.ndarray, grids: list[GridCandidate] | None = None) -> StripInfo | None:
    """A single-row (or single-column) animation strip, or None.

    Square frames: w % h == 0 with 2..32 frames (or the vertical equivalent). Non-square frames:
    every grid candidate with exactly one row or column. A strip is accepted when 75% of its
    frames hold art, the art sizes are consistent and the frame boundaries do not cut through art.
    """
    K = FRAME_CONSTANTS
    h, w = mask.shape
    candidates: list[tuple[Literal["x", "y"], int, tuple[int, int]]] = []
    if w % h == 0 and K["STRIP_MIN_FRAMES"] <= w // h <= K["STRIP_MAX_FRAMES"]:
        candidates.append(("x", w // h, (h, h)))
    if h % w == 0 and K["STRIP_MIN_FRAMES"] <= h // w <= K["STRIP_MAX_FRAMES"]:
        candidates.append(("y", h // w, (w, w)))
    for g in grids or []:
        fw, fh = g.cell
        if g.margin != (0, 0) or g.separation != (0, 0):
            continue
        cols, rows = w // fw, h // fh
        if rows == 1 and cols >= K["STRIP_MIN_FRAMES"] and w % fw == 0 and h == fh:
            candidates.append(("x", cols, (fw, fh)))
        elif cols == 1 and rows >= K["STRIP_MIN_FRAMES"] and h % fh == 0 and w == fw:
            candidates.append(("y", rows, (fw, fh)))
    for axis, count, frame in candidates:
        info = _check_strip(mask, axis, count, frame)
        if info is not None:
            return info
    return None


def _check_strip(
    mask: np.ndarray, axis: Literal["x", "y"], count: int, frame: tuple[int, int]
) -> StripInfo | None:
    K = FRAME_CONSTANTS
    fw, fh = frame
    rects = (
        [(i * fw, 0, fw, fh) for i in range(count)]
        if axis == "x"
        else [(0, i * fh, fw, fh) for i in range(count)]
    )
    boxes = [b for b in frame_bboxes(mask, rects) if b is not None]
    if len(boxes) / count < K["STRIP_MIN_NONEMPTY"]:
        return None
    widths, heights = [b[2] for b in boxes], [b[3] for b in boxes]
    if (max(widths) - min(widths)) > K["STRIP_MAX_VARIATION"] * fw:
        return None
    if (max(heights) - min(heights)) > K["STRIP_MAX_VARIATION"] * fh:
        return None
    empty = _line_empty(mask, "x" if axis == "x" else "y")
    size = fw if axis == "x" else fh
    if _clean_ratio(empty, size, strict=True) < K["STRIP_CLEAN_BOUNDARIES"]:
        return None
    return StripInfo(axis, count, frame)


# --------------------------------------------------------------------------- character sheets


def _candidate_sizes(length: int, lo: int, hi: int, count_ok) -> list[int]:
    return [s for s in range(lo, min(hi, length) + 1) if length % s == 0 and count_ok(length // s)]


def _find_frame(mask: np.ndarray) -> tuple[tuple[int, int], int, int] | None:
    """Smallest frame size whose boundaries do not cut art, with 3..12 columns and 4k rows."""
    K = FRAME_CONSTANTS
    h, w = mask.shape
    col_empty, row_empty = _line_empty(mask, "x"), _line_empty(mask, "y")
    widths = _candidate_sizes(
        w,
        K["SHEET_MIN_FRAME"],
        K["SHEET_MAX_FRAME"],
        lambda n: K["SHEET_MIN_COLS"] <= n <= K["SHEET_MAX_COLS"],
    )
    heights = _candidate_sizes(
        h, K["SHEET_MIN_FRAME"], K["SHEET_MAX_FRAME"], lambda n: n >= 4 and n % 4 == 0
    )
    fw = next(
        (s for s in widths if _clean_ratio(col_empty, s, False) >= K["SHEET_CLEAN_BOUNDARIES"]),
        None,
    )
    fh = next(
        (s for s in heights if _clean_ratio(row_empty, s, False) >= K["SHEET_CLEAN_BOUNDARIES"]),
        None,
    )
    if fw is None or fh is None:
        return None
    return (fw, fh), w // fw, h // fh


def detect_character_sheet(
    a: np.ndarray, mask: np.ndarray, grid: GridCandidate | None
) -> SheetLayout | None:
    """A directional character sheet: 3..12 columns and 4 (or a multiple of 4) rows of frames.

    A supplied grid is tried first; otherwise (or when it does not describe a sheet) the frame size
    is inferred from the gaps between frames. Every row needs at least two non-empty frames and the
    per-row counts must agree (+-1).
    """
    K = FRAME_CONSTANTS
    h, w = mask.shape
    found: tuple[tuple[int, int], int, int] | None = None
    if grid is not None and grid.margin == (0, 0) and grid.separation == (0, 0):
        fw, fh = grid.cell
        cols, rows = w // fw, h // fh
        if (
            w % fw == 0
            and h % fh == 0
            and K["SHEET_MIN_COLS"] <= cols <= K["SHEET_MAX_COLS"]
            and rows >= 4
            and rows % 4 == 0
        ):
            found = ((fw, fh), cols, rows)
    if found is None:
        found = _find_frame(mask)
    if found is None:
        return None
    frame, cols, rows = found
    rects = frame_rects(frame, cols, rows)
    boxes = frame_bboxes(mask, rects)
    counts = [sum(1 for c in range(cols) if boxes[r * cols + c] is not None) for r in range(rows)]
    if min(counts) < K["SHEET_MIN_ROW_FRAMES"] or max(counts) - min(counts) > 1:
        return None
    directions: list[str] | None = None
    confidence = 0.0
    if rows == 4:
        directions, confidence = _infer_directions(mask, frame, cols)
    return SheetLayout(frame, cols, rows, directions, confidence)


def _infer_directions(
    mask: np.ndarray, frame: tuple[int, int], cols: int
) -> tuple[list[str], float]:
    """Weak heuristic for the row order of a 4-row sheet (see 02: mirror pairs, then face area)."""
    K = FRAME_CONSTANTS
    fw, fh = frame
    firsts = [mask[r * fh : (r + 1) * fh, 0:fw] for r in range(4)]

    def iou(a: np.ndarray, b: np.ndarray) -> float:
        union = (a | b).sum()
        return float((a & b).sum() / union) if union else 0.0

    scored = sorted(
        ((iou(firsts[i], np.fliplr(firsts[j])), i, j) for i in range(4) for j in range(i + 1, 4)),
        reverse=True,
    )
    best = scored[0]
    if len(scored) > 1 and best[0] - scored[1][0] < K["MIRROR_DECISIVE"]:
        return list(DEFAULT_DIRECTIONS), K["DEFAULT_DIRECTION_CONFIDENCE"]
    left_i, right_i = best[1], best[2]  # lower row index is "left" (RPG Maker order)
    rest = [r for r in range(4) if r not in (left_i, right_i)]
    region = (slice(fh // 8, fh // 2), slice(fw // 4, (fw * 3) // 4))
    face = {r: int(firsts[r][region].sum()) for r in rest}
    down_i = max(rest, key=lambda r: (face[r], -r))
    up_i = next(r for r in rest if r != down_i)
    order = {down_i: "down", up_i: "up", left_i: "left", right_i: "right"}
    return [order[r] for r in range(4)], K["DIRECTION_CONFIDENCE"]
