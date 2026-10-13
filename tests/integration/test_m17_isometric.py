"""Milestone M17, isometric maps and actors (T17.14): the synthetic pack ``iso_tiles`` (single
tiles on a diamond of 60 x 34, a tree and a house, no people) with ``projection: isometric`` as
a turn-based game and as an action RPG. Both are generated, painted on the diamonds of
``iso.tres`` where the plan says, peopled with the drawn hero, villager and enemy, and played by
the smoke sequences of their kinds, with the pad following the screen and following the grid.
The same pack seen from above still makes what it made."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from rpggen import jsonio, paths
from rpggen.core import archive, catalog, config, inventory, iso_math, map_preview, orchestrator

pytestmark = [pytest.mark.integration, pytest.mark.isometric]

REPO = Path(__file__).resolve().parents[2]
PACK = REPO / "test_packs" / "synthetic" / "iso_tiles"
FOOT = (60, 34)
# the shared sequence of the top-down kinds (smoke_steps_m6.gd with the M1 and M4 steps)
SHARED_STEPS = [
    "title_new_game",
    "map_music",
    "boot",
    "player_exists",
    "player_moves",
    "collision_blocks",
    "npc_dialogue",
    "chest_open",
    "enter_building",
    "exit_building",
    "decor_blocks",
    "walk_to_field",
    "return_from_field",
    "autosave",
    "save_slot_1",
    "save_overwrite_confirm",
    "equip_raises_attack",
    "shop_buy_sell",
    "quest_journal",
    "party_members",
    "followers_trail",
    "sequence_plays",
    "keys_and_switches",
    "credits_screen",
    "mutate_then_load",
    "pause_menu",
]
TURN_BASED_STEPS = [
    "encounter_start",
    "battle_victory",
    "rewards_granted",
    "returned_to_map",
    "enemy_stays_defeated",
    "random_encounter",
    "skills_and_status",
    "defeat_policy",
    "game_over_screen",
]
ARPG_STEPS = [
    "enemy_detects",
    "player_attack_hits",
    "no_damage_outside_active_frames",
    "heavy_attack_hits",
    "follower_assists",
    "enemy_dies",
    "player_hurt_invuln",
    "dodge",
    "ranged_enemy_shoots",
    "charger_charges",
    "player_bow_shoots",
    "persist",
    "death_policy",
    "game_over_screen",
]
# what the pack does not have, and a step says so instead of testing nothing: music, a wall
# tile, a chest (and the demo quest that needs one)
ABSENT = ("map_music", "collision_blocks", "chest_open", "quest_journal")
WALL_TILE = "iso_tiles.png.isotile_019_"  # a block that rises: the wall of one of the runs
MAPS = ["game/maps/starter_map.tscn", "game/maps/interior_1.tscn", "game/maps/field_1.tscn"]
KIT = [
    "generated/iso_kit/hero.png",
    "generated/iso_kit/villager.png",
    "generated/iso_kit/enemy.png",
]


def _config(
    archetype: str, projection: str = "isometric", controls: str = "screen"
) -> config.GeneratorConfig:
    cfg = config.default_for(
        "Diamond Vale", [config.pack_ref_from_source(PACK, "iso_tiles")], archetype=archetype
    )
    cfg.projection = projection
    cfg.iso_controls = controls
    return cfg


def _errors(result) -> list[str]:  # noqa: ANN001
    return [f"{i.code}: {i.message}" for i in result.issues if i.severity.value == "error"]


@pytest.fixture(scope="module")
def cache(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    folder = tmp_path_factory.mktemp("cache")
    old = os.environ.get("RPGGEN_CACHE_DIR")
    os.environ["RPGGEN_CACHE_DIR"] = str(folder)
    try:
        yield folder
    finally:
        if old is None:
            os.environ.pop("RPGGEN_CACHE_DIR", None)
        else:
            os.environ["RPGGEN_CACHE_DIR"] = old


def _generated(godot_exe: Path, folder: Path, cfg: config.GeneratorConfig):  # noqa: ANN202
    target = folder / "out"
    result = orchestrator.run_in_memory(cfg, None, target, godot_exe)
    assert result.ok, _errors(result)
    return target, result


@pytest.fixture(scope="module")
def turn_based(godot_exe: Path, cache: Path, tmp_path_factory: pytest.TempPathFactory):  # noqa: ANN201
    return _generated(godot_exe, tmp_path_factory.mktemp("iso_tb"), _config("turn_based"))


@pytest.fixture(scope="module")
def arpg(godot_exe: Path, cache: Path, tmp_path_factory: pytest.TempPathFactory):  # noqa: ANN201
    return _generated(godot_exe, tmp_path_factory.mktemp("iso_arpg"), _config("arpg"))


@pytest.fixture(scope="module")
def on_the_grid(godot_exe: Path, cache: Path, tmp_path_factory: pytest.TempPathFactory):  # noqa: ANN201
    """The same game with the pad on the diamond's axes, and with a wall: the pack names none,
    so one of its blocks is given the role as the audit would give it (the catalog a run is
    handed carries the user's corrections)."""
    opened = archive.open_pack(PACK, set(), pack_id="iso_tiles")
    cat, _issues, _made = catalog.assemble([(opened, inventory.build_inventory(opened))], None, [])
    for asset in cat.assets:
        if asset.id.startswith(WALL_TILE):
            asset.overrides = {"role": "WALL"}
            asset.status = "CONFIRMED"
    cfg = _config("turn_based", controls="grid")
    target = tmp_path_factory.mktemp("iso_grid") / "out"
    result = orchestrator.run_in_memory(cfg, cat, target, godot_exe)
    assert result.ok, _errors(result)
    return target, result


def _smoke(target: Path) -> list[str]:
    smoke = jsonio.read(target / "rpggen/results/smoke_results.json")
    assert smoke["ok"] is True, smoke["issues"]
    assert all(i["ok"] for i in smoke["items"])
    return [i["name"] for i in smoke["items"]]


def _passed_for_real(target: Path, absent: tuple[str, ...] = ABSENT) -> None:
    """Only the steps for what the pack lacks may pass with a note: the doors, the house, the
    tree, the field and the fights are played."""
    log = (target / "rpggen/logs/godot_smoke.log").read_text(encoding="utf-8", errors="replace")
    noted = [
        line.split("INFO ", 1)[1].split(":", 1)[0]
        for line in log.splitlines()
        if "step passes" in line and "INFO " in line
    ]
    assert sorted(set(noted)) == sorted(absent), noted


def _view(target: Path) -> dict:
    return jsonio.read(target / "rpggen/results/starter_map_cells.json")


def _plan(target: Path, archetype: str) -> dict:
    cat = catalog.Catalog.from_json(jsonio.read(paths.from_posix_rel(paths.CATALOG, target)))
    cfg = _config(archetype)
    house = map_preview.building_info_for(cat, "", "isometric")
    assert house == {"size": [1, 1], "door": [0, 1]}
    return map_preview.plan(cfg.starter_map_options(), cfg.seed, house, archetype)


def _at(cell) -> tuple[float, float]:  # noqa: ANN001
    return iso_math.cell_to_screen(int(cell[0]), int(cell[1]), *FOOT)


# --------------------------------------------------------------------------- the turn-based game


def test_the_pack_makes_a_turn_based_game_that_passes_its_smoke_run(turn_based) -> None:  # noqa: ANN001
    target, result = turn_based
    assert not _errors(result)
    assert _smoke(target) == SHARED_STEPS + TURN_BASED_STEPS, "the kind's usual steps, all of them"
    _passed_for_real(target)
    notes = sorted(i.detail["thing"] for i in result.issues if i.code == "ASSET-031")
    assert notes == ["enemy", "hero", "villager"], "the pack has no people: they are drawn"
    for rel in [*MAPS, *KIT, "generated/tilesets/iso.tres", "rpggen/results/starter_map.png"]:
        assert (target / rel).is_file(), rel
    archetypes = target / "addons/rpg_runtime/archetypes"
    assert sorted(p.name for p in archetypes.iterdir()) == ["turn_based"]
    assert (target / "addons/rpg_runtime/world/iso.gd").is_file()


def test_the_maps_are_painted_with_the_tile_set_of_diamonds(turn_based) -> None:  # noqa: ANN001
    target, _result = turn_based
    tilesets = sorted(p.name for p in (target / "generated/tilesets").glob("*.tres"))
    assert tilesets == ["iso.tres"], "an isometric project has one tile set"
    tile_set = (target / "generated/tilesets/iso.tres").read_text(encoding="utf-8")
    assert "tile_shape = 1" in tile_set and "tile_layout = 5" in tile_set
    assert "tile_size = Vector2i(60, 34)" in tile_set
    for rel in MAPS:
        scene = (target / rel).read_text(encoding="utf-8")
        assert 'path="res://generated/tilesets/iso.tres"' in scene, rel
        assert "overworld.tres" not in scene, rel
    # the blocked edge of a pack without a wall tile: an invisible diamond a cell
    starter = (target / MAPS[0]).read_text(encoding="utf-8")
    assert '[node name="BorderCollision" type="StaticBody2D"' in starter
    assert "ConvexPolygonShape2D" in starter and "RectangleShape2D" not in starter
    settings = (target / "project.godot").read_text(encoding="utf-8")
    assert 'iso_controls="screen"' in settings, "the runtime is told how the pad moves the player"
    minimap = target / "generated/minimaps/game__maps__starter_map.tres"
    assert "metadata/isometric = true" in minimap.read_text(encoding="utf-8")


def test_the_cells_of_the_starter_map_are_the_plans(turn_based) -> None:  # noqa: ANN001
    target, _result = turn_based
    view = _view(target)
    plan = _plan(target, "turn_based")
    w, h = plan["size"]
    assert view["projection"] == "isometric" and view["tile_size"] == list(FOOT)
    ground = next(layer for layer in view["layers"] if layer["name"] == "Ground")
    painted = {(c[0], c[1]) for c in ground["cells"]}
    assert painted == {(x, y) for x in range(w) for y in range(h)}, "every cell of the plan"
    assert len({(c[2], c[3], c[4]) for c in ground["cells"]}) > 1, "the ground is varied"
    where = {e["name"]: (e["x"], e["y"]) for e in view["entities"]}
    assert where["Player"] == _at(plan["spawn"])
    assert where["Npc1"] == _at(plan["npcs"][0])
    assert where["Enemy1"] == _at(plan["enemies"][0])
    house = next(e for e in view["entities"] if "house" in e["scene"])
    assert (house["x"], house["y"]) == _at(plan["buildings"][0]), "the house on its cell"
    for i, cell in enumerate(plan["decorations"]):
        assert where[f"Decor{i + 1}"] == _at(cell), "a tree stands on the middle of its diamond"
    # the door of the house: who comes out stands on the plan's door cell, south of the house
    scene = (target / "generated/scenes/objects/iso_tiles__png__house_01_0.tscn").read_text(
        encoding="utf-8"
    )
    assert '[node name="Entrance" type="Area2D"' in scene
    assert '[node name="ExitSpawn" type="Marker2D"' in scene
    door = plan["doors"][0]
    out = (_at(door)[0] - house["x"], _at(door)[1] - house["y"])
    assert out == iso_math.step("s", *FOOT)
    assert f"position = Vector2({out[0]:g}, {out[1]:g})" in scene


def test_a_second_run_changes_nothing(turn_based, godot_exe: Path) -> None:  # noqa: ANN001
    target, _result = turn_based
    kept = {
        rel: (target / rel).read_bytes()
        for rel in [
            *MAPS,
            *KIT,
            "generated/tilesets/iso.tres",
            "generated/scenes/actors/player.tscn",
            "generated/scenes/objects/iso_tiles__png__house_01_0.tscn",
            "project.godot",
            paths.CATALOG,
            paths.CONFIG,
            paths.LEDGER,
        ]
    }
    again = orchestrator.run_in_memory(_config("turn_based"), None, target, godot_exe)
    assert again.ok, _errors(again)
    assert [i.code for i in again.issues if i.code == orchestrator.REPEAT_CODE], (
        "nothing changed: the build and the checks are not repeated"
    )
    for rel, data in kept.items():
        assert (target / rel).read_bytes() == data, rel


def test_the_projection_of_a_generated_project_cannot_be_changed(
    turn_based,  # noqa: ANN001
    godot_exe: Path,
) -> None:
    target, _result = turn_based
    starter = (target / MAPS[0]).read_bytes()
    seen_from_above = _config("turn_based", projection="top_down")
    result = orchestrator.run_in_memory(
        seen_from_above, None, target, godot_exe, placeholders=["PLAYER", "GROUND"]
    )
    assert not result.ok and result.failed_phase == "preflight"
    refused = [i for i in result.issues if i.code == "CAT-002"]
    assert refused and "cannot change its projection" in refused[0].message
    assert (target / MAPS[0]).read_bytes() == starter, "the project is as it was"
    saved = jsonio.read(paths.from_posix_rel(paths.CONFIG, target))
    assert saved["projection"] == "isometric"


def test_the_steps_hold_when_the_pad_follows_the_grid(on_the_grid) -> None:  # noqa: ANN001
    """The steps ask the map where things are and which way to go: with the four directions of
    the pad on the diamond's axes the same sequence passes."""
    target, _result = on_the_grid
    assert _smoke(target) == SHARED_STEPS + TURN_BASED_STEPS
    # this map has a wall: the player walks at it and is stopped, the step is no note
    _passed_for_real(target, tuple(name for name in ABSENT if name != "collision_blocks"))
    settings = (target / "project.godot").read_text(encoding="utf-8")
    assert 'iso_controls="grid"' in settings
    assert jsonio.read(paths.from_posix_rel(paths.CONFIG, target))["iso_controls"] == "grid"
    # the wall rises, so its near sides are painted where they are sorted with who stands by
    # them: the Y-sorted Props layer. Its far sides (the first row and the first column, behind
    # which nobody stands) lie in the place of the ground of their cells, where the tiles
    # before them cover the earth under them (T17.18): a ring of the plan's size in all, with
    # a gap for the way to the field
    view = _view(target)
    plan = _plan(target, "turn_based")
    w, h = plan["size"]
    props = next(layer for layer in view["layers"] if layer["name"] == "Props")
    ground = next(layer for layer in view["layers"] if layer["name"] == "Ground")
    ring = {(x, y) for x in range(w) for y in range(h) if x in (0, w - 1) or y in (0, h - 1)}
    ring -= {tuple(plan["exit_gap"])}
    far = {cell for cell in ring if 0 in cell}
    assert {(c[0], c[1]) for c in props["cells"]} == ring - far
    wall_tiles = {(c[2], c[3], c[4]) for c in props["cells"]}
    on_ground = {(c[0], c[1]) for c in ground["cells"] if (c[2], c[3], c[4]) in wall_tiles}
    assert on_ground == far, "the far walls, and no other cell of the ground"
    assert not next(layer for layer in view["layers"] if layer["name"] == "Walls")["cells"]
    # the near walls block by their own diamonds; the ground's layer blocks nothing, so the far
    # ones keep theirs as unseen shapes
    starter = (target / MAPS[0]).read_text(encoding="utf-8")
    assert starter.count('parent="BorderCollision"') == len(far)


def test_a_world_of_areas_on_diamonds(
    godot_exe: Path, cache: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """The areas of a world are planned on cells like the village and painted through the same
    seam: the player walks through a door of the village to an area and back."""
    cfg = _config("turn_based")
    cfg.starter_map = {
        "areas": [
            {"name": "Green Field", "biome": "field"},
            {"name": "Old Shore", "biome": "shore"},
        ]
    }
    target, _result = _generated(godot_exe, tmp_path_factory.mktemp("iso_world"), cfg)
    names = _smoke(target)
    assert "world_doors" in names
    log = (target / "rpggen/logs/godot_smoke.log").read_text(encoding="utf-8", errors="replace")
    assert "world_doors: went to" in log, "through a door of the village and back"
    plan = jsonio.read(target / "rpggen/world_plan.json")
    others = [area for area in plan["areas"] if area["id"] != "starter_map"]
    assert others, "the world has areas beside the village"
    for area in others:
        scene = (target / area["map"]).read_text(encoding="utf-8")
        assert 'path="res://generated/tilesets/iso.tres"' in scene, area["id"]
        assert "ConvexPolygonShape2D" in scene and "RectangleShape2D" not in scene, area["id"]


# ------------------------------------------------------------------------------- the action RPG


def test_the_pack_makes_an_action_rpg_that_passes_its_smoke_run(arpg) -> None:  # noqa: ANN001
    target, result = arpg
    assert not _errors(result)
    assert _smoke(target) == SHARED_STEPS + ARPG_STEPS, "the kind's usual steps, all of them"
    _passed_for_real(target)
    archetypes = target / "addons/rpg_runtime/archetypes"
    assert sorted(p.name for p in archetypes.iterdir()) == ["arpg"]
    view = _view(target)
    plan = _plan(target, "arpg")
    where = {e["name"]: (e["x"], e["y"]) for e in view["entities"]}
    assert where["Player"] == _at(plan["spawn"])
    assert [where[f"Enemy{i + 1}"] for i in range(2)] == [_at(c) for c in plan["enemies"]]
    for rel in MAPS:
        assert 'path="res://generated/tilesets/iso.tres"' in (target / rel).read_text(
            encoding="utf-8"
        )
    # the hero is as wide as a step on the diamonds, and its reach is counted by that step
    player = (target / "generated/scenes/actors/player.tscn").read_text(encoding="utf-8")
    assert "tile_size = 34.0" in player
    hero = catalog.Catalog.from_json(
        jsonio.read(paths.from_posix_rel(paths.CATALOG, target))
    ).asset("rpggen_iso_kit.hero")
    assert hero is not None and hero.detected["frame"] == [34, 51]


# ------------------------------------------------------------------- the same pack, from above


def test_the_same_pack_seen_from_above_still_makes_what_it_made(
    godot_exe: Path, cache: Path, tmp_path: Path
) -> None:
    """A top-down project uses nothing isometric: the pack has no ground and no hero for it,
    so it is made with the placeholders that were asked for, on squares."""
    cfg = _config("turn_based", projection="top_down")
    target = tmp_path / "out"
    result = orchestrator.run_in_memory(
        cfg, None, target, godot_exe, placeholders=["PLAYER", "GROUND"]
    )
    assert result.ok, _errors(result)
    assert _smoke(target)[: len(SHARED_STEPS)] == SHARED_STEPS
    tilesets = sorted(p.name for p in (target / "generated/tilesets").glob("*.tres"))
    assert tilesets == ["overworld.tres"]
    starter = (target / MAPS[0]).read_text(encoding="utf-8")
    assert 'path="res://generated/tilesets/overworld.tres"' in starter
    assert "iso.tres" not in starter and "ConvexPolygonShape2D" not in starter
    tile_set = (target / "generated/tilesets/overworld.tres").read_text(encoding="utf-8")
    assert "tile_shape" not in tile_set, "squares"
    assert "debug_placeholders/ground.png" in tile_set
    assert not (target / "generated/iso_kit").exists(), "no people are drawn for it"
    assert not (target / "generated/iso_atlases").exists()
    assert "iso_controls" not in (target / "project.godot").read_text(encoding="utf-8")
    saved = jsonio.read(paths.from_posix_rel(paths.CONFIG, target))
    assert "projection" not in saved and "iso_controls" not in saved
    cat = catalog.Catalog.from_json(jsonio.read(paths.from_posix_rel(paths.CATALOG, target)))
    assert [t.name for t in cat.tilesets] == ["overworld"]
    assert not [a for a in cat.assets if a.pack_id in ("rpggen_iso", "rpggen_iso_kit")]
    view = _view(target)
    assert "projection" not in view and view["tile_size"] == [16, 16]


# --------------------------------------------------------------------------- the farm (T17.14)
#
# The seventh kind on the same pack: its plan is the grid of cells a farm seen from above has,
# painted on diamonds. The farm's own sequence (tests/integration/test_m17_farm.py has the same
# lists) is played with the pad on the screen on a farm with a well and no animals, and with
# the pad on the grid on a farm with a pond and a coop.

FARM_HOUSE_STEPS = ["wake_in_the_house", "walk_out_of_the_house", "go_to_the_village"]
FARM_STEPS = [
    "villager_by_the_clock",
    "give_a_gift",
    "back_to_the_farm",
    "farm_is_there",
    "fill_the_can",
    "clear_debris",
    "till_a_cell",
    "plant_a_seed",
    "water_it",
    "a_night_grows_it",
    "crop_ripens",
    "harvest",
    "ship_the_crop",
    "sleep_in_the_bed",
    "morning_summary",
    "buy_seeds_at_the_shop",
    "rain_waters_the_field",
    "hud_shows_the_day",
    "season_turns",
    "forage_on_the_farm",
    "catch_a_fish",
]
FARM_ANIMAL_STEPS = [
    "buy_a_hen",
    "hen_in_the_coop",
    "feed_at_the_trough",
    "pet_the_hen",
    "egg_in_the_morning",
    "ship_the_egg",
]
# a new game starts in the farmhouse; the shared steps are played in the village
FARM_SEQUENCE = [
    SHARED_STEPS[0],
    *FARM_HOUSE_STEPS,
    *SHARED_STEPS[1:],
    *FARM_STEPS,
    *FARM_ANIMAL_STEPS,
    "save_and_load",  # T17.18: saved, changed and loaded, the field compared cell by cell
]
FARM_MAPS = ["game/maps/farm.tscn", "game/maps/farm_house.tscn", "game/maps/starter_map.tscn"]
FARM_SOIL = "generated/tilesets/farm_soil.tres"
POND_TILE = "iso_tiles.png.isotile_007_"  # a flat tile that is given the role of water
# the cells of the tiles the field recipe draws (field_recipe.gd): source 0
PLOT_TILE = (0, 0, 0)
WATER_MARK = (0, 4, 0)


def _farm_config(controls: str = "screen", animals: str = "none") -> config.GeneratorConfig:
    cfg = config.default_for(
        "Diamond Acre" if animals == "none" else "Diamond Coop",
        [config.pack_ref_from_source(PACK, "iso_tiles")],
        archetype="farm",
    )
    cfg.projection = "isometric"
    cfg.iso_controls = controls
    cfg.starter_map["animals"] = animals
    return cfg


@pytest.fixture(scope="module")
def iso_farm(godot_exe: Path, cache: Path, tmp_path_factory: pytest.TempPathFactory):  # noqa: ANN201
    return _generated(godot_exe, tmp_path_factory.mktemp("iso_farm"), _farm_config())


@pytest.fixture(scope="module")
def iso_coop(godot_exe: Path, cache: Path, tmp_path_factory: pytest.TempPathFactory):  # noqa: ANN201
    """A farm with a coop and a pond, the pad on the diamond's axes. The pack names no water,
    so one of its flat tiles is given the role as the audit would give it."""
    opened = archive.open_pack(PACK, set(), pack_id="iso_tiles")
    cat, _issues, _made = catalog.assemble([(opened, inventory.build_inventory(opened))], None, [])
    for asset in cat.assets:
        if asset.id.startswith(POND_TILE):
            asset.overrides = {"role": "WATER"}
            asset.status = "CONFIRMED"
    target = tmp_path_factory.mktemp("iso_coop") / "out"
    result = orchestrator.run_in_memory(_farm_config("grid", "coop"), cat, target, godot_exe)
    assert result.ok, _errors(result)
    return target, result


def _farm_plan(target: Path) -> dict:
    return jsonio.read(target / "rpggen/world_plan.json")["farm"]["map"]


def _map_view(target: Path, godot_exe: Path, rel: str) -> dict:
    """The cells and the entities of one map of a generated project, dumped by the builder's
    own tool (what the picture of the starter map is drawn from)."""
    from rpggen.core import godot

    out = target / "rpggen/results" / (Path(rel).stem + "_cells.json")
    run = godot.run_godot(
        godot.find_console_exe(godot_exe),
        target,
        [
            "--script",
            "res://generated/builder/tools/dump_map_view.gd",
            "--",
            f"--map=res://{rel}",
            f"--out={out}",
        ],
        timeout_s=120,
        log_name="farm_view",
        log_dir=target / "rpggen/logs",
    )
    assert run.returncode == 0 and out.is_file(), run.stdout[-2000:]
    return jsonio.read(out)


def _cells(view: dict, layer: str) -> dict[tuple[int, int], tuple[int, int, int]]:
    found = next(entry for entry in view["layers"] if entry["name"] == layer)
    return {(c[0], c[1]): (c[2], c[3], c[4]) for c in found["cells"]}


def test_the_pack_makes_an_isometric_farm_that_passes_its_smoke_run(iso_farm) -> None:  # noqa: ANN001
    target, result = iso_farm
    assert not _errors(result)
    assert _smoke(target) == FARM_SEQUENCE, "the farm's usual steps, all of them"
    # what this farm does not have says so: no music, wall or chest in the pack, a well where
    # the pack has no water, no animal house
    _passed_for_real(target, (*ABSENT, "catch_a_fish", *FARM_ANIMAL_STEPS))
    for rel in [*FARM_MAPS, FARM_SOIL, "generated/tilesets/iso.tres", "generated/data/crops.json"]:
        assert (target / rel).is_file(), rel
    archetypes = target / "addons/rpg_runtime/archetypes"
    assert sorted(p.name for p in archetypes.iterdir()) == ["farm"]
    assert (archetypes / "farm/farm_iso.gd").is_file()
    # the people of the view and the farm's own stand-ins are drawn; what lies flat on squares
    # (soil tiles, the bin, the bed) is not: the recipes draw those on their diamonds
    notes = sorted(i.detail["thing"] for i in result.issues if i.code == "ASSET-031")
    assert {"hero", "villager", "hoe", "farm animal"} <= set(notes)
    assert not {"tilled soil", "watered soil", "shipping bin", "bed"} & set(notes)
    kit = sorted(p.name for p in (target / "generated/farm_kit").glob("*.png"))
    assert "hoe.png" in kit and "turnip.png" in kit
    assert not {"soil.png", "watered.png", "shipping_bin.png", "bed.png"} & set(kit)
    cat = catalog.Catalog.from_json(jsonio.read(paths.from_posix_rel(paths.CATALOG, target)))
    assert [t.name for t in cat.tilesets] == ["iso"], "no tile set of squares"
    hoe = next(a for a in cat.assets if a.id == "rpggen_farm_kit.hoe")
    unit = iso_math.unit(*FOOT)
    assert catalog.effective(hoe)["size"] == [unit, unit], "the kit is a step on the diamonds large"
    saved = jsonio.read(paths.from_posix_rel(paths.CONFIG, target))
    assert saved["projection"] == "isometric" and saved["archetype"] == "farm"


def test_the_farm_is_painted_on_diamonds_where_its_plan_says(iso_farm, godot_exe: Path) -> None:  # noqa: ANN001
    target, _result = iso_farm
    tilesets = sorted(p.name for p in (target / "generated/tilesets").glob("*.tres"))
    assert tilesets == ["farm_room.tres", "farm_soil.tres", "iso.tres"]
    # the drawn floor of the rooms (T17.18) is a diamond on the grid of the ground
    room_set = (target / "generated/tilesets/farm_room.tres").read_text(encoding="utf-8")
    assert (
        "tile_shape = 1" in room_set and f"tile_size = Vector2i({FOOT[0]}, {FOOT[1]})" in room_set
    )
    house = (target / "game/maps/farm_house.tscn").read_text(encoding="utf-8")
    assert "generated/tilesets/farm_room.tres" in house and "generated/tilesets/iso.tres" in house
    soil_set = (target / FARM_SOIL).read_text(encoding="utf-8")
    assert "tile_shape = 1" in soil_set and "tile_layout = 5" in soil_set
    assert "tile_size = Vector2i(60, 34)" in soil_set, "the soil lies on the diamonds of the ground"
    for rel in FARM_MAPS:
        scene = (target / rel).read_text(encoding="utf-8")
        assert 'path="res://generated/tilesets/iso.tres"' in scene, rel
        assert "overworld.tres" not in scene and "RectangleShape2D" not in scene, rel
    farm_scene = (target / FARM_MAPS[0]).read_text(encoding="utf-8")
    assert 'path="res://generated/tilesets/farm_soil.tres"' in farm_scene
    assert "ConvexPolygonShape2D" in farm_scene
    # the plan: the one the planner makes of the view's facts, stored, and a grid of cells
    plan = _farm_plan(target)
    cat = catalog.Catalog.from_json(jsonio.read(paths.from_posix_rel(paths.CATALOG, target)))
    cfg = _farm_config()
    facts = orchestrator.farm_facts(cfg, cat)
    assert facts == {"water": False, "house": {"size": [1, 1], "door": [0, 1]}}
    from rpggen.core import farm_plan

    planned = farm_plan.plan(cfg.starter_map_options(), cfg.seed, facts)
    for key in ("size", "house", "tillable", "water", "bin", "exit", "paths", "trees", "debris"):
        assert plan[key] == planned[key], key
    assert farm_plan.check(plan) == []
    w, h = plan["size"]
    view = _map_view(target, godot_exe, FARM_MAPS[0])
    assert view["projection"] == "isometric" and view["tile_size"] == list(FOOT)
    assert set(_cells(view, "Ground")) == {(x, y) for x in range(w) for y in range(h)}
    # the field: what can be tilled in the scene is what the plan lists, and the can is filled
    # where the plan has its water
    soil = _cells(view, "Soil")
    assert {c for c, tile in soil.items() if tile == PLOT_TILE} == {
        tuple(c) for c in plan["tillable"]
    }
    assert {c for c, tile in soil.items() if tile == WATER_MARK} == {
        tuple(c) for c in plan["water"]["cells"]
    }
    assert len(soil) == len(plan["tillable"]) + len(plan["water"]["cells"])
    # what stands on the farm stands on the middle of its diamond
    where = {e["name"]: (e["x"], e["y"]) for e in view["entities"]}
    door = plan["house"]["door"]
    assert where["Player"] == _at(door), "a farmer who comes out of the house is on the door cell"
    assert where["ShippingBin"] == _at(plan["bin"]["cell"])
    # the pack's house is drawn on one diamond: it stands in the last row of the plan's
    # footprint, over the door cell
    x, y, wide, high = plan["house"]["rect"]
    assert (wide, high) == (2, 2) and door == [x, y + high]
    assert where["House"] == _at([door[0], door[1] - 1])
    house = next(e for e in view["entities"] if e["name"] == "House")
    assert "house_01" in house["scene"]
    for i, cell in enumerate(plan["trees"][:3]):
        assert f'[node name="Tree{i + 1}"' in farm_scene, cell
    assert farm_scene.count('[node name="Debris_') == len(plan["debris"])
    # the room of the house: the farmer by the bed, on the plan's cell
    room = _map_view(target, godot_exe, FARM_MAPS[1])
    inside = {e["name"]: (e["x"], e["y"]) for e in room["entities"]}
    start = plan["house"]["interior"]["start"]
    assert inside["Player"] == _at(start)
    bed = plan["house"]["interior"]["bed"]["cell"]
    assert inside["Bed"] == _at([bed[0], bed[1] + 1]), "the bed's origin is the cell of its foot"


def test_a_second_run_of_the_farm_changes_nothing(iso_farm, godot_exe: Path) -> None:  # noqa: ANN001
    target, _result = iso_farm
    kept = {
        rel: (target / rel).read_bytes()
        for rel in [
            *FARM_MAPS,
            FARM_SOIL,
            "generated/tilesets/iso.tres",
            "generated/scenes/actors/player.tscn",
            "generated/scenes/farm/bed.tscn",
            "generated/scenes/farm/shipping_bin.tscn",
            "generated/scenes/farm/crops/turnip.tscn",
            "generated/farm_kit/hoe.png",
            "game/data/new_game.tres",
            "rpggen/world_plan.json",
            "project.godot",
            paths.CATALOG,
            paths.CONFIG,
            paths.LEDGER,
        ]
    }
    again = orchestrator.run_in_memory(_farm_config(), None, target, godot_exe)
    assert again.ok, _errors(again)
    assert [i.code for i in again.issues if i.code == orchestrator.REPEAT_CODE], (
        "nothing changed: the build and the checks are not repeated"
    )
    for rel, data in kept.items():
        assert (target / rel).read_bytes() == data, rel


def test_an_isometric_farm_with_a_coop_and_a_pond(iso_coop, godot_exe: Path) -> None:  # noqa: ANN001
    """The steps of the animals and the fishing step are played, with the pad on the grid: the
    hen is bought, wanders the cells of its yard, is fed at the trough and gives an egg; the
    rod is cast at the pond ahead and a fish is landed."""
    target, result = iso_coop
    assert not _errors(result)
    assert _smoke(target) == FARM_SEQUENCE
    _passed_for_real(target)  # nothing of the farm passes with a note
    settings = (target / "project.godot").read_text(encoding="utf-8")
    assert 'iso_controls="grid"' in settings
    plan = _farm_plan(target)
    assert plan["animals"] == "coop" and plan["water"]["kind"] == "pond"
    coop = plan["animal_houses"][0]
    yard = coop["yard"]
    scene = (target / FARM_MAPS[0]).read_text(encoding="utf-8")
    assert scene.count('[node name="Fence_coop_') == len(yard["fence"])
    assert (
        '[node name="Gate_coop"' in scene
        and '[node name="Coop" type="Node2D" parent="Yards"' in scene
    )
    assert (target / "game/maps/farm_coop.tscn").is_file()
    assert "iso.tres" in (target / "game/maps/farm_coop.tscn").read_text(encoding="utf-8")
    assert (target / "generated/scenes/farm/animals/hen__hen.tscn").is_file()
    # the pond: the pack's water tile on the ground at the plan's cells, and those cells fill
    # the can
    view = _map_view(target, godot_exe, FARM_MAPS[0])
    ground = _cells(view, "Ground")
    tiles = sorted(set(ground.values()), key=lambda tile: -list(ground.values()).count(tile))
    assert len(tiles) == 2, "the ground, and the water"
    water = {tuple(c) for c in plan["water"]["cells"]}
    assert {c for c, tile in ground.items() if tile == tiles[1]} == water
    assert {c for c, tile in _cells(view, "Soil").items() if tile == WATER_MARK} == water
    where = {e["name"]: (e["x"], e["y"]) for e in view["entities"]}
    assert where["ShippingBin"] == _at(plan["bin"]["cell"])
    assert "Coop" not in where, "the pack has no coop: it is drawn in the map itself"
    x, y, wide, high = coop["rect"]
    assert '[node name="Coop" type="StaticBody2D" parent="YSorted/Entities"' in scene
    middle = _at([x + wide - 1, y + high - 1])
    assert f"position = Vector2({middle[0]:g}, {middle[1]:g})" in scene, (
        "the drawn coop stands on the cell of its footprint nearest the camera"
    )


# --------------------------------------------------------------------------- Stone isle (T17.17)
#
# The isometric sample pack as a turn-based game, made the way *Try the sample* makes it: the
# bundled profile, the starter the catalog suggests, the default options. It is the first
# isometric pack of the repository whose names say on which sides its pieces join, so its map
# lays its path and its wall from them, and its house stands on four diamonds.

ISLE = REPO / "sample_pack_iso"
ISLE_FOOT = (40, 22)
ISLE_NOTES = {"ADAPT-003"}  # what a sample may say: that its profile was found
SIDES = {"n": (0, -1), "e": (1, 0), "s": (0, 1), "w": (-1, 0)}


def _isle_config(archetype: str = "turn_based") -> config.GeneratorConfig:
    from rpggen.core import mapping, profiles
    from rpggen.gui.models import project_model

    sample = project_model.sample("iso")
    assert (sample.key, sample.archetype, sample.projection) == ("iso", "turn_based", "isometric")
    pack = REPO / sample.folder
    assert pack == ISLE
    profiles.install_profile(pack / sample.profile)
    opened = archive.open_pack(pack, set(), pack_id=sample.folder)
    cat, _issues, _made = catalog.assemble([(opened, inventory.build_inventory(opened))], None, [])
    cfg = config.default_for(
        sample.name,
        [config.pack_ref_from_source(pack, sample.folder)],
        archetype=archetype,
    )
    cfg.projection = sample.projection
    cfg.starter = mapping.default_starter(cat, archetype, sample.projection)
    return cfg


@pytest.fixture(scope="module")
def isle(godot_exe: Path, cache: Path, tmp_path_factory: pytest.TempPathFactory):  # noqa: ANN201
    return _generated(godot_exe, tmp_path_factory.mktemp("iso_isle"), _isle_config())


def _isle_plan(target: Path) -> dict:
    cat = catalog.Catalog.from_json(jsonio.read(paths.from_posix_rel(paths.CATALOG, target)))
    cfg = _isle_config()
    house = map_preview.building_info_for(cat, cfg.starter["building"], "isometric")
    assert house == {"size": [2, 2], "door": [0, 2]}, "the planner sees the house of four cells"
    return map_preview.plan(cfg.starter_map_options(), cfg.seed, house, "turn_based")


def _isle_tiles(target: Path) -> dict[tuple[int, int, int], tuple[str, list[str]]]:
    """(source, column, row) of a tile of the project's tile set -> (its asset, its joins)."""
    data = jsonio.read(paths.from_posix_rel(paths.CATALOG, target))
    cat = catalog.Catalog.from_json(data)
    (definition,) = [t for t in data["tilesets"] if t.get("projection") == "isometric"]
    out = {}
    for asset_id, at in definition["tiles"].items():
        joins = catalog.effective(cat.asset(asset_id)).get("joins") or []
        out[(at["source"], *at["coords"])] = (asset_id, sorted(joins))
    return out


def _joined(cells: dict, tiles: dict) -> dict[tuple[int, int], tuple[str, list[str], list[str]]]:
    """cell -> (the asset of its tile, the sides that tile says it joins on, the sides on which
    the cell has a neighbour among ``cells``)."""
    out = {}
    for cell, tile in cells.items():
        asset_id, joins = tiles[tile]
        beside = sorted(s for s, (dx, dy) in SIDES.items() if (cell[0] + dx, cell[1] + dy) in cells)
        out[cell] = (asset_id, joins, beside)
    return out


def test_stone_isle_is_an_isometric_turn_based_game_that_passes_its_smoke_run(isle) -> None:  # noqa: ANN001
    target, result = isle
    assert not _errors(result)
    assert _smoke(target) == SHARED_STEPS + TURN_BASED_STEPS, "the kind's usual steps, all of them"
    _passed_for_real(target, ())  # the pack has music, a wall, a chest: no step passes with a note
    notes = sorted(
        f"{i.code}: {i.message}"
        for i in result.issues
        if not i.code.startswith("ENV-")
        and (i.severity.value != "info" or i.code not in ISLE_NOTES)
    )
    assert notes == [], "nothing is missing, and nobody is drawn: the pack has its people"
    assert not (target / "generated/iso_kit").exists()
    saved = jsonio.read(paths.from_posix_rel(paths.CONFIG, target))
    assert saved["archetype"] == "turn_based" and saved["projection"] == "isometric"
    tile_set = (target / "generated/tilesets/iso.tres").read_text(encoding="utf-8")
    assert "tile_size = Vector2i(40, 22)" in tile_set, "the diamond that was measured"
    assert sorted(p.name for p in (target / "generated/tilesets").glob("*.tres")) == ["iso.tres"]
    player = (target / "generated/scenes/actors/player.tscn").read_text(encoding="utf-8")
    assert "sample_pack_iso.characters.hero" in player, "the hero of the pack, seen from the front"


def test_the_path_of_stone_isle_is_laid_from_the_pieces_that_name_their_sides(isle) -> None:  # noqa: ANN001
    target, _result = isle
    view = _view(target)
    plan = _isle_plan(target)
    assert view["projection"] == "isometric" and view["tile_size"] == list(ISLE_FOOT)
    roads = {tuple(c) for c in [*plan["path"], *plan["exit_path"]]}
    # a path piece is a whole tile, the diamond with the earth under it: it lies in the place
    # of the ground of its cell, on the ground's own layer, where the tiles before it cover its
    # earth (T17.18: on the layer above it showed as a dark kerb along every path)
    assert not _cells(view, "GroundDetails")
    tiles = _isle_tiles(target)
    paved = {c: t for c, t in _cells(view, "Ground").items() if ".png.path" in tiles[t][0]}
    laid = _joined(paved, tiles)
    assert set(laid) == roads and len(roads) > 30, "every cell of the plan's paths"
    for cell, (asset_id, joins, beside) in laid.items():
        assert ".png.path" in asset_id, (cell, asset_id)
        assert joins == beside, f"{cell}: {asset_id} joins on {joins}, the path goes on at {beside}"
    kinds = {len(joins) for _asset, joins, _beside in laid.values()}
    assert {1, 2} <= kinds, "ends and pieces between them"
    assert len({asset for asset, _j, _b in laid.values()}) >= 4, "straights, corners and ends"
    corners = [a for a, joins, _b in laid.values() if "".join(joins) in ("en", "es", "sw", "nw")]
    assert corners, "the path turns, and a corner piece is laid where it does"
    log = (target / "rpggen/logs/godot_build.log").read_text(encoding="utf-8", errors="replace")
    assert "were laid with the nearest piece" not in log, "the pack has a piece for every cell"


def test_the_walls_of_stone_isle_are_painted_and_join(isle) -> None:  # noqa: ANN001
    target, _result = isle
    view = _view(target)
    plan = _isle_plan(target)
    w, h = plan["size"]
    ring = {(x, y) for x in range(w) for y in range(h) if x in (0, w - 1) or y in (0, h - 1)}
    # the near sides on the layer that sorts with who stands by them, the far sides (the first
    # row and the first column) in the place of the ground, where nothing shows of the earth
    # under them (T17.18: over the ground it was a brown footing along the two far walls)
    tiles = _isle_tiles(target)
    near = _cells(view, "Props")
    far = {c: t for c, t in _cells(view, "Ground").items() if ".png.wall" in tiles[t][0]}
    assert set(far) == {c for c in ring if 0 in c} - {tuple(plan["exit_gap"])}
    assert not set(near) & set(far) and all(0 not in c for c in near)
    walls = _joined({**near, **far}, tiles)
    assert set(walls) == ring - {tuple(plan["exit_gap"])}, "the edge of the map, less its way out"
    assert not _cells(view, "Walls"), "a wall rises: it is sorted with who stands by it"
    for cell, (asset_id, joins, beside) in walls.items():
        assert ".png.wall" in asset_id, (cell, asset_id)
        assert joins == beside, f"{cell}: {asset_id} joins on {joins}, the wall goes on at {beside}"
    pieces = {"".join(joins) for _asset, joins, _beside in walls.values()}
    assert {"ns", "ew", "es", "sw", "en", "nw"} <= pieces, "straights and the four corners"
    assert len([p for p in pieces if len(p) == 1]) == 2, "an end on each side of the way out"
    starter = (target / MAPS[0]).read_text(encoding="utf-8")
    assert starter.count('parent="BorderCollision"') == len(far), (
        "the near walls block by their own diamonds, the far ones by an unseen diamond each"
    )


def test_the_house_of_stone_isle_stands_on_its_four_cells(isle) -> None:  # noqa: ANN001
    target, _result = isle
    view = _view(target)
    plan = _isle_plan(target)
    (first,) = plan["buildings"]
    cells = {(first[0] + dx, first[1] + dy) for dx in range(2) for dy in range(2)}
    house = next(e for e in view["entities"] if e["name"] == "house_0")
    # the picture's diamond is the one of its four cells nearest the camera
    nearest = (first[0] + 1, first[1] + 1)
    assert (house["x"], house["y"]) == iso_math.cell_to_screen(*nearest, *ISLE_FOOT)
    scene = (target / "generated/scenes/objects/sample_pack_iso__png__house_0.tscn").read_text(
        encoding="utf-8"
    )
    assert "metadata/stands_on = [2, 2]" in scene
    # what blocks is the outline of the four diamonds around that cell: 80 x 44
    assert "polygon = PackedVector2Array(0, -33, 40, -11, 0, 11, -40, -11)" in scene
    # nothing else of the plan stands on them, and the path ends at the cell before the door
    taken = [
        tuple(c)
        for key in ("decorations", "npcs", "chests", "enemies", "path", "exit_path")
        for c in plan[key]
    ]
    assert not cells & {*taken, tuple(plan["spawn"])}
    door = tuple(plan["doors"][0])
    assert door == (first[0], first[1] + 2) and door in {tuple(c) for c in plan["path"]}
    where = {e["name"]: (e["x"], e["y"]) for e in view["entities"]}
    assert where["Player"] == iso_math.cell_to_screen(*plan["spawn"], *ISLE_FOOT)
    assert where["Chest1"] == iso_math.cell_to_screen(*plan["chests"][0], *ISLE_FOOT)
    for i, cell in enumerate(plan["decorations"]):
        assert where[f"Decor{i + 1}"] == iso_math.cell_to_screen(*cell, *ISLE_FOOT)


def test_a_second_run_of_stone_isle_changes_nothing(isle, godot_exe: Path) -> None:  # noqa: ANN001
    target, _result = isle
    kept = {
        p.relative_to(target).as_posix(): p.read_bytes()
        for folder in ("generated/scenes", "game/data", "game/maps", "generated/tilesets")
        for p in sorted((target / folder).rglob("*"))
        if p.is_file() and not p.name.endswith(".import")
    }
    for rel in ("project.godot", paths.CATALOG, paths.CONFIG, paths.LEDGER):
        kept[rel] = (target / rel).read_bytes()
    assert len(kept) > 30
    again = orchestrator.run_in_memory(_isle_config(), None, target, godot_exe)
    assert again.ok, _errors(again)
    assert [i.code for i in again.issues if i.code == orchestrator.REPEAT_CODE], (
        "nothing changed: the build and the checks are not repeated"
    )
    for rel, data in kept.items():
        assert (target / rel).read_bytes() == data, rel


# ------------------------------------------------- Stone isle: the other sequences (T17.18)
#
# Isometric has no sequence of its own: the shared one and the action RPG's run over the sample
# as they are (the racing one in test_m17_iso_racing.py). And what a run writes follows the
# schemas, as the arcade samples' does (test_m16_samples.py).


@pytest.fixture(scope="module")
def isle_arpg(godot_exe: Path, cache: Path, tmp_path_factory: pytest.TempPathFactory):  # noqa: ANN201
    return _generated(godot_exe, tmp_path_factory.mktemp("iso_isle_arpg"), _isle_config("arpg"))


def test_stone_isle_is_an_isometric_action_rpg_that_passes_its_smoke_run(isle_arpg) -> None:  # noqa: ANN001
    """The pack's own hero is 16 px wide on diamonds of 23 px a step: the steps that put an
    enemy "a tile away" to be struck asked the tile where they should have asked the bodies,
    and the swing ended 5 px short of it (`player_attack_hits`). They ask the bodies now."""
    target, result = isle_arpg
    assert not _errors(result)
    assert _smoke(target) == SHARED_STEPS + ARPG_STEPS, "the kind's usual steps, all of them"
    assert "SCRIPT ERROR" not in (target / "rpggen/logs/godot_smoke.log").read_text(
        encoding="utf-8", errors="replace"
    )
    archetypes = target / "addons/rpg_runtime/archetypes"
    assert sorted(p.name for p in archetypes.iterdir()) == ["arpg"]
    saved = jsonio.read(paths.from_posix_rel(paths.CONFIG, target))
    assert (saved["archetype"], saved["projection"]) == ("arpg", "isometric")
    player = (target / "generated/scenes/actors/player.tscn").read_text(encoding="utf-8")
    assert "sample_pack_iso.characters.hero" in player, "the pack's own hero, not the drawn one"
    assert "tile_size = 23.0" in player, "one step on diamonds of 40 x 22"
    assert not (target / "generated/iso_kit").exists()
    for rel in MAPS:
        assert 'path="res://generated/tilesets/iso.tres"' in (target / rel).read_text(
            encoding="utf-8"
        )


def test_stone_isle_follows_the_schemas(
    isle,  # noqa: ANN001
    godot_exe: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """What the run wrote, and the document of `rpggen generate --json` on the project (a run
    that finds nothing changed), each against its schema: what test_m16_samples.py checks of
    the arcade samples, less the world plan, which a village without areas does not have."""
    import json

    from rpggen import cli, schema

    target, _result = isle
    for rel in (paths.RESULTS_BUILD, paths.RESULTS_VALIDATE, paths.RESULTS_SMOKE):
        doc = jsonio.read(target / rel)
        schema.validate("results", doc)
        assert doc["ok"] is True, rel
    saved = jsonio.read(target / paths.CONFIG)
    schema.validate("config", saved)
    assert (saved["archetype"], saved["projection"]) == ("turn_based", "isometric")
    schema.validate("ledger", jsonio.read(target / paths.LEDGER))
    schema.validate("catalog", jsonio.read(target / paths.CATALOG))
    capsys.readouterr()
    code = cli.main(
        [
            "generate",
            "--config",
            str(target / paths.CONFIG),
            "--target",
            str(target),
            "--godot",
            str(godot_exe),
            "--json",
        ]
    )
    document = json.loads(capsys.readouterr().out)
    schema.validate("cli", document)
    assert code == 0 and document["ok"] is True and document["failed_phase"] is None
    assert not [i for i in document["issues"] if i["severity"] != "info"], document["issues"]
    assert orchestrator.REPEAT_CODE in {i["code"] for i in document["issues"]}
