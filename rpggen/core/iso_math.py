"""The arithmetic of the isometric view (T17.14), the same the runtime counts by.

``RpgIso`` (``world/iso.gd``) has every function of this module with the same numbers;
``cases()`` is a table of inputs and results that both are tested against
(``godot_templates/tests/unit/iso_math_cases.json``, written by ``python -m
rpggen.core.iso_math``). The preview of a planned map draws with it.

**The grid.** A map is planned on cells ``(x, y)``, x east and y south, whatever the view. In
the isometric view a cell is a diamond ``w`` wide and ``h`` high (the footprint of the pack:
60 x 34, 180 x 104, never assumed 2:1) laid out as Godot lays out ``TILE_LAYOUT_DIAMOND_DOWN``:
the middle of the cell ``(x, y)`` is at ``((x - y + 1) * w / 2, (x + y + 1) * h / 2)``, so the
cell ``(0, 0)`` is the top corner of the map, east runs down and to the right and south down
and to the left. The four sides of a diamond are, by the grid, ``n`` (the upper right), ``e``
(the lower right), ``s`` (the lower left) and ``w`` (the upper left).

**Depth.** What is lower on the screen is nearer: the sort key of a cell is the y of its
middle, which is the line through the left and the right corner of its diamond. A thing that
stands on several cells is cut in two at the corner nearest the camera, and each half sorts by
the outer corner of its side (``sort_keys``): an actor whose feet are below that line is in
front of that half, and nothing that can be walked lies on the wrong side of it.

No Qt, no Godot.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

CASES_FILE = "godot_templates/tests/unit/iso_math_cases.json"
SIDES = ("n", "e", "s", "w")
# the neighbour of a cell on each side, by the grid
STEPS: dict[str, tuple[int, int]] = {"n": (0, -1), "e": (1, 0), "s": (0, 1), "w": (-1, 0)}
# the side a facing looks to when nothing says more: a quarter turn clockwise brings each of
# the four directions of the screen onto the side of the diamond next to it
FACING_SIDES: dict[str, str] = {"up": "n", "right": "e", "down": "s", "left": "w"}
CONTROLS = ("screen", "grid")
CONTROLS_DEFAULT = "screen"


def cell_to_screen(cx: int, cy: int, w: int, h: int) -> tuple[float, float]:
    """The middle of the cell on the screen (in the px of the map's layer)."""
    return (cx - cy + 1) * w / 2.0, (cx + cy + 1) * h / 2.0


def grid_point(x: float, y: float, w: int, h: int) -> tuple[float, float]:
    """A point of the screen in the grid's own coordinates: the cell ``(cx, cy)`` is the
    square from ``(cx, cy)`` to ``(cx + 1, cy + 1)``."""
    a = 2.0 * x / w - 1.0
    b = 2.0 * y / h
    return (a + b) / 2.0, (b - a) / 2.0


def screen_to_cell(x: float, y: float, w: int, h: int) -> tuple[int, int]:
    """The cell a point of the screen lies in."""
    gx, gy = grid_point(x, y, w, h)
    return math.floor(gx), math.floor(gy)


def depth(cx: int, cy: int, w: int, h: int) -> float:
    """The sort key of a cell: the y of its middle. A greater one is drawn later, in front."""
    return (cx + cy + 1) * h / 2.0


def diamond(cx: int, cy: int, w: int, h: int) -> list[list[float]]:
    """The corners of a cell on the screen: the top, the right, the bottom, the left."""
    x, y = cell_to_screen(cx, cy, w, h)
    return [[x, y - h / 2.0], [x + w / 2.0, y], [x, y + h / 2.0], [x - w / 2.0, y]]


def neighbours(cx: int, cy: int) -> list[list[int]]:
    """The four neighbours of a cell, in the order n, e, s, w."""
    return [[cx + STEPS[side][0], cy + STEPS[side][1]] for side in SIDES]


def step(side: str, w: int, h: int) -> tuple[float, float]:
    """How far the middle of the neighbour on ``side`` is on the screen."""
    dx, dy = STEPS.get(side, (0, 0))
    return (dx - dy) * w / 2.0, (dx + dy) * h / 2.0


def unit(w: int, h: int) -> int:
    """The length of one step from a cell to its neighbour, in whole px: what a recipe or the
    runtime takes where a square map has its tile size (a reach, a spacing, a range)."""
    return max(1, int(math.floor(math.hypot(w / 2.0, h / 2.0) + 0.5)))


def side_of(dx: float, dy: float) -> str:
    """The side of the diamond a direction of the screen points to. The four neighbours lie
    in the four quadrants of the screen; a direction along an axis goes to the side a quarter
    turn clockwise brings it to (up to n, right to e, down to s, left to w), and no direction
    at all is s (an actor that has not moved faces down)."""
    if dx > 0 and dy < 0:
        return "n"
    if dx > 0 and dy > 0:
        return "e"
    if dx < 0 and dy > 0:
        return "s"
    if dx < 0 and dy < 0:
        return "w"
    if dy < 0:
        return "n"
    if dx > 0:
        return "e"
    if dx < 0:
        return "w"
    return "s"


def facing_of(dx: float, dy: float) -> str:
    """The one of four facings a direction of the screen is nearest to (the vertical wins a
    tie): ``RpgAnimationDriver.dir_to_facing``."""
    if abs(dx) > abs(dy):
        return "right" if dx > 0 else "left"
    return "down" if dy >= 0 else "up"


def faced_side(facing: str, look_x: float, look_y: float) -> str:
    """The side an actor faces: where it last went (``look``) while that still agrees with
    its facing, else the side of the facing alone (a spawn point turned it)."""
    if (look_x != 0 or look_y != 0) and facing_of(look_x, look_y) == facing:
        return side_of(look_x, look_y)
    return FACING_SIDES.get(facing, "s")


def faced_cell(cx: int, cy: int, facing: str, look_x: float, look_y: float) -> tuple[int, int]:
    """The cell in front of an actor that stands on ``(cx, cy)``."""
    dx, dy = STEPS[faced_side(facing, look_x, look_y)]
    return cx + dx, cy + dy


def pad_vector(ix: float, iy: float, controls: str, w: int, h: int) -> tuple[float, float]:
    """Where the pad moves an actor on the screen. ``screen``: up is up. ``grid``: the four
    directions follow the diamond's axes (up to n, right to e, down to s, left to w), so one
    direction held walks along a row of cells. Never longer than 1."""
    if controls != "grid":
        return float(ix), float(iy)
    length = math.hypot(w / 2.0, h / 2.0)
    if length <= 0:
        return 0.0, 0.0
    ex, ey = w / 2.0 / length, h / 2.0 / length  # one step east
    sx, sy = -w / 2.0 / length, h / 2.0 / length  # one step south
    x = ix * ex + iy * sx
    y = ix * ey + iy * sy
    size = math.hypot(x, y)
    if size > 1.0:
        x, y = x / size, y / size
    return x, y


def pad_side(ix: float, iy: float, controls: str) -> str:
    """The neighbour one press of the pad steps to (the stronger axis wins, the vertical a
    tie): by the grid with ``grid`` controls, and with ``screen`` controls the side the
    direction of the screen points to. "" for no press."""
    if ix == 0 and iy == 0:
        return ""
    if abs(ix) > abs(iy):
        dx, dy = (1.0 if ix > 0 else -1.0), 0.0
    else:
        dx, dy = 0.0, (1.0 if iy > 0 else -1.0)
    if controls == "grid":
        return FACING_SIDES[facing_of(dx, dy)]
    return side_of(dx, dy)


def bounds(columns: int, rows: int, w: int, h: int) -> list[float]:
    """The rectangle ``[x, y, width, height]`` around a map of ``columns`` by ``rows`` cells
    whose first cell is ``(0, 0)``."""
    return [-(rows - 1) * w / 2.0, 0.0, (columns + rows) * w / 2.0, (columns + rows) * h / 2.0]


def sort_keys(x0: int, y0: int, columns: int, rows: int, w: int, h: int) -> list[float]:
    """How a thing that stands on the cells from ``(x0, y0)``, ``columns`` by ``rows``, sorts:
    ``[split x, key of the left half, key of the right half]``. The halves meet at the x of
    the corner nearest the camera; the left one sorts by the y of the left corner of what it
    stands on, the right one by the y of the right corner. On a square of cells the two are
    one line, the one through the middle."""
    split = (x0 + columns - (y0 + rows) + 1) * w / 2.0
    left = (x0 + y0 + rows) * h / 2.0
    right = (x0 + columns + y0) * h / 2.0
    return [split, left, right]


def in_front(x: float, y: float, x0: int, y0: int, columns: int, rows: int, w: int, h: int) -> int:
    """Whether a point of the ground is in front of a thing on those cells (1), behind it
    (-1) or on it or beside it, where neither hides the other (0). By the grid: in front is
    south or east of all of it, behind is north or west of all of it."""
    gx, gy = grid_point(x, y, w, h)
    south, east = gy >= y0 + rows, gx >= x0 + columns
    north, west = gy <= y0, gx <= x0
    if (south or east) and not (north or west):
        return 1
    if (north or west) and not (south or east):
        return -1
    return 0


def _r(value: float) -> float:
    return round(float(value), 4)


def _plain(result: Any) -> Any:
    if isinstance(result, tuple | list):
        return [_plain(item) for item in result]
    if isinstance(result, float):
        return _r(result)
    return result


FOOTPRINTS = ((60, 34), (64, 32), (180, 104), (120, 74), (132, 66), (33, 17))


def cases() -> list[dict[str, Any]]:
    """The table both languages are tested against: ``{"fn", "args", "result"}``."""
    out: list[dict[str, Any]] = []
    functions = globals()

    def add(fn: str, *args: Any) -> None:
        out.append({"fn": fn, "args": list(args), "result": _plain(functions[fn](*args))})

    cells = ((0, 0), (1, 0), (0, 1), (3, 2), (12, 12), (39, 23), (-1, 0), (0, -2), (-4, -7))
    looks = ((0.0, 0.0), (1.0, 0.0), (-1.0, 0.0), (0.0, 1.0), (0.0, -1.0), (30.0, -17.0),
             (30.0, 17.0), (-30.0, 17.0), (-30.0, -17.0), (0.2, -3.0), (-5.0, 0.1))  # fmt: skip
    for w, h in FOOTPRINTS:
        add("unit", w, h)
        add("bounds", 40, 24, w, h)
        add("bounds", 1, 1, w, h)
        for side in SIDES:
            add("step", side, w, h)
        for cx, cy in cells:
            add("cell_to_screen", cx, cy, w, h)
            add("depth", cx, cy, w, h)
            add("diamond", cx, cy, w, h)
            x, y = cell_to_screen(cx, cy, w, h)
            # the middle, and a point a quarter of the way to each corner: all in the cell
            for px, py in ((x, y), (x + w / 4.0 - 1, y), (x - w / 4.0 + 1, y),
                           (x, y + h / 4.0 - 1), (x, y - h / 4.0 + 1)):  # fmt: skip
                add("screen_to_cell", _r(px), _r(py), w, h)
                add("grid_point", _r(px), _r(py), w, h)
        for controls in CONTROLS:
            for ix, iy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1),
                           (-1, -1), (0.5, 0), (0, -0.25), (0.3, 0.8)):  # fmt: skip
                add("pad_vector", ix, iy, controls, w, h)
        for x0, y0, columns, rows in ((4, 4, 1, 1), (4, 4, 2, 2), (4, 4, 2, 1), (4, 4, 1, 2),
                                      (8, 6, 3, 2), (0, 0, 4, 4)):  # fmt: skip
            add("sort_keys", x0, y0, columns, rows, w, h)
            # the middle of every cell of a ring two cells wide around it
            for cy in range(y0 - 2, y0 + rows + 2):
                for cx in range(x0 - 2, x0 + columns + 2):
                    x, y = cell_to_screen(cx, cy, w, h)
                    add("in_front", x, y, x0, y0, columns, rows, w, h)
    for cx, cy in cells:
        add("neighbours", cx, cy)
    for dx, dy in looks:
        add("side_of", dx, dy)
        add("facing_of", dx, dy)
        for facing in ("up", "down", "left", "right", "sideways"):
            add("faced_side", facing, dx, dy)
            add("faced_cell", 5, 7, facing, dx, dy)
    for controls in CONTROLS:
        for ix, iy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (0.3, -0.8), (-0.9, 0.2)):
            add("pad_side", ix, iy, controls)
    return out


def write_cases(repo: Path) -> Path:
    path = repo / CASES_FILE
    path.write_text(json.dumps(cases(), indent=1) + "\n", encoding="utf-8", newline="\n")
    return path


if __name__ == "__main__":  # pragma: no cover
    print(write_cases(Path(__file__).resolve().parents[2]))
