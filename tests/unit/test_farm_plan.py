"""T17.06: the map of a farm: a house with a bed, a plot, water, a bin, animal houses with fenced
yards, things to clear and the way out, all as cells; the check that the farmer can walk to each
of them; the stored plan; the picture."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from rpggen import schema
from rpggen.core import crop_plan, farm_plan, map_preview, world_plan
from rpggen.errors import RpgGenError
from rpggen.errors_table import CODES

ALL = {"farm_size": "medium", "plot": "medium", "animals": "coop_and_barn"}


def _world(section: dict, seed: int = 7) -> dict:
    """A world plan with the crops of a farm and its map beside them."""
    return farm_plan.attach(crop_plan.world(crop_plan.plan({}, seed), seed), section)


def _cells(rows: list) -> set[tuple[int, int]]:
    return {(c[0], c[1]) for c in rows}


def test_the_plan_is_the_same_for_the_same_seed_and_fits_the_schema() -> None:
    first = farm_plan.plan(ALL, 12345)
    assert first == farm_plan.plan(ALL, 12345)
    assert first != farm_plan.plan(ALL, 12346)
    assert farm_plan.check(first) == []
    schema.validate("world_plan", _world(first))
    assert (first["id"], first["map"], first["seed"]) == ("farm", "game/maps/farm.tscn", 12345)
    assert first["size"] == [40, 30] and len(first["tillable"]) == 96
    assert [b["kind"] for b in first["animal_houses"]] == ["coop", "barn"]
    assert first["notes"] == [] and first["added_maps"] == []
    # nothing in the plan is a place on the screen: every number of it is a whole number
    todo: list = [first]
    while todo:
        value = todo.pop()
        assert not isinstance(value, float), "a plan of cells has no pixel positions"
        todo.extend(value.values() if isinstance(value, dict) else [])
        todo.extend(value if isinstance(value, list) else [])


def test_the_options_have_defaults_and_say_what_is_wrong() -> None:
    assert farm_plan.defaults() == {
        "farm_size": "medium",
        "plot": "medium",
        "animals": "none",
        "difficulty": "normal",
        "added_maps": [],
    }
    # the section holds the village's options too: they are not the farm's and not looked at
    village = {"size": [40, 24], "buildings": 2, "ground": ""}
    assert farm_plan.normalized(village) == farm_plan.defaults()
    assert farm_plan.normalized(None) == farm_plan.defaults()
    assert farm_plan.normalized({"added_maps": ["Beach", {"name": " Cave "}]})["added_maps"] == [
        {"name": "Beach"},
        {"name": "Cave"},
    ]
    for key in ("farm_size", "plot", "animals", "difficulty"):
        with pytest.raises(farm_plan.FarmPlanError, match=f"{key} must be one of"):
            farm_plan.normalized({key: "huge"})
    with pytest.raises(farm_plan.FarmPlanError, match="two added maps are called"):
        farm_plan.normalized({"added_maps": ["Beach", "beach"]})
    with pytest.raises(farm_plan.FarmPlanError, match="needs a name"):
        farm_plan.normalized({"added_maps": [{"name": " "}]})
    with pytest.raises(farm_plan.FarmPlanError, match="at most 8"):
        farm_plan.normalized({"added_maps": [str(n) for n in range(9)]})
    assert farm_plan.describe({"animals": "coop"}) == "a medium farm with a medium plot, a coop"


@pytest.mark.parametrize("size", list(farm_plan.SIZES))
@pytest.mark.parametrize("plot", list(farm_plan.PLOTS))
def test_every_size_of_field_and_plot_is_what_the_options_say(size: str, plot: str) -> None:
    section = farm_plan.plan({"farm_size": size, "plot": plot}, 3)
    assert tuple(section["size"]) == farm_plan.SIZES[size]
    wide, high = farm_plan.PLOTS[plot]
    assert len(section["tillable"]) == wide * high >= farm_plan.MIN_PLOT
    assert (section["farm_size"], section["plot"], section["animals"]) == (size, plot, "none")
    assert section["animal_houses"] == []
    assert farm_plan.summary(section) == (
        f"a farm of {section['size'][0]} x {section['size'][1]} with a plot of {wide * high} "
        "cells, a pond"
    )


def test_what_stands_on_a_farm_is_where_the_card_says() -> None:
    section = farm_plan.plan(ALL, 21)
    cols, rows = section["size"]
    house = section["house"]
    x, y, w, h = house["rect"]
    assert house["kind"] == "house" and house["id"] == "farm_house"
    assert house["door"][1] == y + h and x <= house["door"][0] < x + w, "before its bottom row"
    # the bin stands against a side of the house, in its bottom row
    bx, by = section["bin"]["cell"]
    assert by == y + h - 1 and bx in (x - 1, x + w)
    assert section["bin"]["front"] == [bx, by + 1]
    # the room of the house: walls round it, a way out in the bottom wall, the bed, the start
    room = house["interior"]
    assert room["id"] == "farm_house" and room["door"][1] == room["size"][1] - 1
    assert room["arrive"] == [room["door"][0], room["door"][1] - 1]
    assert room["bed"] == {"cell": [1, 1], "size": [1, 2]}
    assert section["start"] == {"map": "farm_house", "cell": room["start"], "facing": "down"}
    # the water and where the can is filled
    assert section["water"]["kind"] == "pond" and len(section["water"]["cells"]) >= 4
    fx, fy = section["water"]["fill"]
    assert [fx, fy - 1] in section["water"]["cells"]
    # every animal house: a building, a room with a trough and stalls, a yard, a fence, a gate
    for building in section["animal_houses"]:
        kind = building["kind"]
        bx, by, bw, bh = building["rect"]
        yard = building["yard"]
        inside = _cells(farm_plan._rect_cells(yard["rect"]))
        assert tuple(building["door"]) in inside, "an animal house opens into its yard"
        assert building["interior"]["id"] == building["id"] == f"farm_{kind}"
        assert len(building["interior"]["stalls"]) == farm_plan.STALLS[kind]
        assert building["interior"]["trough"] == [1, 1]
        fence, gate = _cells(yard["fence"]), tuple(yard["gate"])
        assert gate not in fence and not fence & inside
        # the fence, the gate and the wall of the building close the yard
        closed = fence | {gate} | _cells(farm_plan._rect_cells(building["rect"]))
        for cx, cy in inside:
            for nxt in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                assert nxt in inside or nxt in closed
        assert yard["side"] in ("S", "E", "W")
    # the way out is a gap in the edge, the farmer arrives one cell inside it
    way_out = section["exit"]
    ex, ey = way_out["cell"]
    assert way_out["to"] == "starter_map" and way_out["edge"] in farm_plan.EXIT_EDGES
    assert ex in (0, cols - 1) or ey == rows - 1
    assert way_out["facing"] == {"E": "left", "S": "up", "W": "right"}[way_out["edge"]]
    assert abs(way_out["spawn"][0] - ex) + abs(way_out["spawn"][1] - ey) == 1
    # the paths lead from the door to the way out, and nothing lies on them
    paths = _cells(section["paths"])
    assert section["paths"][0] == house["door"] and section["paths"][-1] == way_out["cell"]
    assert tuple(way_out["spawn"]) in paths and tuple(section["water"]["fill"]) in paths
    assert not paths & farm_plan.blocked_cells(section)
    # trees at the edges; things to clear on the plot and round it
    assert section["trees"] and all(
        min(tx, ty, cols - 1 - tx, rows - 1 - ty) in (1, 2) for tx, ty in section["trees"]
    )
    plot = _cells(section["tillable"])
    on_plot = [d for d in section["debris"] if tuple(d["cell"]) in plot]
    assert on_plot and len(on_plot) < len(section["debris"])
    assert {d["kind"] for d in section["debris"]} == set(farm_plan.DEBRIS)
    assert {s["kind"] for s in section["scenery"]} <= set(farm_plan.SCENERY)


def test_there_is_more_to_clear_on_a_harder_game_and_a_larger_field() -> None:
    def cleared(**options: str) -> float:
        plans = [farm_plan.plan(options, seed) for seed in range(12)]
        return sum(len(p["debris"]) for p in plans) / len(plans)

    assert cleared(difficulty="easy") < cleared(difficulty="normal") < cleared(difficulty="hard")
    assert cleared(farm_size="small", plot="small") < cleared(farm_size="large", plot="small")


def test_the_packs_say_how_large_the_house_is_and_whether_there_is_water() -> None:
    facts = farm_plan.facts_of({"size": [8, 5], "door": [5, 5]}, water=False)
    assert facts == {"water": False, "house": {"size": [8, 5], "door": [5, 5]}}
    section = farm_plan.plan({"animals": "coop"}, 5, facts)
    x, y, w, h = section["house"]["rect"]
    assert (w, h) == (8, 5) and section["house"]["door"] == [x + 5, y + 5]
    assert section["house"]["interior"]["size"] == [10, 7]
    assert section["water"]["kind"] == "well" and len(section["water"]["cells"]) == 1
    assert farm_plan.summary(section).endswith("a plot of 96 cells, a well, a coop")
    assert farm_plan.check(section) == []
    # a building the size of a town hall is cut to what a field can hold
    huge = farm_plan.plan({}, 5, {"building": {"size": [30, 20], "door": [40, 20]}})
    assert huge["house"]["rect"][2:] == [10, 8] and farm_plan.check(huge) == []


@pytest.mark.parametrize("size", list(farm_plan.SIZES))
@pytest.mark.parametrize("animals", list(farm_plan.ANIMALS))
def test_every_farm_of_forty_seeds_can_be_worked(size: str, animals: str) -> None:
    for seed in range(40):
        plot = tuple(farm_plan.PLOTS)[seed % 3]
        difficulty = farm_plan.DIFFICULTIES[(seed // 3) % 3]
        options = {"farm_size": size, "plot": plot, "animals": animals, "difficulty": difficulty}
        section = farm_plan.plan(options, seed, {"water": seed % 5 != 0})
        assert farm_plan.check(section) == [], (seed, options)
        assert len(section["tillable"]) >= farm_plan.MIN_PLOT
        assert len(section["animal_houses"]) == len(farm_plan.ANIMALS[animals])
        reached = farm_plan.reached_cells(section)
        assert tuple(section["exit"]["cell"]) in reached
        assert tuple(section["water"]["fill"]) in reached
        assert tuple(section["bin"]["front"]) in reached
        for building in section["animal_houses"]:
            assert tuple(building["door"]) in reached


def test_a_field_too_small_for_its_plot_gets_a_smaller_one_and_says_so() -> None:
    # a pack whose coop is twice the usual one leaves a small field little room
    options = {"farm_size": "small", "plot": "large", "animals": "coop_and_barn"}
    section = farm_plan.plan(options, 0, {"coop": {"size": [8, 6], "door": [2, 6]}})
    assert section["size"] == [32, 24] and section["animal_houses"][0]["rect"][2:] == [8, 6]
    assert farm_plan.MIN_PLOT <= len(section["tillable"]) < 160
    assert section["notes"] == [
        "The plot is 12 x 10: the field has no room for 16 x 10 beside what else stands on it."
    ]
    assert section["plot"] == "large", "what was asked for stays in the plan"
    assert farm_plan.check(section) == []
    # and buildings no small field can hold at all get the next larger one
    big = {"size": [10, 8], "door": [5, 8]}
    section = farm_plan.plan(options, 0, {"house": big, "coop": big, "barn": big})
    assert section["size"] == [40, 30] and section["farm_size"] == "medium"
    assert section["notes"] == [
        "The field is medium: a small one has no room for the buildings of the packs."
    ]
    assert len(section["tillable"]) == 160 and farm_plan.check(section) == []
    assert farm_plan._smaller((4, 3)) is None, "a plot never has fewer than twelve cells"


def _ring(rect: list[int]) -> list[list[int]]:
    """The cells round a rectangle."""
    x0, y0, w, h = rect
    around = farm_plan._rect_cells((x0 - 1, y0 - 1, w + 2, h + 2))
    return [[x, y] for x, y in around if not (x0 <= x < x0 + w and y0 <= y < y0 + h)]


def _plot_rect(section: dict) -> list[int]:
    xs = [c[0] for c in section["tillable"]]
    ys = [c[1] for c in section["tillable"]]
    return [min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1]


def _bare(seed: int = 4) -> dict:
    """A farm with a coop and nothing lying about, to break by hand."""
    section = farm_plan.plan({"animals": "coop"}, seed)
    section.update(paths=[], debris=[], trees=[], scenery=[])
    assert farm_plan.check(section) == []
    return section


def test_the_check_rejects_a_plot_that_is_walled_in() -> None:
    section = _bare()
    section["trees"] = _ring(_plot_rect(section))
    assert farm_plan.check(section) == ["the plot cannot be reached from the house"]
    # one tree less and the farmer is through
    x, y, _w, _h = _plot_rect(section)
    section["trees"].remove([x, y - 1])
    assert farm_plan.check(section) == []


def test_the_check_rejects_a_bin_and_water_that_cannot_be_reached() -> None:
    section = _bare()
    bx, by = section["bin"]["cell"]
    house = _cells(farm_plan._rect_cells(section["house"]["rect"]))
    section["scenery"] = [
        {"kind": "rock", "cell": [x, y]}
        for x, y in ((bx - 1, by), (bx + 1, by), (bx, by - 1), (bx, by + 1))
        if (x, y) not in house
    ]
    assert farm_plan.check(section) == ["the shipping bin cannot be reached from the house"]
    # flowers are walked over
    for thing in section["scenery"]:
        thing["kind"] = "flowers"
    assert farm_plan.check(section) == []

    section = _bare()
    water = _cells(section["water"]["cells"])
    shore = {
        (x + dx, y + dy) for x, y in water for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
    } - water
    section["debris"] = [{"kind": "stump", "cell": [x, y]} for x, y in sorted(shore)]
    assert farm_plan.check(section) == ["the water cannot be reached from the house"]
    section["debris"] = [{"kind": "stump", "cell": section["water"]["fill"]}]
    assert farm_plan.check(section) == ["the can cannot be filled where the plan says"]
    section["debris"] = []
    section["water"]["cells"] = []
    assert farm_plan.check(section) == ["there is no water to fill the can"]


def test_the_check_rejects_a_yard_without_a_gate() -> None:
    section = _bare()
    yard = section["animal_houses"][0]["yard"]
    gate = yard.pop("gate")
    assert farm_plan.check(section) == ["the yard of the coop has no gate"]
    schema.validate("world_plan", _world(section))  # a plan may be broken and still be read
    # a fence where the gate was: there is a gate in the plan, and no way through it
    yard["gate"] = gate
    step = {"S": (0, 1), "E": (1, 0), "W": (-1, 0)}[yard["side"]]
    section["trees"] = [[gate[0] + step[0], gate[1] + step[1]]]
    assert farm_plan.check(section) == ["the yard of the coop cannot be reached from the house"]


def test_the_check_rejects_a_plot_of_eleven_cells() -> None:
    section = _bare()
    section["tillable"] = section["tillable"][:11]
    assert farm_plan.check(section) == ["the plot has 11 cells, 12 are needed"]
    section["tillable"] = section["tillable"][:1]
    assert farm_plan.check(section) == ["the plot has 1 cell, 12 are needed"]
    section = _bare()
    section["tillable"] = section["tillable"][:12]
    assert farm_plan.check(section) == []


def test_the_check_rejects_what_lies_on_something_else() -> None:
    section = _bare()
    section["water"]["cells"].append(section["tillable"][0])
    assert farm_plan.check(section) == [f"the plot overlaps the water at {section['tillable'][0]}"]

    section = _bare()
    section["trees"] = [section["bin"]["cell"]]
    assert farm_plan.check(section) == [
        f"a tree overlaps the shipping bin at {section['bin']['cell']}"
    ]

    section = _bare()
    x, y, _w, _h = section["animal_houses"][0]["rect"]
    section["tillable"].append([x, y])
    assert farm_plan.check(section) == [f"the plot overlaps the coop at {[x, y]}"]

    # a thing to clear lies on the plot and on bare ground, and nowhere else
    section = _bare()
    section["debris"] = [{"kind": "grass", "cell": section["tillable"][5]}]
    assert farm_plan.check(section) == []
    section["debris"].append({"kind": "grass", "cell": section["tillable"][5]})
    assert farm_plan.check(section) == [f"two things to clear lie at {section['tillable'][5]}"]
    section["debris"] = [{"kind": "grass", "cell": section["water"]["cells"][0]}]
    assert farm_plan.check(section) == [
        f"a thing to clear (grass) overlaps the water at {section['water']['cells'][0]}"
    ]

    section = _bare()
    section["trees"] = [[section["size"][0] + 2, 3]]
    assert farm_plan.check(section) == [f"a tree is outside the field at {section['trees'][0]}"]

    section = _bare()
    section["exit"]["cell"] = section["exit"]["spawn"]
    found = farm_plan.check(section)
    assert found[0].startswith("the way out is not at the edge of the field")


def test_the_check_rejects_a_way_out_and_a_bed_that_cannot_be_reached() -> None:
    section = _bare()
    section["trees"] = [section["exit"]["spawn"]]
    assert farm_plan.check(section) == ["the way out cannot be reached from the house"]

    section = _bare()
    section["trees"] = [section["house"]["door"]]
    found = farm_plan.check(section)
    assert found[-1] == "the door of the house is blocked" and len(found) == 2

    section = _bare()
    section["start"]["cell"] = [1, 1]
    assert farm_plan.check(section) == ["the farmer does not start on the floor of the house"]
    section["start"]["cell"] = [4, 4]
    assert farm_plan.check(section) == ["the farmer does not start by the bed"]
    section = _bare()
    section["house"]["interior"]["bed"]["cell"] = [0, 0]
    assert farm_plan.check(section) == ["the bed is not in the room of the house"]
    del section["house"]["interior"]["bed"]
    assert farm_plan.check(section) == ["the house has no bed"]


def test_a_farm_that_cannot_be_worked_is_planned_again_with_the_next_seed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real = farm_plan.check
    monkeypatch.setattr(
        farm_plan, "check", lambda s: [] if len(s["trees"]) % 2 else ["an even number of trees"]
    )

    def trees(seed: int) -> int:
        farm = farm_plan._farm(farm_plan.defaults(), seed, {})
        assert farm is not None
        return len(farm["trees"])

    seed = next(s for s in range(50) if trees(s) % 2 == 0)
    section = farm_plan.plan({}, seed)
    took = int(section["notes"][-1].removeprefix("The farm was planned with seed ").rstrip("."))
    assert section["seed"] == seed < took and len(section["trees"]) % 2 == 1
    assert real(section) == []
    assert trees(took) == len(section["trees"])
    # and when no seed makes one, the planner says what was in the way
    monkeypatch.setattr(farm_plan, "check", lambda s: ["the plot cannot be reached"])
    with pytest.raises(farm_plan.FarmPlanError, match="no farm that can be worked: the plot"):
        farm_plan.plan({}, seed)


def test_added_maps_are_names_and_a_project_keeps_the_farm_it_stored(tmp_path: Path) -> None:
    stored = farm_plan.plan({"added_maps": ["Beach"]}, 8)
    assert stored["added_maps"] == ["Beach"]
    grown, added = farm_plan.extend(stored, [{"name": "beach"}, {"name": "Forest"}, "Cave"])
    assert added == ["Forest", "Cave"] and grown["added_maps"] == ["Beach", "Forest", "Cave"]
    without = {k: v for k, v in grown.items() if k != "added_maps"}
    assert without == {k: v for k, v in stored.items() if k != "added_maps"}, "the farm stays"
    assert farm_plan.extend(grown, [{"name": "CAVE"}]) == (grown, [])
    with pytest.raises(farm_plan.FarmPlanError, match="8 added maps at most"):
        farm_plan.extend(grown, [str(n) for n in range(6)])

    # a project: a fresh plan first, then the stored one, whatever the options and the seed say
    project = tmp_path / "game"
    project.mkdir()
    first, notes = farm_plan.for_project(project, {"added_maps": ["Beach"]}, 8)
    assert notes == [] and first == stored
    world = _world(first, 8)
    assert farm_plan.stored_in(world) == first and len(world["farm"]["crops"]) == 3
    world_plan.save(project, world)
    assert world_plan.load(project) == world, "the stored plan round-trips"
    assert not farm_plan.exists(project), "the farm's map has not been built yet"
    again, _notes = farm_plan.for_project(project, {"farm_size": "large"}, 9)
    assert again["size"] == [48, 36], "until it is, the options and the seed still count"
    (project / "game" / "maps").mkdir(parents=True)
    (project / farm_plan.MAP_FILE).write_text("[gd_scene]\n", encoding="utf-8")
    assert farm_plan.exists(project)
    kept, notes = farm_plan.for_project(
        project, {"farm_size": "large", "animals": "coop", "added_maps": ["Beach", "Cave"]}, 4711
    )
    assert notes == ["The farm kept its plan; added: Cave."]
    assert kept["added_maps"] == ["Beach", "Cave"] and kept["house"] == stored["house"]
    assert kept["size"] == [40, 30] and kept["animal_houses"] == []
    kept_world = farm_plan.attach(world, kept)
    schema.validate("world_plan", kept_world)
    assert kept_world["farm"]["crops"] == world["farm"]["crops"], "the crops are not touched"
    assert farm_plan.for_project(project, {}, 1) == (stored, [])

    # the crops own the section: a world plan without it cannot take the map
    with pytest.raises(farm_plan.FarmPlanError, match="plan the crops first"):
        farm_plan.attach({"world_plan_version": 1, "areas": []}, first)
    assert farm_plan.stored_in(None) is None and not farm_plan.exists(tmp_path / "nothing")


def test_the_schema_knows_the_map_of_a_farm() -> None:
    section = farm_plan.plan(ALL, 5)
    world = _world(section)
    schema.validate("world_plan", world)
    for broken in (
        lambda s: s.update(size=[40.5, 30]),
        lambda s: s["house"].update(position=[120.0, 64.0]),
        lambda s: s["debris"].append({"kind": "boulder", "cell": [3, 3]}),
        lambda s: s["animal_houses"][0].update(kind="stable"),
        lambda s: s.pop("tillable"),
        lambda s: s["exit"].update(edge="up"),
    ):
        bad = copy.deepcopy(world)
        broken(bad["farm"]["map"])
        with pytest.raises(RpgGenError):
            schema.validate("world_plan", bad)
    # a farm whose map has not been planned yet (T17.05 alone) is a plan as before
    schema.validate("world_plan", crop_plan.world(crop_plan.plan({}, 5), 5))


def test_val_031_is_a_warning_that_names_the_problem() -> None:
    assert CODES["VAL-031"].severity == "warning"
    assert "{problem}" in CODES["VAL-031"].message
    assert "farm.map" in CODES["VAL-031"].fix


def test_the_picture_of_a_farm_is_drawn_from_the_plan() -> None:
    section = farm_plan.plan(ALL, 7)
    cols, rows = section["size"]
    picture = map_preview.render_farm(section, scale=4)
    assert picture.size == (cols * 4, rows * 4)
    assert map_preview.render_farm(section).size == (cols * 8, rows * 8)
    colors = {color for _count, color in picture.getcolors(maxcolors=4096)}
    assert set(map_preview.FARM_COLORS.values()) == colors, "every kind of the legend is drawn"
    assert set(map_preview.FARM_ORDER) == set(map_preview.FARM_COLORS) - {"ground", "edge"}
    assert len(set(map_preview.FARM_COLORS.values())) == len(map_preview.FARM_COLORS)

    def at(cell: list[int]) -> tuple[int, int, int]:
        return picture.getpixel((cell[0] * 4 + 1, cell[1] * 4 + 1))  # type: ignore[return-value]

    shown = map_preview.FARM_COLORS
    assert at([0, 0]) == shown["edge"]
    assert at(section["exit"]["cell"]) == shown["exit"]
    assert at(section["house"]["door"]) == shown["door"]
    assert at(section["house"]["rect"][:2]) == shown["building"]
    assert at(section["bin"]["cell"]) == shown["bin"]
    assert at(section["water"]["cells"][0]) == shown["water"]
    assert at(section["trees"][0]) == shown["tree"]
    assert at(section["debris"][0]["cell"]) == shown["debris"]
    assert at(section["scenery"][0]["cell"]) == shown["scenery"]
    clear = _cells(section["tillable"]) - _cells([d["cell"] for d in section["debris"]])
    assert at(list(min(clear))) == shown["tillable"]
    for building in section["animal_houses"]:
        yard = building["yard"]
        assert at(yard["gate"]) == shown["gate"]
        assert at(yard["fence"][0]) == shown["fence"]
        assert at(building["door"]) == shown["door"]
        x, y, w, h = yard["rect"]
        assert at([x + w - 1, y + h - 1]) == shown["yard"]
    x, y, w, h = section["house"]["rect"]
    assert at([x + w // 2, y + h // 2]) == shown["start"]
    # the legend lists what is there
    counts = map_preview.farm_markers(section)
    assert list(counts) == list(map_preview.FARM_ORDER)
    assert counts["start"] == 1 and counts["exit"] == 1 and counts["gate"] == 2
    assert counts["bin"] == 1 and counts["door"] == 3 and counts["water"] >= 4
    assert map_preview.farm_markers(farm_plan.plan({}, 7))["gate"] == 0
    # the same plan, the same picture
    assert map_preview.render_farm(farm_plan.plan(ALL, 7), 4).tobytes() == picture.tobytes()
