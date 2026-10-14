"""T17.24: the cave, combat on a farm. *Combat* is shown for a farm and, on, gives it a cave (an
added map of its own kind, planned once with the others), whose things and enemy the kit draws
when the packs lack them; a cave row without *Combat* is refused in words; a farm that fights
gets the action RPG's runtime folder and recipes, and a farm that does not is what it was."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from rpggen import paths, schema
from rpggen.core import (
    added_map_plan,
    catalog,
    config,
    crop_plan,
    farm_kit,
    farm_plan,
    forage_plan,
    map_preview,
    options,
    orchestrator,
    staging,
)

REF = config.PackRef("p", "/p", "0" * 64, "folder")


def _cells(rows: list) -> set[tuple[int, int]]:
    return {(c[0], c[1]) for c in rows}


def _catalog() -> catalog.Catalog:
    return catalog.Catalog(assets=[])


def _cfg(combat: bool, rows: list | None = None) -> config.GeneratorConfig:
    cfg = config.default_for("T", [REF], archetype="farm")
    cfg.features["combat"] = combat
    if rows is not None:
        cfg.starter_map["added_maps"] = rows
    return cfg


# --------------------------------------------------------------------------- the feature


def test_combat_is_shown_for_a_farm_and_says_what_it_does_there() -> None:
    assert options.hidden_features("farm") == ()
    assert "cave" in options.feature_text("combat", "farm")
    assert options.feature_text("combat", "arpg") == options.FEATURE_INFO["combat"][2]
    # the demo and the navigation layer of a farm still do not need it
    assert options.dependencies("farm")["demo"] == ("tilesets", "dialogue", "save")
    assert options.dependencies("farm")["navigation"] == ()
    assert config.default_features("farm")["combat"] is False, "a farm does not fight by default"


# --------------------------------------------------------------------------- the rows


def test_combat_adds_a_cave_and_a_cave_row_needs_combat() -> None:
    """The choice of the card: *Combat* on implies a cave; a cave row without *Combat* is
    refused. A row of the kind names the cave, and no second one is added."""
    with_cave = added_map_plan.with_cave
    assert with_cave([], True) == [{"name": "Cave", "kind": "cave"}]
    assert with_cave([], False) == []
    assert with_cave([{"name": "Old woods"}], False) == [{"name": "Old woods"}]
    named = [{"name": "Old mine"}]
    assert with_cave(named, True) == named, "a row whose name says cave is the cave"
    chosen = [{"name": "Deep", "kind": "cave"}, {"name": "Bay"}]
    assert with_cave(chosen, True) == chosen
    taken = [{"name": "cave", "kind": "forest"}]
    assert with_cave(taken, True)[-1] == {"name": "Cave 2", "kind": "cave"}, "a name of its own"
    with pytest.raises(added_map_plan.CaveNeedsCombat, match="Old mine: .*feature Combat"):
        with_cave(named, False)
    # a stored map is not read again: a forest called "Old mine" from before the card stays one,
    # and a farm that has its cave gets no second one
    stored = [{"name": "Old mine", "kind": "forest", "id": "farm_map_1"}]
    assert with_cave(named, False, stored) == named
    stored_cave = [{"name": "Cave", "kind": "cave", "id": "farm_map_1"}]
    assert with_cave([], True, stored_cave) == []
    assert added_map_plan.fights(False, stored_cave) and not added_map_plan.fights(False, stored)
    assert added_map_plan.kinds_for([{"name": "Bay"}], True) == ["beach", "cave"]
    assert added_map_plan.kinds_for([{"name": "Bay"}], False) == ["beach"]
    assert added_map_plan.kinds_for([], False, stored_cave) == ["cave"]
    # the orchestrator's options for the farm's planner
    assert orchestrator.farm_map_options(_cfg(True), None)["added_maps"][-1]["kind"] == "cave"
    assert orchestrator.farm_map_options(_cfg(False), None)["added_maps"] == []
    assert orchestrator.farm_fights(_cfg(True)) and not orchestrator.farm_fights(_cfg(False))
    assert not orchestrator.farm_fights(config.default_for("T", [REF], archetype="arpg"))


# --------------------------------------------------------------------------- the plan


def test_a_cave_is_rock_with_chambers_enemies_and_things_to_find() -> None:
    for seed in range(80):
        cave = added_map_plan.plan("cave", 1 + seed % 4, seed, "Cave")
        assert added_map_plan.check(cave) == [], seed
        assert cave["size"] == list(added_map_plan.SIZES["cave"])
        walls, reached = _cells(cave["walls"]), added_map_plan.reached_cells(cave)
        assert walls and not walls & reached, "the rock is not walked on"
        assert len(walls) > len(reached), "a cave is more rock than floor"
        enemies = _cells([e["cell"] for e in cave["enemies"]])
        assert 1 <= len(enemies) <= added_map_plan.CAVE_ENEMIES and enemies <= reached
        spawn = cave["door"]["spawn"]
        assert all(
            abs(x - spawn[0]) + abs(y - spawn[1]) >= added_map_plan.ENEMY_AWAY for x, y in enemies
        ), "nobody waits at the way in"
        assert len(cave["spots"]) >= 3 and _cells(cave["spots"]) <= reached
        assert not enemies & _cells(cave["spots"])
        assert cave["trees"] == [] and cave["debris"] == []
        assert {s["kind"] for s in cave["scenery"]} <= {"rock"}
    # a cave is the same for the same seed and number
    assert added_map_plan.plan("cave", 2, 9, "Deep") == added_map_plan.plan("cave", 2, 9, "Deep")
    # the check finds an enemy that was moved into the rock or to the way in
    cave = added_map_plan.plan("cave", 1, 4, "Cave")
    broken = copy.deepcopy(cave)
    broken["enemies"][0]["cell"] = cave["walls"][0]
    assert any("an enemy overlaps the rock" in p for p in added_map_plan.check(broken))
    broken = copy.deepcopy(cave)
    broken["enemies"] = []
    assert "the cave has no enemy" in added_map_plan.check(broken)
    broken = copy.deepcopy(cave)
    spawn = cave["door"]["spawn"]
    near = next(c for c in added_map_plan.reached_cells(cave) if c != tuple(spawn)
                and abs(c[0] - spawn[0]) + abs(c[1] - spawn[1]) <= 2)  # fmt: skip
    broken["enemies"] = [{"cell": list(near)}]
    assert any("stands at the way in" in p for p in added_map_plan.check(broken))


def test_a_farm_with_combat_plans_its_cave_once_and_keeps_it(tmp_path: Path) -> None:
    rows = added_map_plan.with_cave([{"name": "Old woods"}], True)
    farm = farm_plan.plan({"added_maps": rows}, 31)
    assert [e["kind"] for e in farm["added"]] == ["forest", "cave"]
    assert farm_plan.check(farm) == []
    world = farm_plan.attach(crop_plan.world(crop_plan.plan({}, 31), 31), farm)
    schema.validate("world_plan", world)
    assert added_map_plan.summary(farm["added"]) == "a forest (Old woods) and a cave (Cave)"
    # a later generation with the same options plans nothing new
    again, added = farm_plan.extend(farm, added_map_plan.with_cave(rows, True, farm["added"]))
    assert (again, added) == (farm, [])
    # switched off afterwards, the stored cave stays and the farm still fights
    off = added_map_plan.with_cave([{"name": "Old woods"}], False, farm["added"])
    assert farm_plan.extend(farm, off) == (farm, [])
    assert added_map_plan.fights(False, farm["added"])
    text = options.added_maps_text(farm)
    assert text[1].startswith("Cave: a cave of 26 x 20 with ") and text[1].endswith("to fight")


def test_a_config_with_a_cave_row_and_no_combat_is_refused_in_words() -> None:
    cfg = _cfg(False, [{"name": "Deep", "kind": "cave"}])
    schema.validate("config", cfg.to_json())  # the schema knows the kind
    with pytest.raises(farm_plan.FarmPlanError, match="switch on the feature Combat"):
        options.plan_farm(cfg, None)
    plans = options.plan_farm(_cfg(True), None)
    assert [e["kind"] for e in plans["map"]["added"]] == ["cave"]


# --------------------------------------------------------------------------- what a cave has


def test_a_cave_brings_its_own_things_dearer_than_the_farms() -> None:
    farm = farm_plan.plan({"added_maps": [{"name": "Cave", "kind": "cave"}]}, 5)
    section = forage_plan.plan({}, 5, None, farm)
    cave = [f for f in section["forage"] if f.get("maps") == ["cave"]]
    assert [f["name"] for f in cave] == ["Amethyst", "Cave mushroom", "Copper ore"]
    assert all(f["seasons"] == list(forage_plan.SEASONS) for f in cave), "every season"
    assert [f["price"] for f in cave] == list(forage_plan.CAVE_PRICES)
    assert [f["energy"] for f in cave] == [0, forage_plan.FORAGE_ENERGY, 0], "the mushroom is food"
    assert forage_plan.check(section) == [], "they do not count for the farm's seasons"
    assert forage_plan.with_cave(section, None) == [], "appended once"
    # a stored plan without a cave gets them when the farm gets its cave
    plain = forage_plan.plan({}, 5, None, farm_plan.plan({}, 5))
    assert not any(f.get("maps") == ["cave"] for f in plain["forage"])
    grown, notes = forage_plan.for_project(plain, {}, 5, None, farm)
    assert len(grown["forage"]) == len(plain["forage"]) + 3 and "Copper ore" in notes[0]
    assert grown["forage"][: len(plain["forage"])] == plain["forage"], "nothing stored changes"


def test_the_kit_draws_the_things_and_the_enemy_of_a_cave_only_for_a_farm_that_fights(
    tmp_path: Path,
) -> None:
    empty = _catalog()
    plain = [s.name for s in farm_kit.lacking(empty)]
    assert not {"slime", "copper_ore", "amethyst", "cave_mushroom"} & set(plain)
    cave = [s.name for s in farm_kit.lacking(empty, kinds=["cave"])]
    assert cave == [*plain, "copper_ore", "amethyst", "cave_mushroom", "slime"]
    added, issues = farm_kit.add(empty, 16, tmp_path, kinds=["cave"])
    notes = [i.message for i in issues if i.code == "ASSET-031"]
    assert any("enemy of the cave" in n for n in notes)
    assert any("thing to find in a cave (copper ore)" in n for n in notes)
    slime = next(a for a in empty.assets if a.id == f"{farm_kit.KIT_PACK}.slime")
    facets = catalog.effective(slime)
    assert facets["role"] == "ENEMY" and facets["usage"] == "sprite"
    assert {"idle_down", "walk_left", "walk_up"} <= set(facets["animations"])
    facts = forage_plan.facts_of(empty)
    assert [f["name"] for f in facts["cave"]] == ["amethyst", "cave_mushroom", "copper_ore"]
    assert len(facts["forage"]) == 4, "the farm's own are not the cave's"
    picture = farm_kit.slime(16)
    assert picture.size == (16 * farm_kit.HEN_FRAMES, 16 * len(farm_kit.HEN_ROWS))
    for name in farm_kit.CAVE_FORAGE:
        assert farm_kit.forage(16, name).getbbox() is not None
    # a pack's own enemy is the cave's: no slime is drawn
    assert farm_kit.KIND_STAND_INS["cave"][-1].role == "ENEMY"


def test_the_picture_of_a_cave_shows_its_rock_and_its_enemies() -> None:
    cave = added_map_plan.plan("cave", 1, 3, "Cave")
    shown = {**map_preview.FARM_COLORS, **map_preview.ADDED_COLORS}
    picture = map_preview.render_added(cave, scale=1)
    wall, enemy = cave["walls"][0], cave["enemies"][0]["cell"]
    assert picture.getpixel(tuple(wall)) == shown["rock"]
    assert picture.getpixel(tuple(enemy)) == shown["enemy"]
    marked = map_preview.added_cells(cave)
    floor = next(c for c in sorted(added_map_plan.reached_cells(cave)) if c not in marked)
    assert picture.getpixel(floor) == shown["cave"], "the floor of a cave"
    assert map_preview.render_added(cave, scale=4, footprint=(60, 34)).width > 0


# --------------------------------------------------------------------------- the install


def test_a_farm_that_fights_gets_the_action_rpgs_folder_and_one_that_does_not_does_not(
    tmp_path: Path,
) -> None:
    templates = paths.templates_root()

    def folders(written: list[str], prefix: str) -> set[str]:
        return {w.split("/")[3] for w in written if w.startswith(prefix) and w.count("/") > 3}

    plain = staging.install_templates(staging.create_staging(tmp_path / "a"), templates, "farm")
    fights = staging.install_templates(
        staging.create_staging(tmp_path / "b"), templates, "farm", borrowed=("arpg",)
    )
    assert folders(plain, "addons/rpg_runtime/archetypes/") == {"farm"}
    assert folders(fights, "addons/rpg_runtime/archetypes/") == {"farm", "arpg"}
    assert folders(fights, "generated/builder/recipes/") == {"farm", "arpg"}
    assert not any("smoke_steps_arpg" in w for w in fights), "not its smoke steps"
    assert set(fights) - set(plain) == {w for w in fights if "/arpg/" in w}, "nothing else differs"
    # a kind that may not borrow the folder does not get it
    other = staging.install_templates(
        staging.create_staging(tmp_path / "c"), templates, "racing", borrowed=("arpg",)
    )
    assert "arpg" not in folders(other, "addons/rpg_runtime/archetypes/")
