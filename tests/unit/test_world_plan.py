"""A world of connected maps (T13.20): the planner, the biomes and the stored plan."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from rpggen import jsonio, schema
from rpggen.core import archive, catalog, config, inventory, lockkey, profiles
from rpggen.core import world_plan as wp

REPO = Path(__file__).resolve().parents[2]
SAMPLE = REPO / "sample_pack"
SYNTH = REPO / "test_packs" / "synthetic"

AREAS = [
    {"name": "Village", "biome": "village"},
    {"name": "Meadow", "biome": "field"},
    {"name": "Woods", "biome": "forest", "size": [28, 22], "enemies": 3, "chests": 2},
    {"name": "Old mine", "biome": "cave", "size": [24, 18]},
    {"name": "Bay", "biome": "shore"},
]


@pytest.fixture(autouse=True)
def _cache(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))


def _catalog(pack: Path, pack_id: str) -> catalog.Catalog:
    opened = archive.open_pack(pack, set(), pack_id=pack_id)
    return catalog.assemble([(opened, inventory.build_inventory(opened))], None, [])[0]


# ------------------------------------------------------------------------ the table


def test_the_table_is_checked_and_put_into_its_canonical_form() -> None:
    rows = wp.normalized(
        [{"name": " Woods ", "biome": "forest"}, {"name": "Cave", "biome": "cave"}]
    )
    assert rows[0] == {
        "name": "Woods",
        "biome": "forest",
        "size": [32, 20],
        "enemies": 2,
        "chests": 1,
    }
    assert wp.village_index(rows) == 0, "without a village the first row is the starter map"
    assert wp.village_index(wp.normalized(AREAS)) == 0
    assert wp.village_index(wp.normalized(AREAS[1:] + AREAS[:1])) == 4
    for bad in (
        [],
        "areas",
        [{"biome": "field"}],
        [{"name": "A", "biome": "swamp"}],
        [{"name": "A", "biome": "field", "size": [8, 20]}],
        [{"name": "A", "biome": "field", "enemies": 99}],
        [{"name": "A", "biome": "field"}, {"name": "a", "biome": "cave"}],
        [{"name": f"A{i}", "biome": "field"} for i in range(13)],
    ):
        with pytest.raises(wp.WorldPlanError):
            wp.normalized(bad)
    schema.validate(
        "config",
        {
            **config.default_for("W", [config.PackRef("p", "x", "0" * 64, "folder")]).to_json(),
            "starter_map": {"areas": wp.normalized(AREAS)},
        },
    )
    assert wp.normalized(wp.default_areas())[1]["biome"] == "field"


# ------------------------------------------------------------------------ the plan


def test_the_plan_is_deterministic_and_valid() -> None:
    plan = wp.plan(AREAS, 7)
    assert plan == wp.plan(copy.deepcopy(AREAS), 7), "the same table and seed: the same world"
    assert plan != wp.plan(AREAS, 8)
    schema.validate("world_plan", plan)
    assert [a["id"] for a in plan["areas"]] == ["starter_map", "meadow", "woods", "old_mine", "bay"]
    assert plan["grid"]["starter_map"] == [0, 0], "the village is in the middle"
    assert plan["grid"]["meadow"] == [1, 0], "the first area lies east, where the road leads"
    assert len({tuple(c) for c in plan["grid"].values()}) == 5, "no two areas on one cell"
    assert wp.summary(plan) == (
        "5 areas: Village, Meadow (field), Woods (forest), Old mine (cave, locked), Bay (shore)"
    )
    village = wp.area_of(plan, "starter_map")
    assert village["size"] == [40, 30] and "chests" not in village, "its inside is the planner's"
    assert wp.plan(AREAS, 7, starter_size=(64, 40))["areas"][0]["size"] == [64, 40]


def test_doors_come_in_pairs_on_facing_edges() -> None:
    plan = wp.plan(AREAS, 7)
    by_id = {a["id"]: a for a in plan["areas"]}
    for area in plan["areas"]:
        w, h = area["size"]
        for door in area["doors"]:
            other = by_id[door["to"]]
            back = next(d for d in other["doors"] if d["to"] == area["id"])
            assert back["edge"] == wp.OPPOSITE[door["edge"]]
            assert door["to_spawn"] == back["spawn_id"] and back["to_spawn"] == door["spawn_id"]
            assert door["to_map"] == other["map"]
            x, y = door["cell"]
            assert (x in (0, w - 1)) != (y in (0, h - 1)), "in a wall, not in a corner"
            assert door["spawn"] == list(wp._inside(door["edge"], (x, y)))
            # the two areas are neighbours on the grid in the direction of the door
            ax, ay = plan["grid"][area["id"]]
            step = wp.STEP[door["edge"]]
            assert plan["grid"][other["id"]] == [ax + step[0], ay + step[1]]
        cells = [tuple(d["cell"]) for d in area["doors"]]
        assert len(cells) == len(set(cells))


def test_nothing_stands_in_the_way_and_enemies_keep_off_the_doors() -> None:
    plan = wp.plan(AREAS, 7)
    for area in plan["areas"][1:]:
        w, h = area["size"]
        placed = (
            [tuple(c["cell"]) for c in area["chests"]]
            + [tuple(e["cell"]) for e in area["enemies"]]
            + [tuple(d) for d in area["decorations"]]
        )
        assert len(placed) == len(set(placed)), "one thing per cell"
        assert all(2 <= x <= w - 3 and 2 <= y <= h - 3 for x, y in placed), "inside the walls"
        ways = set()
        for door in area["doors"]:
            ways.update(wp._corridor(tuple(door["spawn"]), (w, h)))
        assert not ways & set(placed), "the way from every door to the middle is free"
        for enemy in area["enemies"]:
            for door in area["doors"]:
                far = abs(enemy["cell"][0] - door["spawn"][0]) + abs(
                    enemy["cell"][1] - door["spawn"][1]
                )
                assert far >= wp.ENEMY_DISTANCE
        assert len(area["decorations"]) == wp.DECORATIONS[area["biome"]]
    woods, bay = wp.area_of(plan, "woods"), wp.area_of(plan, "bay")
    assert (len(woods["chests"]), len(woods["enemies"])) == (2, 3)
    assert woods["decor_words"] == ["tree", "bush"]
    rect = bay["water"]
    assert rect and not any(d["edge"] == "S" for d in bay["doors"]) or rect[1] != 16
    assert not {
        (x, y) for x in range(rect[0], rect[0] + rect[2]) for y in range(rect[1], rect[1] + rect[3])
    } & {tuple(d) for d in bay["decorations"]}


def test_the_key_is_reachable_before_the_gate() -> None:
    plan = wp.plan(AREAS, 7)
    key = plan["key"]
    assert key["item"] == wp.KEY_ITEM and key["opens"] == "old_mine"
    assert key["area"] not in ("starter_map", "old_mine"), "never in the village, never behind it"
    holder = wp.area_of(plan, key["area"])
    assert {"item_id": wp.KEY_ITEM, "qty": 1} in holder["chests"][0]["items"]
    assert key["chest"] == holder["chests"][0]["id"]
    # every door into the cave is locked, and has its gate on its cell
    locked = [(a, d) for a in plan["areas"] for d in a["doors"] if d["to"] == "old_mine"]
    assert locked and all(d["key"] == wp.KEY_ITEM for _a, d in locked)
    for area, door in locked:
        gate = next(g for g in area["gates"] if g["door"] == door["id"])
        assert gate["cell"] == door["cell"] and gate["key_item"] == wp.KEY_ITEM
    # the planner's own check: the key can be fetched without the key
    graph = wp.graph_of(plan)
    assert key["area"] in lockkey.reachable(graph, "starter_map", [])
    assert "old_mine" not in lockkey.reachable(graph, "starter_map", [])
    assert "old_mine" in lockkey.reachable(graph, "starter_map", [wp.KEY_ITEM])
    # an area that holds the key but was asked to have no chest gets one
    no_chests = [dict(a, chests=0) if a["biome"] != "village" else a for a in AREAS]
    for seed in range(20):
        found = wp.plan(no_chests, seed)
        assert wp.area_of(found, found["key"]["area"])["chests"], seed


def test_a_cave_next_to_the_village_only_is_not_locked() -> None:
    plan = wp.plan([AREAS[0], AREAS[3]], 3)
    assert "key" not in plan
    assert not any(d.get("key") for a in plan["areas"] for d in a["doors"])
    assert "not locked" in plan["notes"][0]
    assert wp.check(plan) == {"unreachable": [], "unpaired": []}


def test_no_plan_is_unreachable_or_unpaired_over_200_seeds() -> None:
    for seed in range(200):
        for count in range(2, len(AREAS) + 1):
            plan = wp.plan(AREAS[:count], seed)
            assert wp.check(plan) == {"unreachable": [], "unpaired": []}, (seed, count)
    full = [{"name": f"Area {i}", "biome": wp.BIOMES[i % 5]} for i in range(wp.MAX_AREAS)]
    for seed in range(40):
        plan = wp.plan(full, seed)
        assert wp.check(plan) == {"unreachable": [], "unpaired": []}, seed
        schema.validate("world_plan", plan)


def test_check_names_what_is_broken() -> None:
    plan = wp.plan(AREAS[:3], 7)
    woods = wp.area_of(plan, "woods")
    village = wp.area_of(plan, "starter_map")
    village["doors"] = [d for d in village["doors"] if d["to"] != "woods"]
    found = wp.check(plan)
    assert found["unreachable"] == ["woods"], "no door leads to it any more"
    assert found["unpaired"] == [woods["doors"][0]["id"]], "its own door has no spawn to arrive at"


# ------------------------------------------------------------------------ biomes


def test_a_biome_without_its_assets_falls_back_with_a_note() -> None:
    profiles.install_profile(SAMPLE / "sample.rpgprofile.json")
    sample = _catalog(SAMPLE, "sample_pack")
    assert wp.available("forest", sample)[0], "the sample pack has trees"
    assert wp.available("cave", sample)[0] and wp.available("shore", sample)[0]
    assert wp.resolve_biome("forest", sample)[0] == "forest"
    plain = _catalog(SYNTH / "basic16", "basic16")  # ground and a hero, nothing else
    assert not wp.available("forest", plain)[0]
    assert wp.resolve_biome("shore", plain)[0] == "field", "shore -> cave -> forest -> field"
    plan = wp.plan(AREAS, 7, plain)
    assert [a["biome"] for a in plan["areas"]] == ["village", "field", "field", "field", "field"]
    assert wp.area_of(plan, "woods")["wanted_biome"] == "forest"
    assert plan["notes"][0] == "Woods: the packs have nothing for a forest, so it is a field."
    assert len(plan["notes"]) == 3 and "key" not in plan, "no cave: nothing is locked"
    schema.validate("world_plan", plan)
    # without a catalog nothing is checked (the preview before the packs are analysed)
    assert [a["biome"] for a in wp.plan(AREAS, 7)["areas"]][2:] == ["forest", "cave", "shore"]


def test_a_biome_prefers_ground_named_for_it(tmp_path: Path) -> None:
    import shutil

    pack = tmp_path / "caves"
    shutil.copytree(SAMPLE, pack)
    shutil.copy(pack / "tilesets" / "ground.png", pack / "tilesets" / "stone_floor.png")
    cat = _catalog(pack, "caves")
    ok, ground = wp.available("cave", cat)
    assert ok and ground == "caves.tilesets.stone_floor"
    assert wp.area_of(wp.plan(AREAS, 7, cat), "old_mine")["ground"] == ground
    assert wp.area_of(wp.plan(AREAS, 7, cat), "meadow")["ground"] == ""


# ------------------------------------------------------------------------ the stored plan


def test_a_stored_plan_is_reused_once_a_map_exists(tmp_path: Path) -> None:
    project = tmp_path / "project"
    first, notes = wp.for_project(project, AREAS[:3], 7, None)
    assert notes == [] and wp.load(project) is None
    wp.save(project, first)
    assert wp.load(project) == first
    assert not wp.exists(project), "no area map yet: the world can still be planned again"
    # before any area map exists a new seed or table gives a new plan
    assert wp.for_project(project, AREAS[:3], 8, None)[0] != first
    # ... the starter map alone does not fix it either
    (project / "game" / "maps").mkdir(parents=True)
    (project / "game" / "maps" / "starter_map.tscn").write_text("x", encoding="utf-8")
    assert wp.for_project(project, AREAS[:3], 8, None)[0] != first
    # once an area map exists the seed and the table no longer count
    (project / "game" / "maps" / "meadow.tscn").write_text("x", encoding="utf-8")
    assert wp.exists(project)
    again, notes = wp.for_project(project, AREAS[:3], 999, None)
    assert again == first and notes == []
    changed = [dict(AREAS[1], size=[60, 40]), AREAS[0], AREAS[2]]
    assert wp.for_project(project, changed, 999, None)[0] == first, "an old row cannot change"


def test_a_new_row_is_appended_and_nothing_else_moves(tmp_path: Path) -> None:
    project = tmp_path / "project"
    stored = wp.plan(AREAS[:3], 7)
    wp.save(project, stored)
    (project / "game" / "maps").mkdir(parents=True)
    (project / "game" / "maps" / "woods.tscn").write_text("x", encoding="utf-8")
    table = [*AREAS[:3], {"name": "Peak", "biome": "cave", "join": "Woods"}]
    plan, notes = wp.for_project(project, table, 12345, None)
    assert notes == ["The world kept its plan; added: peak."]
    schema.validate("world_plan", plan)
    assert [a["id"] for a in plan["areas"]] == ["starter_map", "meadow", "woods", "peak"]
    for area in stored["areas"]:
        new = wp.area_of(plan, area["id"])
        assert plan["grid"][area["id"]] == stored["grid"][area["id"]]
        for key in ("size", "biome", "chests", "enemies", "decorations"):
            assert new.get(key) == area.get(key), (area["id"], key)
        assert new["doors"][: len(area["doors"])] == area["doors"], "its old doors are as they were"
    peak, woods = wp.area_of(plan, "peak"), wp.area_of(plan, "woods")
    assert [d["to"] for d in peak["doors"]] == ["woods"], "joined to the area the row names"
    assert woods["doors"][-1]["to"] == "peak"
    gx, gy = plan["grid"]["woods"]
    px, py = plan["grid"]["peak"]
    assert abs(gx - px) + abs(gy - py) == 1, "beside it on the grid"
    assert wp.check(plan) == {"unreachable": [], "unpaired": []}
    # asked again, nothing is added twice
    assert wp.extend(plan, table, 5)[1] == []
    # a row without `join` hangs on any area with room
    more, added = wp.extend(plan, [*table, {"name": "Dunes", "biome": "shore"}], 5)
    assert added == ["dunes"] and wp.check(more) == {"unreachable": [], "unpaired": []}


def test_map_hashes_are_recorded_for_the_maps_a_run_built(tmp_path: Path) -> None:
    from rpggen.core import ledger

    staging, before = tmp_path / "staging", tmp_path / "before"
    plan = wp.plan(AREAS[:3], 7)
    for folder in (staging, before):
        (folder / "game" / "maps").mkdir(parents=True)
    for name in ("starter_map", "meadow", "woods"):
        (staging / "game" / "maps" / f"{name}.tscn").write_text(f"[{name}]\n", encoding="utf-8")
    # the woods were there before this run (a person may have changed them): no hash
    (before / "game" / "maps" / "woods.tscn").write_text("[woods]\n", encoding="utf-8")
    assert wp.record_hashes(staging, plan, before)
    assert sorted(plan["maps"]) == ["meadow", "starter_map"]
    assert plan["maps"]["meadow"]["map_hash"] == ledger.file_hash(
        staging / "game" / "maps" / "meadow.tscn"
    )
    assert not wp.record_hashes(staging, plan, before), "a hash is recorded once"
    schema.validate("world_plan", plan)
    wp.save(staging, plan)
    assert jsonio.read(staging / wp.PLAN_FILE)["maps"]["starter_map"]["map_hash"]
    # a first generation has no project before it: every map is rpggen's
    fresh = wp.plan(AREAS[:3], 7)
    assert wp.record_hashes(staging, fresh) and sorted(fresh["maps"]) == [
        "meadow",
        "starter_map",
        "woods",
    ]


def test_a_broken_stored_plan_is_no_plan(tmp_path: Path) -> None:
    (tmp_path / "rpggen").mkdir()
    (tmp_path / wp.PLAN_FILE).write_text("{not json", encoding="utf-8")
    assert wp.load(tmp_path) is None and not wp.exists(tmp_path)
    jsonio.write(tmp_path / wp.PLAN_FILE, {"world_plan_version": 99})
    assert wp.load(tmp_path) is None
