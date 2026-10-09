from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

OPAQUE_BACKGROUND_TOLERANCE = 8


def load_rgba(path: Path) -> np.ndarray:
    """Open an image and return it as uint8 RGBA, shape (h, w, 4).

    Animated GIFs: only the first frame is loaded here (the strips adapter handles the rest).
    """
    with Image.open(path) as im:
        im.seek(0)
        rgba = im.convert("RGBA")
        return np.asarray(rgba, dtype=np.uint8)


def dhash(a: np.ndarray) -> str:
    """A 64-bit difference hash of an RGBA image, as 16 hex digits (T13.04): the picture in
    grey (transparent pixels count as black) is reduced to 9 x 8, and each bit says whether a
    pixel is brighter than its left neighbour. Pictures that look alike differ in few bits."""
    rgb = a[..., :3].astype(np.float32)
    alpha = a[..., 3].astype(np.float32) / 255.0
    grey = (rgb @ np.array([0.299, 0.587, 0.114], dtype=np.float32)) * alpha
    small = Image.fromarray(np.clip(grey + 0.5, 0, 255).astype(np.uint8), "L").resize(
        (9, 8), Image.Resampling.BOX
    )
    px = np.asarray(small, dtype=np.int16)
    bits = (px[:, 1:] > px[:, :-1]).flatten()
    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    return f"{value:016x}"


def hashes(a: np.ndarray, regions: list[list[int]] | None) -> dict[str, object]:
    """The hash facts of an image: of the whole picture and of each region of a sheet (the
    objects found on it), in the order of ``regions``."""
    cut = [a[y : y + h, x : x + w] for x, y, w, h in regions or []]
    return {"dhash": dhash(a), "region_dhashes": [dhash(c) for c in cut if c.size]}


def is_fully_opaque(a: np.ndarray) -> bool:
    return bool((a[..., 3] == 255).all())


def _corner_background(a: np.ndarray) -> np.ndarray:
    h, w = a.shape[:2]
    corners = [
        tuple(int(v) for v in a[y, x]) for y, x in ((0, 0), (0, w - 1), (h - 1, 0), (h - 1, w - 1))
    ]
    counts: dict[tuple[int, ...], int] = {}
    for c in corners:
        counts[c] = counts.get(c, 0) + 1
    best = max(counts.values())
    for c in corners:  # corner order is top-left first, so ties resolve to the top-left pixel
        if counts[c] == best:
            return np.array(c, dtype=np.int16)
    raise AssertionError("unreachable")


def occupancy(a: np.ndarray) -> np.ndarray:
    """bool (h, w) mask of pixels that carry art.

    With any transparency: alpha > 0. For a fully opaque image the background is the most common
    colour among the four corners (ties: top-left) and a pixel is occupied when any channel
    differs from it by more than 8.
    """
    alpha = a[..., 3]
    if (alpha < 255).any():
        return alpha > 0
    background = _corner_background(a)
    diff = np.abs(a.astype(np.int16) - background[None, None, :])
    return (diff > OPAQUE_BACKGROUND_TOLERANCE).any(axis=2)


def opaque_bbox(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    """(x, y, w, h) of the True pixels, or None when there are none."""
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return None
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    return x0, y0, x1 - x0 + 1, y1 - y0 + 1


def dominant_colors(a: np.ndarray, k: int = 3) -> list[str]:
    """Top-k colours among occupied pixels, quantized to 5 bits per channel ("#rrggbb")."""
    mask = occupancy(a)
    px = a[mask]
    if len(px) == 0:
        return []
    q = (
        ((px[:, 0].astype(np.uint32) >> 3) << 10)
        | ((px[:, 1].astype(np.uint32) >> 3) << 5)
        | (px[:, 2].astype(np.uint32) >> 3)
    )
    keys, counts = np.unique(q, return_counts=True)
    order = sorted(range(len(keys)), key=lambda i: (-int(counts[i]), int(keys[i])))
    out: list[str] = []
    for i in order[:k]:
        key = int(keys[i])
        r, g, b = ((key >> 10) & 31) << 3 | 4, ((key >> 5) & 31) << 3 | 4, (key & 31) << 3 | 4
        out.append(f"#{r:02x}{g:02x}{b:02x}")
    return out


def _longest_true_run(flags: np.ndarray) -> tuple[int, int]:
    """(start, length) of the longest run of True values (length 0 when there is none)."""
    best_start, best_len, start = 0, 0, -1
    for i, v in enumerate(flags):
        if v and start < 0:
            start = i
        if (not v or i == len(flags) - 1) and start >= 0:
            end = i + 1 if v else i
            if end - start > best_len:
                best_start, best_len = start, end - start
            start = -1
    return best_start, best_len


def detect_nine_slice(a: np.ndarray) -> list[int] | None:
    """[left, top, right, bottom] border margins of a UI-like image, or None.

    The image must have alpha and be at least 24 px on both sides. The stretchable centre is the
    longest band of identical rows (and of identical columns); everything around it is border.
    """
    h, w = a.shape[:2]
    if h < 24 or w < 24 or not (a[..., 3] < 255).any():
        return None
    row_start, row_len = _longest_true_run((a[1:] == a[:-1]).all(axis=(1, 2)))
    col_start, col_len = _longest_true_run((a[:, 1:] == a[:, :-1]).all(axis=(0, 2)))
    if row_len < 1 or col_len < 1:
        return None
    top, bottom = row_start, h - (row_start + row_len + 1)
    left, right = col_start, w - (col_start + col_len + 1)
    if min(top, bottom, left, right) < 1:
        return None
    if row_len + 1 < h // 5 or col_len + 1 < w // 5:
        return None
    return [int(left), int(top), int(right), int(bottom)]
