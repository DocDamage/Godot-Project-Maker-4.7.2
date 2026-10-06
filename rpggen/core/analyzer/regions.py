from __future__ import annotations

import numpy as np

from rpggen.core.analyzer.grid import GridCandidate

REGION_CONSTANTS = {
    "JOIN_MIN_FRACTION": 0.25,  # share of border pixels that must be occupied on both sides
    "TERRAIN_FRACTION": 0.6,  # a component holding more of the occupied cells is terrain
}

Rect = tuple[int, int, int, int]


class _UnionFind:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))

    def find(self, i: int) -> int:
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]
            i = self.parent[i]
        return i

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def _axis_cells(length: int, cell: int, margin: int, sep: int) -> list[int]:
    n = (length - 2 * margin + sep) // (cell + sep)
    return [margin + k * (cell + sep) for k in range(max(n, 0))]


def detect_regions(mask: np.ndarray, grid: GridCandidate, min_cells: int = 2) -> list[Rect]:
    """Pixel rects [x, y, w, h] of multi-cell objects whose art continues across cell borders."""
    K = REGION_CONSTANTS
    cw, ch = grid.cell
    xs = _axis_cells(mask.shape[1], cw, grid.margin[0], grid.separation[0])
    ys = _axis_cells(mask.shape[0], ch, grid.margin[1], grid.separation[1])
    rows, cols = len(ys), len(xs)
    if rows == 0 or cols == 0:
        return []

    def cell(r: int, c: int) -> np.ndarray:
        return mask[ys[r] : ys[r] + ch, xs[c] : xs[c] + cw]

    occ = np.array([[cell(r, c).any() for c in range(cols)] for r in range(rows)])
    full = np.array([[cell(r, c).all() for c in range(cols)] for r in range(rows)])
    uf = _UnionFind(rows * cols)
    for r in range(rows):
        for c in range(cols):
            if not occ[r, c]:
                continue
            if c + 1 < cols and occ[r, c + 1]:
                left = cell(r, c)[:, -1]
                right = cell(r, c + 1)[:, 0]
                if (left & right).sum() >= K["JOIN_MIN_FRACTION"] * ch:
                    uf.union(r * cols + c, r * cols + c + 1)
            if r + 1 < rows and occ[r + 1, c]:
                top = cell(r, c)[-1, :]
                bottom = cell(r + 1, c)[0, :]
                if (top & bottom).sum() >= K["JOIN_MIN_FRACTION"] * cw:
                    uf.union(r * cols + c, (r + 1) * cols + c)

    groups: dict[int, list[tuple[int, int]]] = {}
    for r in range(rows):
        for c in range(cols):
            if occ[r, c]:
                groups.setdefault(uf.find(r * cols + c), []).append((r, c))
    total_occupied = int(occ.sum())
    found: list[Rect] = []
    for members in groups.values():
        if len(members) < min_cells:
            continue
        rs = [m[0] for m in members]
        cs = [m[1] for m in members]
        if max(rs) - min(rs) + 1 < 2 and max(cs) - min(cs) + 1 < 2:
            continue
        if len(members) > K["TERRAIN_FRACTION"] * total_occupied:
            continue
        if all(full[r, c] for r, c in members):
            continue  # terrain fill: every cell is solid
        x0, x1 = xs[min(cs)], xs[max(cs)] + cw
        y0, y1 = ys[min(rs)], ys[max(rs)] + ch
        sub = mask[y0:y1, x0:x1]
        py, px = np.nonzero(sub)
        found.append(
            (
                x0 + int(px.min()),
                y0 + int(py.min()),
                int(px.max() - px.min() + 1),
                int(py.max() - py.min() + 1),
            )
        )
    found.sort(key=lambda r: (r[1], r[0]))
    return found
