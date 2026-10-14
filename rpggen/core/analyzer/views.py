"""Which view of a thing a picture is, told from the picture (the cars of *Tiles Vehicles*).

A pack draws a car once a heading. Some of its cars say the heading in the file's name
(``taxi_N.png``, ``taxi_NEU.png``); others are numbered (``carBlack2_000.png`` to ``_015``),
and the numbers follow no order: two cars of one model in two colours begin at different
views. What a numbered picture shows is then read from the picture: it is laid over every
view of a car whose names say them, and takes the name of the one it is most like.

* **How alike two pictures are** (``likeness``, 0 to 1): the mean of how much their
  silhouettes overlap and how many of their edges (the pixels where the colour changes: a
  window, a wheel, the roof's rim) fall on each other, at the best of nine shifts of a pixel.
  The colours themselves are not compared, so a black car is like a yellow one.
* **Every view once** (``assign``): the views of a numbered set take the names so that the
  likeness summed over the set is as large as it can be, and no name is given twice. A front
  and a back that look the same would both take the better name otherwise.
* **Names that are wrong** (``misnamed``): the named sets are laid over each other first. A
  view of one set that every other set takes for another view, all of them for the same one,
  is named wrongly in the pack (measured: the taxi's ``N`` and ``S`` show what ``S`` and ``N``
  of the police car, the ambulance and the lorry show).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

PAINTED_ALPHA = 128
EDGE_STEP = 24  # two neighbours this far apart in one channel lie on an edge
SIZE_SLACK = 4  # two views whose painted parts differ by more than this are not laid
SHIFTS = (-1, 0, 1)


@dataclass(frozen=True, eq=False)
class View:
    """The painted part of one picture: its silhouette and its edges."""

    mask: np.ndarray
    edge: np.ndarray

    @property
    def size(self) -> tuple[int, int]:
        return int(self.mask.shape[1]), int(self.mask.shape[0])

    def key(self) -> bytes:
        """The silhouette as bytes: two pictures of one model in two colours have one."""
        return bytes(self.mask.shape) + np.packbits(self.mask).tobytes()


def view(rgba: np.ndarray) -> View | None:
    """The view an RGBA picture shows, cut to its painted part; None for an empty one."""
    solid = rgba[..., 3] >= PAINTED_ALPHA
    ys, xs = np.nonzero(solid)
    if xs.size == 0:
        return None
    part = rgba[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1].astype(np.int16)
    mask = part[..., 3] >= PAINTED_ALPHA
    colour = np.where(mask[..., None], part[..., :3], -255)
    edge = np.zeros(mask.shape, dtype=bool)
    across = np.abs(colour[:, 1:] - colour[:, :-1]).max(axis=-1) > EDGE_STEP
    down = np.abs(colour[1:] - colour[:-1]).max(axis=-1) > EDGE_STEP
    edge[:, 1:] |= across
    edge[:, :-1] |= across
    edge[1:] |= down
    edge[:-1] |= down
    return View(mask, edge & mask)


def _placed(layer: np.ndarray, width: int, height: int, dx: int, dy: int) -> np.ndarray:
    """``layer`` on a canvas, standing in the middle of its bottom row, moved by a shift."""
    out = np.zeros((height, width), dtype=bool)
    h, w = layer.shape
    x, y = (width - w) // 2 + dx, height - h - 1 + dy
    out[y : y + h, x : x + w] = layer
    return out


def likeness(a: View, b: View, slack: int | None = SIZE_SLACK) -> float:
    """How alike two views are, from 0 to 1 (the module's words). Two whose painted parts
    differ by more than ``slack`` pixels are not laid at all (None: any two are)."""
    apart = max(abs(a.size[0] - b.size[0]), abs(a.size[1] - b.size[1]))
    if slack is not None and apart > slack:
        return 0.0
    width = max(a.size[0], b.size[0]) + 4
    height = max(a.size[1], b.size[1]) + 2
    mask_b, edge_b = _placed(b.mask, width, height, 0, 0), _placed(b.edge, width, height, 0, 0)
    edges = int(a.edge.sum()) + int(b.edge.sum())
    best = 0.0
    for dx in SHIFTS:
        for dy in SHIFTS:
            mask_a = _placed(a.mask, width, height, dx, dy)
            overlap = int((mask_a & mask_b).sum()) / int((mask_a | mask_b).sum())
            shared = int((_placed(a.edge, width, height, dx, dy) & edge_b).sum())
            best = max(best, (overlap + (2 * shared / edges if edges else 0.0)) / 2)
    return best


def assign(scores: np.ndarray) -> list[int]:
    """``out[row] = column``: every row a column of its own, the scores summed as large as
    they can be (the Hungarian method on a square matrix)."""
    n = int(scores.shape[0])
    cost = (-scores).tolist()
    inf = float("inf")
    u, v = [0.0] * (n + 1), [0.0] * (n + 1)
    owner, way = [0] * (n + 1), [0] * (n + 1)
    for row in range(1, n + 1):
        owner[0] = row
        j0 = 0
        least = [inf] * (n + 1)
        used = [False] * (n + 1)
        while True:
            used[j0] = True
            i0, delta, j1 = owner[j0], inf, 0
            for j in range(1, n + 1):
                if used[j]:
                    continue
                cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                if cur < least[j]:
                    least[j], way[j] = cur, j0
                if least[j] < delta:
                    delta, j1 = least[j], j
            for j in range(n + 1):
                if used[j]:
                    u[owner[j]] += delta
                    v[j] -= delta
                else:
                    least[j] -= delta
            j0 = j1
            if owner[j0] == 0:
                break
        while j0:
            j1 = way[j0]
            owner[j0] = owner[j1]
            j0 = j1
    out = [0] * n
    for j in range(1, n + 1):
        out[owner[j] - 1] = j - 1
    return out


def lay(
    views: list[View], named: list[View], slack: int | None = SIZE_SLACK
) -> tuple[list[int], float]:
    """``(names, likeness)``: for every one of ``views`` the place in ``named`` of the view it
    is, every place once, and how alike the two sets are on average (0 to 1)."""
    scores = np.array([[likeness(a, b, slack) for b in named] for a in views], dtype=np.float64)
    order = assign(scores)
    return order, float(np.mean([scores[i][j] for i, j in enumerate(order)]))


def misnamed(named: list[list[View]]) -> list[dict[int, int]]:
    """For every named set ``{place: the place its picture belongs in}``: the views that
    every other set (two at least) takes for one other view. The sets have their views in one
    order."""
    count = len(named)
    out: list[dict[int, int]] = [{} for _ in named]
    if count < 3:
        return out
    # models of every size are laid here: a lorry says which end of a car is its front
    seen = {
        (a, b): lay(named[a], named[b], None)[0] for a in range(count) for b in range(a + 1, count)
    }
    for a in range(count):
        for place in range(len(named[a])):
            said = set()
            for b in range(count):
                if b == a:
                    continue
                if a < b:
                    said.add(seen[(a, b)][place])
                else:  # where b's views went in a: the one that went to this place
                    said.add(seen[(b, a)].index(place))
            if len(said) == 1 and place not in said:
                out[a][place] = said.pop()
    # only whole exchanges are believed: what moves to a place makes room there
    for moves in out:
        if set(moves) != set(moves.values()):
            moves.clear()
    return out
