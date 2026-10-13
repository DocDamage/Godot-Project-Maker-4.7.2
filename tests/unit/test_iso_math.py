"""T17.14: the arithmetic of the isometric view, and the table of cases the GDScript mirror
(``RpgIso``) is tested against."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import pytest

from rpggen.core import iso_math

REPO = Path(__file__).resolve().parents[2]
RUNTIME = REPO / "godot_templates/addons/rpg_runtime/world/iso.gd"
FOOTPRINTS = [(60, 34), (64, 32), (180, 104), (120, 74), (132, 66), (33, 17)]


def test_the_table_of_cases_is_what_the_module_gives() -> None:
    """The file the GDScript test reads is written by ``python -m rpggen.core.iso_math``; a
    change of the arithmetic that is not written there fails here, and then in Godot."""
    stored = json.loads((REPO / iso_math.CASES_FILE).read_text(encoding="utf-8"))
    assert stored == iso_math.cases()
    names = {case["fn"] for case in stored}
    public = {
        name
        for name, value in vars(iso_math).items()
        if callable(value) and not name.startswith("_") and value.__module__ == iso_math.__name__
    }
    assert public - {"cases", "write_cases"} == names, "every function is in the table"
    assert len(stored) > 2000
    assert set(iso_math.FOOTPRINTS) == set(FOOTPRINTS)


def test_the_runtime_has_the_same_names() -> None:
    text = RUNTIME.read_text(encoding="utf-8")
    sides = ", ".join(f'"{side}"' for side in iso_math.SIDES)
    assert f"const SIDES: Array[String] = [{sides}]" in text
    for side, (dx, dy) in iso_math.STEPS.items():
        assert f'"{side}": Vector2i({dx}, {dy})' in text, side
    for facing, side in iso_math.FACING_SIDES.items():
        assert f'"{facing}": "{side}"' in text, facing
    for controls in iso_math.CONTROLS:
        assert re.search(
            rf'^const CONTROLS_{controls.upper()} := "{controls}"$', text, re.MULTILINE
        )
    for name in vars(iso_math):
        value = getattr(iso_math, name)
        own = callable(value) and getattr(value, "__module__", "") == iso_math.__name__
        if own and not name.startswith("_") and name not in ("cases", "write_cases"):
            assert f"static func {name}(" in text, f"RpgIso has no {name}"


@pytest.mark.parametrize("footprint", FOOTPRINTS)
def test_a_cell_and_its_place_on_the_screen(footprint: tuple[int, int]) -> None:
    w, h = footprint
    assert iso_math.cell_to_screen(0, 0, w, h) == (w / 2, h / 2), "the first cell hangs under 0"
    assert iso_math.cell_to_screen(1, 0, w, h) == (w, h), "east is down and to the right"
    assert iso_math.cell_to_screen(0, 1, w, h) == (0, h), "south is down and to the left"
    for cx in range(-3, 9):
        for cy in range(-3, 9):
            x, y = iso_math.cell_to_screen(cx, cy, w, h)
            assert iso_math.screen_to_cell(x, y, w, h) == (cx, cy)
            assert iso_math.grid_point(x, y, w, h) == pytest.approx((cx + 0.5, cy + 0.5))
            assert iso_math.depth(cx, cy, w, h) == y
            top, right, bottom, left = iso_math.diamond(cx, cy, w, h)
            assert top == [x, y - h / 2] and bottom == [x, y + h / 2]
            assert right == [x + w / 2, y] and left == [x - w / 2, y]
            # nine tenths of the way to every corner is still the cell
            for px, py in (top, right, bottom, left):
                inside = (x + (px - x) * 0.9, y + (py - y) * 0.9)
                assert iso_math.screen_to_cell(*inside, w, h) == (cx, cy)
            for side, near in zip(iso_math.SIDES, iso_math.neighbours(cx, cy), strict=True):
                dx, dy = iso_math.step(side, w, h)
                assert iso_math.cell_to_screen(*near, w, h) == (x + dx, y + dy)
                assert iso_math.screen_to_cell(x + dx, y + dy, w, h) == tuple(near)
    assert iso_math.neighbours(4, 7) == [[4, 6], [5, 7], [4, 8], [3, 7]], "n, e, s, w"
    # the four sides on the screen: n the upper right, e the lower right, s the lower left
    assert iso_math.step("n", w, h) == (w / 2, -h / 2)
    assert iso_math.step("e", w, h) == (w / 2, h / 2)
    assert iso_math.step("s", w, h) == (-w / 2, h / 2)
    assert iso_math.step("w", w, h) == (-w / 2, -h / 2)
    assert iso_math.unit(w, h) == round(math.hypot(w / 2, h / 2))


def test_what_is_lower_on_the_screen_is_nearer() -> None:
    w, h = 60, 34
    assert iso_math.depth(3, 3, w, h) < iso_math.depth(4, 3, w, h) == iso_math.depth(3, 4, w, h)
    assert iso_math.depth(4, 2, w, h) == iso_math.depth(3, 3, w, h), "side by side: neither hides"
    # a map of 40 x 24 cells: its rectangle on the screen holds every diamond, and no more
    x0, y0, width, height = iso_math.bounds(40, 24, w, h)
    assert (x0, y0, width, height) == (-690.0, 0.0, 1920.0, 1088.0)
    corners = [
        c for cell in ((0, 0), (39, 0), (0, 23), (39, 23)) for c in iso_math.diamond(*cell, w, h)
    ]
    assert min(c[0] for c in corners) == x0 and max(c[0] for c in corners) == x0 + width
    assert min(c[1] for c in corners) == y0 and max(c[1] for c in corners) == y0 + height


@pytest.mark.parametrize("size", [(1, 1), (2, 2), (2, 1), (1, 2), (3, 2), (2, 3), (4, 2), (2, 4)])
def test_a_thing_on_several_cells_sorts_right_in_two_halves(size: tuple[int, int]) -> None:
    """The claim the object scenes are built on: with the halves keyed by the outer corners of
    what the thing stands on, an actor anywhere on the ground it does not stand on is drawn on
    the right side of every half it overlaps. It holds while neither side of the footprint is
    more than twice the other."""
    w, h = 60, 34
    x0, y0 = 8, 6
    columns, rows = size
    split, left, right = iso_math.sort_keys(x0, y0, columns, rows, w, h)
    assert split == iso_math.cell_to_screen(x0 + columns - 1, y0 + rows - 1, w, h)[0]
    assert left == iso_math.diamond(x0, y0 + rows - 1, w, h)[3][1], "the y of the left corner"
    assert right == iso_math.diamond(x0 + columns - 1, y0, w, h)[1][1], "... of the right corner"
    if columns == rows:
        assert left == right, "a square of cells sorts by one line"
    checked = 0
    for iy in range(-12, rows * 4 + 13):
        for ix in range(-12, columns * 4 + 13):
            gx, gy = x0 + ix / 4, y0 + iy / 4
            if x0 <= gx <= x0 + columns and y0 <= gy <= y0 + rows:
                continue  # nobody stands on what it stands on
            x, y = (gx - gy + 1) * w / 2, (gx + gy) * h / 2
            truth = iso_math.in_front(x, y, x0, y0, columns, rows, w, h)
            if truth == 0:
                continue
            checked += 1
            keys = ([left] if x <= split else []) + ([right] if x >= split else [])
            for key in keys:
                assert (y > key) == (truth > 0) and y != key, (size, gx, gy)
    assert checked > 300


def test_in_front_of_a_thing_and_behind_it() -> None:
    w, h = 60, 34

    def at(cx: int, cy: int) -> int:
        return iso_math.in_front(*iso_math.cell_to_screen(cx, cy, w, h), 8, 6, 2, 1, w, h)

    assert at(8, 7) == at(9, 7) == at(10, 6) == at(10, 7) == 1, "south and east of it"
    assert at(8, 5) == at(9, 5) == at(7, 6) == at(7, 5) == -1, "north and west of it"
    assert at(8, 6) == at(9, 6) == 0, "on it"
    assert at(10, 5) == at(7, 7) == 0, "beside it: north-east and south-west hide nothing"


def test_the_side_a_direction_points_to() -> None:
    assert [iso_math.side_of(*d) for d in ((1, -1), (1, 1), (-1, 1), (-1, -1))] == list("nesw")
    # along an axis: a quarter turn clockwise brings it onto the next side
    assert [iso_math.side_of(*d) for d in ((0, -1), (1, 0), (0, 1), (-1, 0))] == list("nesw")
    assert iso_math.side_of(0, 0) == "s", "an actor that has not moved faces down"
    assert iso_math.FACING_SIDES == {"up": "n", "right": "e", "down": "s", "left": "w"}
    assert iso_math.facing_of(30, -17) == "right" and iso_math.facing_of(-30, 17) == "left"
    assert iso_math.facing_of(1, -1) == "up", "the vertical wins a tie"
    # an actor looks where it last went while that agrees with its facing
    assert iso_math.faced_side("right", 30, -17) == "n"
    assert iso_math.faced_side("right", 30, 17) == "e"
    assert iso_math.faced_side("down", 30, -17) == "s", "a spawn point turned it"
    assert iso_math.faced_side("up", 0, 0) == "n"
    assert iso_math.faced_side("sideways", 0, 0) == "s"
    assert iso_math.faced_cell(5, 7, "right", 30, -17) == (5, 6)
    assert iso_math.faced_cell(5, 7, "left", 0, 0) == (4, 7)


@pytest.mark.parametrize("footprint", FOOTPRINTS)
def test_the_two_ways_the_pad_moves_an_actor(footprint: tuple[int, int]) -> None:
    w, h = footprint
    assert iso_math.CONTROLS == ("screen", "grid") and iso_math.CONTROLS_DEFAULT == "screen"
    for pad in ((1, 0), (0, -1), (1, 1), (0.3, -0.2)):
        assert iso_math.pad_vector(*pad, "screen", w, h) == pad, "up is up on the screen"
    length = math.hypot(w / 2, h / 2)
    for pad, side in (((0, -1), "n"), ((1, 0), "e"), ((0, 1), "s"), ((-1, 0), "w")):
        x, y = iso_math.pad_vector(*pad, "grid", w, h)
        dx, dy = iso_math.step(side, w, h)
        assert (x, y) == pytest.approx((dx / length, dy / length)), f"{pad} follows the {side} axis"
        assert math.hypot(x, y) == pytest.approx(1.0)
        assert iso_math.pad_side(*pad, "grid") == side
        # one step of the pad is one cell: a unit of walking along it reaches the neighbour
        cx, cy = iso_math.cell_to_screen(5, 5, w, h)
        near = iso_math.screen_to_cell(cx + x * length, cy + y * length, w, h)
        assert list(near) == iso_math.neighbours(5, 5)[iso_math.SIDES.index(side)]
    # two directions at once: across the diamond's corner, never faster than one alone
    x, y = iso_math.pad_vector(1, -1, "grid", w, h)
    assert (x, y) == pytest.approx((1.0, 0.0)), "up and right together are right on the screen"
    assert iso_math.pad_vector(0, 0, "grid", w, h) == (0.0, 0.0)
    assert iso_math.pad_side(0, 0, "grid") == "" and iso_math.pad_side(0, 0, "screen") == ""
    assert (
        iso_math.pad_side(0.3, -0.8, "screen") == "n" and iso_math.pad_side(1, 0, "screen") == "e"
    )
