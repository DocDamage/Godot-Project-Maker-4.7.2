from __future__ import annotations

import importlib.util
import json
import random
from pathlib import Path

import pytest

from rpggen.core import config, map_preview

REPO = Path(__file__).resolve().parents[2]
HOUSE = {"size": [5, 4], "door": [2, 4]}
BIG = {"size": [8, 6], "door": [4, 6]}


def test_default_options_are_the_map_of_every_earlier_project() -> None:
    plan = map_preview.plan(config.starter_map_defaults(), 12345, HOUSE)
    assert plan["is_default"] and plan["size"] == [40, 24]
    assert plan["buildings"] == [[8, 6]] and plan["doors"] == [[10, 10]]
    assert plan["spawn"] == [12, 12] and plan["npcs"] == [[16, 12]] and plan["chests"] == [[18, 8]]
    assert plan["enemies"] == [[28, 12]]
    assert plan["decorations"] == [
        [20, 4], [24, 5], [30, 8], [33, 14], [6, 17], [14, 19], [26, 18], [35, 20],
    ]  # fmt: skip
    assert plan["path"][0] == [12, 12] and [10, 10] in plan["path"] and [10, 12] in plan["path"]
    arpg = map_preview.plan(config.starter_map_defaults("arpg"), 12345, HOUSE, "arpg")
    assert arpg["enemies"] == [[28, 12], [32, 12]]
    assert map_preview.plan(config.starter_map_defaults(), 1, {})["buildings"] == []


def test_the_ground_option_does_not_change_the_layout() -> None:
    a = config.starter_map_defaults()
    b = {**a, "ground": "pack.tiles.sand"}
    assert map_preview.plan(a, 5, HOUSE) == map_preview.plan(b, 5, HOUSE)


def test_the_same_config_gives_the_same_map() -> None:
    options = {**config.starter_map_defaults(), "buildings": 2, "npcs": 3, "decorations": 20}
    assert map_preview.plan(options, 9, HOUSE) == map_preview.plan(options, 9, HOUSE)
    assert map_preview.plan(options, 9, HOUSE) != map_preview.plan(options, 10, HOUSE)


def _random_options(rnd: random.Random) -> dict:
    return {
        "size": [rnd.randint(24, 96), rnd.randint(24, 96)],
        "buildings": rnd.randint(0, 4),
        "npcs": rnd.randint(0, 6),
        "enemies": rnd.randint(0, 8),
        "chests": rnd.randint(0, 4),
        "decorations": rnd.randint(0, 40),
        "ground_patches": rnd.randint(0, 20),
        "ground": "",
    }


def _reachable(plan: dict, rects: list[tuple[int, int, int, int]]) -> set[tuple[int, int]]:
    w, h = plan["size"]
    blocked = {
        (r[0] + i, r[1] + j) for r in rects for i in range(r[2]) for j in range(r[3])
    }
    start = tuple(plan["spawn"])
    seen = {start}
    stack = [start]
    while stack:
        x, y = stack.pop()
        for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 1 <= n[0] <= w - 2 and 1 <= n[1] <= h - 2 and n not in blocked and n not in seen:
                seen.add(n)
                stack.append(n)
    return seen


@pytest.mark.parametrize("building", [HOUSE, BIG, {}], ids=["house", "big", "none"])
def test_random_option_sets_are_valid(building: dict) -> None:
    rnd = random.Random(2024)
    for case in range(200):
        options = _random_options(rnd)
        seed = rnd.randint(0, 99999)
        plan = map_preview.plan(options, seed, building)
        w, h = plan["size"]
        rects = []
        if building:
            bw, bh = building["size"]
            rects = [(bx, by, bw, bh) for bx, by in plan["buildings"]]
        entities = [
            tuple(t) for key in ("npcs", "chests", "enemies", "decorations") for t in plan[key]
        ]
        assert len(entities) == len(set(entities)), (case, "two entities on one tile")
        for x, y in entities:
            assert 1 <= x <= w - 2 and 1 <= y <= h - 2, (case, "outside the map")
            assert not any(map_preview._rect_contains(r, x, y) for r in rects), (case, "in a house")
        assert len(plan["npcs"]) <= options["npcs"]
        assert len(plan["decorations"]) <= options["decorations"]
        assert len(plan["buildings"]) <= options["buildings"]
        for i, first in enumerate(rects):
            for second in rects[i + 1 :]:
                assert not map_preview._intersects(first, second), (case, "buildings overlap")
        reachable = _reachable(plan, rects)
        for door in plan["doors"]:
            assert tuple(door) in reachable, (case, "door unreachable", door)
        for cell in [*plan["path"], *plan["exit_path"]]:
            assert 1 <= cell[0] <= w - 2 and 1 <= cell[1] <= h - 2
            assert not any(map_preview._rect_contains(r, cell[0], cell[1]) for r in rects), (
                case, "a road runs through a house", cell
            )
        assert plan["exit_gap"][0] == w - 1 and tuple(plan["exit_gap"]) not in entities
        assert tuple(plan["exit_path"][-1]) == (w - 2, plan["exit_gap"][1])
        assert not set(map(tuple, plan["exit_path"])) & set(entities), (case, "entity on the exit road")


def test_too_small_a_map_places_what_fits_and_warns() -> None:
    options = {**config.starter_map_defaults(), "size": [24, 24], "buildings": 4}
    plan = map_preview.plan(options, 3, BIG)
    assert 0 < len(plan["buildings"]) < 4
    assert any(w.startswith("buildings: placed") for w in plan["warnings"])


def test_the_fixture_matches_the_python_planner() -> None:
    spec = importlib.util.spec_from_file_location(
        "make_map_plan_cases", REPO / "tools" / "make_map_plan_cases.py"
    )
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    fixture = json.loads(tool.OUT.read_text(encoding="utf-8"))
    assert fixture == json.loads(json.dumps(tool.cases()))
    assert len(fixture) == 20
