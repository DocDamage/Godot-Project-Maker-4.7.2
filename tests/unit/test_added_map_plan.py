"""T17.23: the maps added to a farm. A row is a name and a kind; a forest and a beach are planned
on a grid of cells, once, and stored with the farm; the farm keeps places for their doors (its
trails) from the day it is planned; the check finds a map that cannot be walked; a beach brings
its own things to forage and the fish of the sea; the picture shows them beside the farm."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from rpggen import schema
from rpggen.core import (
    added_map_plan,
    catalog,
    crop_plan,
    farm_kit,
    farm_plan,
    forage_plan,
    map_preview,
    options,
    world_plan,
)

ROWS = [{"name": "Old woods"}, {"name": "North shore"}]


def _world(section: dict, seed: int = 7) -> dict:
    return farm_plan.attach(crop_plan.world(crop_plan.plan({}, seed), seed), section)


def _cells(rows: list) -> set[tuple[int, int]]:
    return {(c[0], c[1]) for c in rows}


# --------------------------------------------------------------------------- the rows


def test_the_kind_of_a_row_is_its_own_or_the_words_of_its_name() -> None:
    kind = added_map_plan.kind_of_name
    assert [kind(n) for n in ("Beach", "North shore", "The Coast", "Seaside")] == ["beach"] * 4
    assert [kind(n) for n in ("Forest", "Old woods", "Birch Grove", "wood")] == ["forest"] * 4
    assert kind("Map 3") == "forest" and kind("") == "forest", "anything else is a forest"
    assert kind("Beachcomber") == "forest", "a word, not a part of one"
    assert kind("Cave") == "forest", "no name chooses the kind that is not built yet"
    assert added_map_plan.row("Dunes") == {"name": "Dunes", "kind": "forest"}
    assert added_map_plan.row({"name": " Dunes ", "kind": "beach"}) == {
        "name": "Dunes",
        "kind": "beach",
    }
    assert added_map_plan.row({"name": "Old shore", "kind": ""})["kind"] == "beach"
    assert added_map_plan.kinds_of(
        [{"name": "A"}, {"name": ""}, "Bay", {"name": "C", "kind": "x"}]
    ) == [
        "forest",
        "beach",
    ]
    assert added_map_plan.BUILT == ("forest", "beach") and added_map_plan.RESERVED == ("cave",)
    assert set(added_map_plan.PLANNERS) == set(added_map_plan.BUILT)
    assert set(added_map_plan.SIZES) == set(added_map_plan.BUILT)


def test_a_row_that_cannot_be_a_map_says_why() -> None:
    with pytest.raises(added_map_plan.AddedMapError, match="needs a name"):
        added_map_plan.row({"name": "  "})
    with pytest.raises(added_map_plan.AddedMapError, match="Deep: .* kind cave is not built yet"):
        added_map_plan.row({"name": "Deep", "kind": "cave"})
    with pytest.raises(added_map_plan.AddedMapError, match="one of forest, beach, not swamp"):
        added_map_plan.row({"name": "Bog", "kind": "swamp"})
    # the farm's options say the same, as the config's check words it
    with pytest.raises(farm_plan.FarmPlanError, match="kind cave is not built yet"):
        farm_plan.normalized({"added_maps": [{"name": "Deep", "kind": "cave"}]})
    with pytest.raises(farm_plan.FarmPlanError, match="not swamp"):
        farm_plan.plan({"added_maps": [{"name": "Bog", "kind": "swamp"}]}, 3)
    # the config's schema offers the kinds that are built, and a row may name none
    text = (Path(schema.__file__).parent / "config.schema.json").read_text(encoding="utf-8")
    item = json.loads(text)["properties"]["starter_map"]["properties"]["added_maps"]["items"]
    assert item["properties"]["kind"]["enum"] == list(added_map_plan.BUILT)
    assert item["required"] == ["name"]
    assert farm_plan.describe({"added_maps": ROWS}) == (
        "a medium farm with a medium plot, a forest, a beach"
    )


# --------------------------------------------------------------------------- the plans


@pytest.mark.parametrize("kind", added_map_plan.BUILT)
def test_an_added_map_is_planned_on_cells_and_is_the_same_for_the_same_seed(kind: str) -> None:
    first = added_map_plan.plan(kind, 2, 12345, "Somewhere")
    assert first == added_map_plan.plan(kind, 2, 12345, "Somewhere")
    assert first != added_map_plan.plan(kind, 2, 12346, "Somewhere")
    assert first != {**added_map_plan.plan(kind, 3, 12345, "Somewhere"), "index": 2}
    assert (first["id"], first["map"]) == ("farm_map_2", "game/maps/farm_map_2.tscn")
    assert (first["kind"], first["name"], first["index"], first["seed"]) == (
        kind,
        "Somewhere",
        2,
        12345,
    )
    assert first["size"] == list(added_map_plan.SIZES[kind]) and first["ground"] == ""
    todo: list = [first]
    while todo:
        value = todo.pop()
        assert not isinstance(value, float), "a plan of cells has no pixel positions"
        todo.extend(value.values() if isinstance(value, dict) else [])
        todo.extend(value if isinstance(value, list) else [])
    for seed in range(60):
        entry = added_map_plan.plan(kind, 1, seed, "Somewhere")
        assert added_map_plan.check(entry) == [], seed
        reached = added_map_plan.reached_cells(entry)
        assert _cells(entry["spots"]) <= reached and len(entry["spots"]) >= 3
        assert not _cells(entry["spots"]) & added_map_plan.blocked_cells(entry)
        gap, spawn = entry["door"]["cell"], entry["door"]["spawn"]
        cols, rows = entry["size"]
        assert gap[0] in (0, cols - 1) or gap[1] in (0, rows - 1)
        assert abs(gap[0] - spawn[0]) + abs(gap[1] - spawn[1]) == 1
        assert entry["debris"], "something to clear lies on every added map"
    # the packs' ground for the kind, when they have one, is named in the plan
    sandy = added_map_plan.plan(kind, 1, 5, "Somewhere", {"grounds": {kind: "pack.tiles.own"}})
    assert sandy["ground"] == "pack.tiles.own"
    assert {**sandy, "ground": ""} == added_map_plan.plan(kind, 1, 5, "Somewhere")


def test_a_forest_is_thick_with_trees_and_has_a_clearing_with_a_path_to_it() -> None:
    for seed in range(30):
        forest = added_map_plan.plan("forest", 1, seed, "Woods")
        cols, rows = forest["size"]
        inside = (cols - 2) * (rows - 2)
        assert len(forest["trees"]) > inside // 4, "denser than a farm ever is"
        x0, y0, wide, high = forest["clearing"]
        clearing = {(x, y) for x in range(x0, x0 + wide) for y in range(y0, y0 + high)}
        assert not clearing & _cells(forest["trees"]), "no tree stands in the clearing"
        path = _cells(forest["paths"])
        assert tuple(forest["door"]["spawn"]) in path and path & clearing
        assert not path & added_map_plan.blocked_cells(forest), "nothing stands on the path"
        assert "water" not in forest and "fish" not in forest
        farm = farm_plan.plan({"farm_size": "medium"}, seed)
        farm_inside = (farm["size"][0] - 2) * (farm["size"][1] - 2)
        assert len(forest["trees"]) / inside > 2 * len(farm["trees"]) / farm_inside


def test_a_beach_has_the_sea_along_one_side_and_a_place_to_fish_from() -> None:
    sides = set()
    for seed in range(40):
        beach = added_map_plan.plan("beach", 1, seed, "Shore")
        cols, rows = beach["size"]
        wet = _cells(beach["water"]["cells"])
        side = beach["water"]["side"]
        sides.add(side)
        assert beach["water"]["kind"] == "sea" and beach["door"]["edge"] != side
        edge = {
            "N": {(x, 0) for x in range(cols)},
            "S": {(x, rows - 1) for x in range(cols)},
            "W": {(0, y) for y in range(rows)},
            "E": {(cols - 1, y) for y in range(rows)},
        }[side]
        assert edge <= wet, "the sea reaches the edge of the map all along its side"
        assert len(wet) >= 3 * len(edge) and len(wet) <= 5 * len(edge)
        stand, cast = tuple(beach["fish"]["from"]), tuple(beach["fish"]["at"])
        assert cast in wet and stand not in wet
        assert abs(stand[0] - cast[0]) + abs(stand[1] - cast[1]) == 1
        assert stand in added_map_plan.reached_cells(beach)
        assert tuple(beach["door"]["cell"]) not in wet and beach["paths"] == []
        assert added_map_plan.has_sea([beach]) and not added_map_plan.has_sea([])
    assert len(sides) >= 3, "the sea is not always on the same side"


def test_the_check_rejects_maps_that_were_broken_by_hand() -> None:
    forest = added_map_plan.plan("forest", 1, 11, "Woods")
    beach = added_map_plan.plan("beach", 2, 11, "Shore")
    assert added_map_plan.check(forest) == [] and added_map_plan.check(beach) == []

    # a forage place walled in by trees
    walled = copy.deepcopy(forest)
    spot = walled["spots"][0]
    ring = [[spot[0] + dx, spot[1] + dy] for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy]
    taken = _cells(walled["paths"]) | {tuple(walled["door"]["spawn"])} | _cells(walled["spots"])
    for key in ("scenery", "debris"):
        walled[key] = [t for t in walled[key] if t["cell"] not in ring]
    walled["trees"] = [c for c in walled["trees"] if c not in ring]
    walled["trees"] += [c for c in ring if tuple(c) not in taken]
    if not any(tuple(c) in taken for c in ring):
        assert f"the forage place {spot} cannot be reached from the way in" in added_map_plan.check(
            walled
        )

    # a tree on the way in, two things on one cell, a thing outside the map
    blocked = copy.deepcopy(forest)
    blocked["trees"].append(list(blocked["door"]["spawn"]))
    found = added_map_plan.check(blocked)
    assert any("overlaps where the farmer arrives" in p for p in found)
    assert "the way in is blocked" in found
    double = copy.deepcopy(forest)
    double["scenery"].append({"kind": "rock", "cell": list(double["debris"][0]["cell"])})
    assert any("overlaps" in p for p in added_map_plan.check(double))
    outside = copy.deepcopy(forest)
    outside["spots"].append([99, 99])
    assert any("is outside the map" in p for p in added_map_plan.check(outside))

    # the way in away from the edge; nowhere to arrive
    inland = copy.deepcopy(forest)
    inland["door"]["cell"] = [5, 5]
    assert any("the way in is not at the edge" in p for p in added_map_plan.check(inland))
    assert added_map_plan.check({**forest, "door": {}}) == ["there is no way in"]

    # a beach: its sea gone, its fishing place inland, or behind rocks
    dry = copy.deepcopy(beach)
    dry["water"]["cells"] = []
    assert "the beach has no sea" in added_map_plan.check(dry)
    inland = copy.deepcopy(beach)
    door = inland["door"]["spawn"]
    inland["fish"]["from"] = [door[0], door[1]]
    assert "the place to fish from is not beside the sea" in added_map_plan.check(inland)
    cut = copy.deepcopy(beach)
    stand = cut["fish"]["from"]
    wet = _cells(cut["water"]["cells"])
    cut["scenery"] = [t for t in cut["scenery"] if abs(t["cell"][0] - stand[0]) > 2]
    cut["debris"] = [t for t in cut["debris"] if abs(t["cell"][0] - stand[0]) > 2]
    cut["spots"] = []
    cut["scenery"] += [
        {"kind": "rock", "cell": [stand[0] + dx, stand[1] + dy]}
        for dx, dy in ((0, 1), (1, 0), (-1, 0), (0, -1))
        if (stand[0] + dx, stand[1] + dy) not in wet
    ]
    assert "the place to fish from cannot be reached from the way in" in added_map_plan.check(cut)
    assert "the beach has no place to fish from" in added_map_plan.check({**beach, "fish": {}})


# --------------------------------------------------------------------------- the farm's side


def test_a_farm_keeps_places_for_the_doors_whether_or_not_it_has_added_maps() -> None:
    for seed in range(40):
        for size in farm_plan.SIZES:
            farm = farm_plan.plan({"farm_size": size, "animals": "coop_and_barn"}, seed)
            assert farm["added"] == [] and farm["added_maps"] == []
            trails = farm["trails"]
            assert 3 <= len(trails) <= farm_plan.TRAILS == farm_plan.MAX_ADDED
            assert farm_plan.check(farm) == []
            cols, rows = farm["size"]
            reached = farm_plan.reached_cells(farm)
            for trail in trails:
                x, y = trail["cell"]
                assert min(x, y, cols - 1 - x, rows - 1 - y) == 1, "beside the edge"
                assert abs(x - trail["spawn"][0]) + abs(y - trail["spawn"][1]) == 1
                assert (x, y) in reached and tuple(trail["spawn"]) in reached
            cells = farm_plan._trail_cells(farm)
            assert len(cells) == 2 * len(trails), "no two trails share a cell"
            # nothing of the farm, and no place where a thing to forage lies, is on a trail
            assert not cells & _cells(forage_plan.spots_for(farm, seed))
            assert not cells & _cells(farm["paths"]) and not cells & _cells(farm["tillable"])
            # the farm is the farm it was before it had trails: they are chosen after it
            plain = farm_plan._farm(
                farm_plan.normalized({"farm_size": size, "animals": "coop_and_barn"}), seed, {}
            )
            assert plain is not None
            for key in plain:
                if key not in ("seed", "added_maps", "notes"):
                    assert farm[key] == plain[key], key
    assert farm_plan.plan({}, 9)["trails"] == farm_plan.plan({}, 9)["trails"]
    assert farm_plan.plan({}, 9)["trails"] != farm_plan.plan({}, 10)["trails"]


def test_the_check_of_the_farm_covers_the_way_to_every_added_map() -> None:
    farm = farm_plan.plan({"added_maps": ROWS}, 21)
    assert farm_plan.check(farm) == []
    assert [e["trail"] for e in farm["added"]] == [0, 1]
    schema.validate("world_plan", _world(farm))

    # a trail walled in by trees
    walled = copy.deepcopy(farm)
    trail = walled["trails"][0]
    taken = farm_plan._trail_cells(walled) | _cells(walled["paths"])
    ring = {
        (c[0] + dx, c[1] + dy)
        for c in (trail["cell"], trail["spawn"])
        for dx in (-1, 0, 1)
        for dy in (-1, 0, 1)
    } - {tuple(trail["cell"]), tuple(trail["spawn"])}
    walled["trees"] = [c for c in walled["trees"] if tuple(c) not in taken]
    walled["scenery"] = [t for t in walled["scenery"] if tuple(t["cell"]) not in ring]
    walled["debris"] = [t for t in walled["debris"] if tuple(t["cell"]) not in ring]
    walled["trees"] += [list(c) for c in ring if c not in _cells(walled["trees"])]
    assert "trail 1 cannot be reached from the house" in farm_plan.check(walled)

    # a thing on a trail, a trail away from the edge, two maps on one trail, a broken map
    littered = copy.deepcopy(farm)
    littered["scenery"].append({"kind": "rock", "cell": list(trail["spawn"])})
    assert any("trail 1 overlaps scenery (rock)" in p for p in farm_plan.check(littered))
    moved = copy.deepcopy(farm)
    moved["trails"][1]["cell"] = list(moved["house"]["door"])
    assert any("trail 2 is not beside the edge" in p for p in farm_plan.check(moved))
    shared = copy.deepcopy(farm)
    shared["added"][1]["trail"] = 0
    assert "North shore has no trail of its own on the farm" in farm_plan.check(shared)
    broken = copy.deepcopy(farm)
    broken["added"][1]["water"]["cells"] = []
    assert "North shore: the beach has no sea" in farm_plan.check(broken)
    schema.validate("world_plan", _world(broken))  # a plan may be broken and still be read


def test_a_new_row_plans_one_more_map_and_leaves_the_stored_ones_byte_for_byte(
    tmp_path: Path,
) -> None:
    project = tmp_path / "game"
    (project / "game" / "maps").mkdir(parents=True)
    first, notes = farm_plan.for_project(project, {"added_maps": [ROWS[0]]}, 31)
    assert notes == [] and [e["name"] for e in first["added"]] == ["Old woods"]
    world_plan.save(project, _world(first, 31))
    (project / farm_plan.MAP_FILE).write_text("[gd_scene]\n", encoding="utf-8")
    before = json.dumps(farm_plan.stored_in(world_plan.load(project)), sort_keys=True)

    # the same options again: nothing is planned
    again, notes = farm_plan.for_project(project, {"added_maps": [ROWS[0]]}, 99)
    assert notes == [] and json.dumps(again, sort_keys=True) == before

    # a second row, another seed, a pack that has gained sand, the first row's kind changed
    rows = [{"name": "Old woods", "kind": "beach"}, ROWS[1], {"name": "Far grove"}]
    grown, notes = farm_plan.for_project(
        project, {"added_maps": rows, "farm_size": "large"}, 4711, {"grounds": {"beach": "sand"}}
    )
    assert notes == ["The farm kept its plan; added: North shore, Far grove."]
    assert [(e["id"], e["kind"], e["trail"]) for e in grown["added"]] == [
        ("farm_map_1", "forest", 0),
        ("farm_map_2", "beach", 1),
        ("farm_map_3", "forest", 2),
    ]
    assert grown["added"][1]["ground"] == "sand" and grown["added"][0]["ground"] == ""
    assert all(e["seed"] == 31 for e in grown["added"]), "the farm's seed, not the new one"
    kept = {k: v for k, v in grown.items() if k not in ("added", "added_maps")}
    was = json.loads(before)
    assert json.dumps(kept, sort_keys=True) == json.dumps(
        {k: v for k, v in was.items() if k not in ("added", "added_maps")}, sort_keys=True
    ), "the farm, its trails and its notes are what they were, byte for byte"
    assert json.dumps(grown["added"][0], sort_keys=True) == json.dumps(
        was["added"][0], sort_keys=True
    ), "the map that was stored is not planned again"
    assert grown["added_maps"] == ["Old woods", "North shore", "Far grove"]
    assert farm_plan.check(grown) == []
    schema.validate("world_plan", _world(grown, 31))
    # the map a row adds later is the one the farm would have had from the start
    whole = farm_plan.plan({"added_maps": [ROWS[0], ROWS[1], {"name": "Far grove"}]}, 31)
    assert whole["added"][2] == grown["added"][2]
    assert {**whole["added"][1], "ground": "sand"} == grown["added"][1]

    # a farm has as many added maps as it has trails
    few = copy.deepcopy(grown)
    few["trails"] = few["trails"][:3]
    with pytest.raises(farm_plan.FarmPlanError, match="Bay: the farm has room for 3 added maps"):
        farm_plan.extend(few, [{"name": "Bay"}])
    with pytest.raises(farm_plan.FarmPlanError, match="kind cave is not built yet"):
        farm_plan.extend(grown, [{"name": "Deep", "kind": "cave"}])


def test_a_farm_from_before_it_had_trails_keeps_a_new_row_as_a_name(tmp_path: Path) -> None:
    project = tmp_path / "game"
    (project / "game" / "maps").mkdir(parents=True)
    old = farm_plan.plan({}, 5)
    del old["trails"], old["added"]
    old["added_maps"] = ["Beach"]
    schema.validate("world_plan", _world(old, 5))
    world_plan.save(project, _world(old, 5))
    (project / farm_plan.MAP_FILE).write_text("[gd_scene]\n", encoding="utf-8")
    kept, notes = farm_plan.for_project(project, {"added_maps": ["Beach", "Forest"]}, 5)
    assert kept["added_maps"] == ["Beach", "Forest"] and "added" not in kept
    assert "trails" not in kept, "a map that exists gets no places for doors afterwards"
    assert {k: v for k, v in kept.items() if k != "added_maps"} == {
        k: v for k, v in old.items() if k != "added_maps"
    }
    assert notes == [
        "The farm kept its plan; added: Forest.",
        "The farm was made before added maps were built: Beach, Forest stay names (its map has "
        "no place for a door to another map, and a map that exists is not built again).",
    ]
    assert farm_plan.names_only(kept) == ["Beach", "Forest"]
    assert farm_plan.check(kept) == [] and farm_plan.summary(kept) == farm_plan.summary(old)
    assert options.added_maps_text(kept) == [
        "Beach: a name only (the farm was made before added maps were built)",
        "Forest: a name only (the farm was made before added maps were built)",
    ]
    assert not forage_plan.has_sea(kept)
    assert farm_plan.names_only(farm_plan.plan({"added_maps": ROWS}, 5)) == []


# --------------------------------------------------------------------------- forage and fish


def test_a_beach_brings_its_own_things_to_forage_and_the_fish_of_the_sea() -> None:
    plain = farm_plan.plan({}, 7)
    wooded = farm_plan.plan({"added_maps": [ROWS[0]]}, 7)
    shore = farm_plan.plan({"added_maps": ROWS}, 7)
    base = forage_plan.plan({}, 7, None, plain)
    assert forage_plan.plan({}, 7, None, wooded) == base, "a forest has what the farm has"
    section = forage_plan.plan({}, 7, None, shore)
    assert section["forage"][: len(base["forage"])] == base["forage"]
    assert section["fish"][: len(base["fish"])] == base["fish"]
    assert section["spots"] == base["spots"], "the farm's own places are what they were"
    things = section["forage"][len(base["forage"]) :]
    fish = section["fish"][len(base["fish"]) :]
    assert [(t["id"], t["maps"]) for t in things] == [
        ("forage_seaweed", ["beach"]),
        ("forage_shell", ["beach"]),
    ]
    assert [(f["id"], f["water"]) for f in fish] == [
        ("fish_sardine", ["sea"]),
        ("fish_sea_bass", ["sea"]),
    ]
    assert all("maps" not in t for t in base["forage"]) and all(
        f["water"] == ["pond"] for f in base["fish"]
    )
    for season in forage_plan.SEASONS:
        assert any(season in t["seasons"] for t in things), season
        for time in forage_plan.TIMES:
            assert any(season in f["seasons"] and time in f["times"] for f in fish), (season, time)
    assert forage_plan.check(section) == []
    schema.validate(
        "world_plan", {**_world(shore), "farm": {**_world(shore)["farm"], "forage": section}}
    )
    schema.validate("forage", forage_plan.forage_file(section))
    assert forage_plan.forage_file(section)["forage"][-1]["maps"] == ["beach"]

    # a stored plan gets them when the farm gets its first beach, once
    stored, notes = forage_plan.for_project(base, {}, 7, None, shore)
    assert notes == ["The farm kept its fish and forage; added: Seaweed, Shell, Sardine, Sea bass."]
    assert stored["forage"] == section["forage"] and stored["fish"] == section["fish"]
    assert forage_plan.for_project(stored, {}, 7, None, shore) == (stored, [])

    # the packs' own: an ITEM tagged for the beach, a fish tagged for the sea
    own = forage_plan.plan(
        {},
        7,
        {
            "forage": [],
            "fish": [],
            "beach": [{"asset": "p.conch", "name": "conch", "seasons": []}],
            "sea": [{"asset": "p.cod", "name": "cod"}],
        },
        shore,
    )
    assert [(t["id"], t["asset"]) for t in own["forage"] if t.get("maps")] == [
        ("forage_conch", "p.conch")
    ]
    assert set(next(t for t in own["forage"] if t.get("maps"))["seasons"]) == set(
        forage_plan.SEASONS
    )
    assert [(f["id"], f["water"]) for f in own["fish"] if f["water"] == ["sea"]] == [
        ("fish_cod", ["sea"])
    ]


def test_the_rod_is_sold_where_the_farm_has_a_pond_or_a_beach() -> None:
    well = farm_plan.plan({}, 7, {"water": False})
    beach = farm_plan.plan({"added_maps": [ROWS[1]]}, 7, {"water": False})
    assert well["water"]["kind"] == "well" == beach["water"]["kind"]
    assert not forage_plan.has_fish(well) and forage_plan.has_fish(beach)
    assert forage_plan.plan({}, 7, None, well)["fishing"] is False
    assert forage_plan.plan({}, 7, None, beach)["fishing"] is True
    assert forage_plan.plan({"fishing": False}, 7, None, beach)["fishing"] is False
    stored = forage_plan.plan({}, 7, None, well)
    grown, _notes = forage_plan.for_project(stored, {}, 7, None, beach)
    assert grown["fishing"] is True, "it follows the map on every generation"
    assert "the rod is sold" in forage_plan.summary(grown)


def _catalog(*assets: catalog.Asset) -> catalog.Catalog:
    return catalog.Catalog(assets=list(assets))


def test_the_kit_draws_what_a_beach_has_only_for_a_farm_with_a_beach(tmp_path: Path) -> None:
    empty = _catalog()
    plain = [s.name for s in farm_kit.lacking(empty)]
    assert not {"shell", "seaweed", "sardine", "sea_bass"} & set(plain)
    assert [s.name for s in farm_kit.lacking(empty, kinds=["forest"])] == plain
    with_beach = [s.name for s in farm_kit.lacking(empty, kinds=["forest", "beach", "beach"])]
    assert with_beach == [*plain, "shell", "seaweed", "sardine", "sea_bass"]
    added, issues = farm_kit.add(empty, 16, tmp_path, kinds=["beach"])
    assert added[-4:] == ["shell", "seaweed", "sardine", "sea_bass"]
    notes = [i.message for i in issues if i.code == "ASSET-031"]
    assert any("thing to forage on a beach (shell)" in n for n in notes)
    assert any("fish of the sea (sea bass)" in n for n in notes)
    facts = forage_plan.facts_of(empty)
    assert [f["name"] for f in facts["beach"]] == ["seaweed", "shell"]
    assert [f["name"] for f in facts["sea"]] == ["sardine", "sea_bass"]
    assert len(facts["forage"]) == 4 and len(facts["fish"]) == 3, "the farm's own are not theirs"
    for name in ("shell", "seaweed", "sardine", "sea_bass"):
        picture = tmp_path / farm_kit.KIT_DIR / f"{name}.png"
        assert picture.is_file()
    assert farm_kit.forage(16, "shell").getbbox() is not None
    assert farm_kit.forage(16, "shell").tobytes() != farm_kit.forage(16, "seaweed").tobytes()
    assert farm_kit.forage(32, "seaweed").size == (32, 32)
    # a farm without a beach has no such key: its facts are what they were
    bare = _catalog()
    farm_kit.add(bare, 16, tmp_path / "bare")
    assert set(forage_plan.facts_of(bare)) == {"forage", "fish"}


# --------------------------------------------------------------------------- in words, in a picture


def test_the_added_maps_are_named_in_words() -> None:
    farm = farm_plan.plan({"added_maps": ROWS, "animals": "coop"}, 7)
    assert farm_plan.summary(farm).endswith(", a coop, a forest (Old woods), a beach (North shore)")
    assert added_map_plan.summary(farm["added"]) == "a forest (Old woods) and a beach (North shore)"
    assert added_map_plan.summary([]) == ""
    assert options.added_maps_text(farm) == [
        "Old woods: a forest of 28 x 22 with 8 places to forage",
        "North shore: a beach of 30 x 20 with 6 places to forage and the sea to fish in",
    ]
    assert options.added_maps_text(farm_plan.plan({}, 7)) == []


def test_a_config_carries_the_rows_and_a_dry_run_names_the_maps() -> None:
    from rpggen.core import archive, config, dry_run, inventory
    from rpggen.errors import RpgGenError

    pack = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic" / "ranch"
    opened = archive.open_pack(pack, set())
    cat = catalog.assemble([(opened, inventory.build_inventory(opened))], None, [])[0]
    cfg = config.default_for("T", [config.pack_ref_from_source(pack, "ranch")], archetype="farm")
    cfg.starter_map["added_maps"] = [{"name": "Old woods"}, {"name": "Bay", "kind": "beach"}]
    again = config.GeneratorConfig.from_json(cfg.to_json())
    assert again.starter_map["added_maps"] == cfg.starter_map["added_maps"]
    plan = dry_run._plan(again, cat)
    assert plan["added_maps"] == [
        "Old woods: a forest of 28 x 22 with 8 places to forage",
        "Bay: a beach of 30 x 20 with 6 places to forage and the sea to fish in",
    ]
    assert ", a forest (Old woods), a beach (Bay), " in plan["farm"]
    # a kind that is not built is refused by the config's schema, and by the planner in words
    schema.validate("config", cfg.to_json())
    cfg.starter_map["added_maps"] = [{"name": "Deep", "kind": "cave"}]
    with pytest.raises(RpgGenError):
        schema.validate("config", cfg.to_json())
    assert "kind cave is not built yet" in " ".join(dry_run._plan(cfg, cat)["warnings"])
    # the requirement check notes what a beach needs drawn, for the dry run and the wizard
    from rpggen.core import requirements

    cfg.starter_map["added_maps"] = [{"name": "Bay"}]
    notes = [i.message for i in requirements.check(cat, cfg) if i.code == "ASSET-031"]
    assert sum("on a beach" in n or "of the sea" in n for n in notes) == 4, notes
    cfg.starter_map["added_maps"] = [{"name": "Woods"}]
    notes = [i.message for i in requirements.check(cat, cfg) if i.code == "ASSET-031"]
    assert not any("on a beach" in n or "of the sea" in n for n in notes)


def test_the_picture_shows_the_added_maps_beside_the_farm() -> None:
    plain = farm_plan.plan({}, 7)
    farm = farm_plan.plan({"added_maps": ROWS}, 7)
    alone = map_preview.render_farm(plain, scale=4)
    picture = map_preview.render_farm(farm, scale=4)
    cols, rows = farm["size"]
    forest, beach = farm["added"]
    assert alone.size == (cols * 4, rows * 4)
    assert picture.size == (
        cols * 4 + 4 + forest["size"][0] * 4 + 4 + beach["size"][0] * 4,
        rows * 4,
    )
    shown = {**map_preview.FARM_COLORS, **map_preview.ADDED_COLORS}
    # the farm is where it was, with the door of every trail that is used in the way out's colour
    for trail in farm["trails"][:2]:
        x, y = trail["cell"]
        assert picture.getpixel((x * 4 + 1, y * 4 + 1)) == shown["exit"]
    unused = farm["trails"][2]["cell"]
    assert picture.getpixel((unused[0] * 4 + 1, unused[1] * 4 + 1)) == shown["ground"]
    assert picture.crop((0, 0, cols * 4, rows * 4)).tobytes() != alone.tobytes()
    left = cols * 4 + 4

    def at(entry: dict, offset: int, cell: list[int]) -> tuple[int, int, int]:
        return picture.getpixel((offset + cell[0] * 4 + 1, cell[1] * 4 + 1))  # type: ignore[return-value]

    assert at(forest, left, [0, 0]) == shown["edge"]
    assert at(forest, left, forest["door"]["cell"]) == shown["exit"]
    assert at(forest, left, forest["trees"][0]) == shown["tree"]
    assert at(forest, left, forest["spots"][0]) == shown["forage"]
    assert at(forest, left, forest["paths"][-1]) == shown["path"]
    right = left + forest["size"][0] * 4 + 4
    assert at(beach, right, beach["water"]["cells"][0]) == shown["water"]
    assert at(beach, right, beach["fish"]["from"]) == shown["sand"]
    assert at(beach, right, beach["spots"][0]) == shown["forage"]
    one = map_preview.render_added(forest, scale=4)
    assert one.size == (forest["size"][0] * 4, forest["size"][1] * 4)
    colors = {color for _count, color in one.getcolors(maxcolors=4096)}
    assert shown["forest"] in colors and shown["sand"] not in colors
    # on diamonds too, and the farm's own picture is not what moved
    iso = map_preview.render_farm(farm, scale=4, footprint=(60, 34))
    iso_alone = map_preview.render_farm(plain, scale=4, footprint=(60, 34))
    assert iso.width > iso_alone.width and iso.height >= iso_alone.height
    assert map_preview.farm_cell_at(farm, 10, 10, 4) == (2, 2)
    assert set(map_preview.FARM_ORDER) == set(map_preview.FARM_COLORS) - {"ground", "edge"}
    assert not set(map_preview.ADDED_COLORS) & set(map_preview.FARM_COLORS)
