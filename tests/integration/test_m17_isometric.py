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
    "shop_stock_and_repair",
    "quest_journal",
    "party_members",
    "followers_trail",
    "sequence_plays",
    "keys_and_switches",
    "credits_screen",
    "mutate_then_load",
    "pause_menu",
    "skills_and_achievements",
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


# what a report says of the computer, not of the pack: a missing tool (ENV-) or a Godot
# that crashed while importing and was run again (BUILD-006)
MACHINE_NOTES = ("ENV-", "BUILD-006")


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
# the steps of the cave (T17.24): in a farm that does not fight each passes with a note
FARM_CAVE_STEPS = [
    "buy_a_weapon",
    "enter_the_cave",
    "defeat_an_enemy",
    "bring_back_what_it_left",
    "defeated_and_wake_at_home",
]
# the steps of the added maps (T17.23): in a farm without a forest or a beach each passes
# with a note; the cave's (T17.24) after them
FARM_ADDED_STEPS = ["visit_the_forest", "fish_at_the_beach", *FARM_CAVE_STEPS]
# the steps of the festivals and the birthdays (T17.25): played on diamonds as on squares
FARM_EVENT_STEPS = [
    "read_the_calendar",
    "birthday_gift",
    "festival_is_announced",
    "a_year_of_festivals",
    "egg_hunt",
]
# the steps of marriage (T17.26): played on diamonds as on squares
FARM_MARRIAGE_STEPS = [
    "buy_a_bouquet",
    "court_with_a_bouquet",
    "propose_with_a_pendant",
    "the_wedding",
    "spouse_at_home",
]
# a new game starts in the farmhouse; the shared steps are played in the village
FARM_SEQUENCE = [
    SHARED_STEPS[0],
    *FARM_HOUSE_STEPS,
    *SHARED_STEPS[1:],
    *FARM_STEPS,
    *FARM_ANIMAL_STEPS,
    *FARM_ADDED_STEPS,
    *FARM_EVENT_STEPS,
    *FARM_MARRIAGE_STEPS,
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
    _passed_for_real(target, (*ABSENT, "catch_a_fish", *FARM_ANIMAL_STEPS, *FARM_ADDED_STEPS))
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
    # nothing of the farm passes with a note but the steps of the added maps it does not have
    _passed_for_real(target, (*ABSENT, *FARM_ADDED_STEPS))
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
        if not i.code.startswith(MACHINE_NOTES)
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


# ------------------------------------------- a pack of pieces: walls, a house, a farm (T17.22)
#
# The synthetic pack ``iso_kit`` has no whole wall tile and no whole house: its walls stand
# along one side of a diamond (in four turns, and turn 0 is not the north side), one of them
# has a door, one a window, and its roof is a tile. The edge of its maps is laid from the
# segments by the side each stands on, its village has a house put together from the pieces,
# and the smoke run of the kind walks into the wall and in and out of that house.

KIT_PACK = REPO / "test_packs" / "synthetic" / "iso_kit"
KIT_FOOT = (64, 36)
KIT_HOUSE = "generated/scenes/objects/rpggen__iso_house.tscn"
KIT_SHORT = "iso_kit.png.stone_short_wall_01_"
# the side the turn 0, 1, 2, 3 of a wall of the pack stands along
KIT_TURN_SIDES = "eswn"
# what the pack does not have: music, a chest (and the demo quest that needs one). It has
# walls and a house: ``collision_blocks``, ``enter_building`` and ``exit_building`` are played.
KIT_ABSENT = ("map_music", "chest_open", "quest_journal")


def _kit_config(archetype: str = "turn_based") -> config.GeneratorConfig:
    from rpggen.core import mapping

    opened = archive.open_pack(KIT_PACK, set(), pack_id="iso_kit")
    cat, _issues, _made = catalog.assemble([(opened, inventory.build_inventory(opened))], None, [])
    cfg = config.default_for(
        "Kit Vale", [config.pack_ref_from_source(KIT_PACK, "iso_kit")], archetype=archetype
    )
    cfg.projection = "isometric"
    cfg.starter = mapping.default_starter(cat, archetype, "isometric")
    return cfg


@pytest.fixture(scope="module")
def kit_game(godot_exe: Path, cache: Path, tmp_path_factory: pytest.TempPathFactory):  # noqa: ANN201
    return _generated(godot_exe, tmp_path_factory.mktemp("iso_kit"), _kit_config())


def _kit_plan(target: Path) -> dict:
    cat = catalog.Catalog.from_json(jsonio.read(paths.from_posix_rel(paths.CATALOG, target)))
    cfg = _kit_config()
    house = map_preview.building_info_for(cat, "", "isometric")
    assert house == {"size": [2, 2], "door": [0, 2]}, "a kit of pieces counts as a house"
    return map_preview.plan(cfg.starter_map_options(), cfg.seed, house, "turn_based")


def _kit_tiles(target: Path) -> dict[tuple[int, int, int], tuple[str, str]]:
    """(source, column, row) of a tile of the project's tile set -> (its asset, its edge)."""
    data = jsonio.read(paths.from_posix_rel(paths.CATALOG, target))
    cat = catalog.Catalog.from_json(data)
    (definition,) = [t for t in data["tilesets"] if t.get("projection") == "isometric"]
    out = {}
    for asset_id, at in definition["tiles"].items():
        edge = catalog.effective(cat.asset(asset_id)).get("edge") or ""
        out[(at["source"], *at["coords"])] = (asset_id, edge)
    return out


def test_a_pack_of_pieces_is_a_turn_based_game_that_passes_its_smoke_run(kit_game) -> None:  # noqa: ANN001
    target, result = kit_game
    assert not _errors(result)
    assert _smoke(target) == SHARED_STEPS + TURN_BASED_STEPS, "the kind's usual steps"
    _passed_for_real(target, KIT_ABSENT)
    saved = jsonio.read(paths.from_posix_rel(paths.CONFIG, target))
    assert (saved["archetype"], saved["projection"]) == ("turn_based", "isometric")
    assert "building" not in saved.get("starter", {}), "no pack drew a house to choose"
    for rel in [*MAPS, KIT_HOUSE]:
        assert (target / rel).is_file(), rel


def test_the_edge_of_its_map_is_laid_from_wall_segments_by_their_sides(kit_game) -> None:  # noqa: ANN001
    target, _result = kit_game
    view = _view(target)
    plan = _kit_plan(target)
    w, h = plan["size"]
    gap = tuple(plan["exit_gap"])
    ring = {(x, y) for x in range(w) for y in range(h) if x in (0, w - 1) or y in (0, h - 1)}
    tiles = _kit_tiles(target)
    props = {cell: tiles[tile] for cell, tile in _cells(view, "Props").items()}
    assert set(props) == ring - {gap}, "a segment on every cell of the edge, less the way out"
    assert not _cells(view, "Walls")
    wanted = {
        "n": KIT_SHORT + "3",
        "e": KIT_SHORT + "0",
        "s": KIT_SHORT + "1",
        "w": KIT_SHORT + "2",
    }
    for (x, y), (asset_id, edge) in props.items():
        if x in (0, w - 1) and y in (0, h - 1):
            continue  # a corner: below
        side = "n" if y == 0 else "s" if y == h - 1 else "w" if x == 0 else "e"
        assert (asset_id, edge) == (wanted[side], side), f"{(x, y)}: the lowest wall, for {side}"
        assert KIT_TURN_SIDES[int(asset_id[-1])] == side, "the side is the piece's, not its turn"
    # a corner cell has a piece for each of its two sides, on two layers
    under = {cell: tiles[tile] for cell, tile in _cells(view, "GroundDetails").items()}
    over = {cell: tiles[tile] for cell, tile in _cells(view, "Overhead").items()}
    assert (props[(0, 0)][1], under[(0, 0)][1]) == ("n", "w")
    assert (props[(w - 1, 0)][1], under[(w - 1, 0)][1]) == ("e", "n")
    assert (props[(0, h - 1)][1], under[(0, h - 1)][1]) == ("s", "w")
    assert (props[(w - 1, h - 1)][1], over[(w - 1, h - 1)][1]) == ("e", "s")
    assert len(under) == 3 and len(over) == 1
    # the ground under a segment stays: a segment fills no diamond
    ground = _cells(view, "Ground")
    assert ring <= set(ground) and len(ground) == w * h
    starter = (target / MAPS[0]).read_text(encoding="utf-8")
    assert "BorderCollision" not in starter, "the tiles block by their own diamonds"
    # the room of the house has walls of the same segments, and its way out
    room = (target / MAPS[1]).read_text(encoding="utf-8")
    assert "BorderCollision" not in room and 'name="Props"' in room


def test_its_village_has_a_house_put_together_from_the_pieces(kit_game) -> None:  # noqa: ANN001
    import re

    target, _result = kit_game
    view = _view(target)
    plan = _kit_plan(target)
    houses = [e for e in view["entities"] if e["scene"] == "res://" + KIT_HOUSE]
    assert len(houses) == len(plan["buildings"]) >= 1, "a house of pieces for every planned house"
    first = plan["buildings"][0]
    nearest = (first[0] + 1, first[1] + 1)
    assert (houses[0]["x"], houses[0]["y"]) == iso_math.cell_to_screen(*nearest, *KIT_FOOT)
    scene = (target / KIT_HOUSE).read_text(encoding="utf-8")
    assert "metadata/stands_on = [2, 2]" in scene and 'metadata/role = "BUILDING"' in scene
    # it blocks the outline of its four diamonds, and has its door and the spawn before it
    assert "polygon = PackedVector2Array(0, -54, 64, -18, 0, 18, -64, -18)" in scene
    for node in ("Left", "Right", "Footprint", "Entrance", "ExitSpawn"):
        assert f'[node name="{node}"' in scene, node
    # a piece on every side of the rim: eight places, one of them the door, above the plan's
    # door cell (the south side of the cell (0, 1) of its footprint); a roof over each cell
    names = set(re.findall(r'\[node name="((?:Wall|Door|Window|Roof)_[^"]+)"', scene))
    sides = {name.split("_", 1)[1] for name in names if not name.startswith("Roof")}
    assert sides == {"0_0_n", "0_0_w", "1_0_n", "1_0_e", "0_1_w", "0_1_s", "1_1_e", "1_1_s"}
    assert [name for name in names if name.startswith("Door")] == ["Door_0_1_s"]
    assert {name for name in names if name.startswith("Roof")} == {
        "Roof_0_0", "Roof_1_0", "Roof_0_1", "Roof_1_1",
    }  # fmt: skip
    door = tuple(plan["doors"][0])
    assert door == (first[0], first[1] + 2) and door in {tuple(c) for c in plan["path"]}
    # the room behind its door is the room every house of the kind has
    starter = (target / MAPS[0]).read_text(encoding="utf-8")
    assert 'target_map = "res://game/maps/interior_1.tscn"' in starter
    room = (target / MAPS[1]).read_text(encoding="utf-8")
    assert "rpggen__iso_house_exit" in room, "leaving the room returns to the house's door"
    # nothing of the plan stands on its footprint
    cells = {(first[0] + dx, first[1] + dy) for dx in range(2) for dy in range(2)}
    taken = [
        tuple(c)
        for key in ("decorations", "npcs", "chests", "enemies", "path", "exit_path")
        for c in plan[key]
    ]
    assert not cells & {*taken, tuple(plan["spawn"])}


def test_a_second_run_of_the_pack_of_pieces_changes_nothing(kit_game, godot_exe: Path) -> None:  # noqa: ANN001
    target, _result = kit_game
    kept = {
        rel: (target / rel).read_bytes()
        for rel in [
            *MAPS,
            KIT_HOUSE,
            "generated/tilesets/iso.tres",
            "generated/scenes/actors/player.tscn",
            "project.godot",
            paths.CATALOG,
            paths.CONFIG,
            paths.LEDGER,
        ]
    }
    again = orchestrator.run_in_memory(_kit_config(), None, target, godot_exe)
    assert again.ok, _errors(again)
    assert [i.code for i in again.issues if i.code == orchestrator.REPEAT_CODE], (
        "nothing changed: the build and the checks are not repeated"
    )
    for rel, data in kept.items():
        assert (target / rel).read_bytes() == data, rel


@pytest.mark.farm
def test_a_farm_on_the_pack_of_pieces_is_fenced_and_has_a_house_of_pieces(
    godot_exe: Path, cache: Path, tmp_path: Path
) -> None:
    cfg = _kit_config("farm")
    cfg.starter_map["animals"] = "coop"
    target = tmp_path / "out"
    result = orchestrator.run_in_memory(cfg, None, target, godot_exe)
    assert result.ok, _errors(result)
    assert "save_and_load" in _smoke(target), "the farm's whole sequence"
    farm = (target / "game/maps/farm.tscn").read_text(encoding="utf-8")
    # the buildings of the plan are put together from the pieces, each on its own footprint
    for name in ("House", "Coop"):
        assert f'parent="YSorted/Entities/{name}/Left"' in farm, f"{name} is made of pieces"
        assert f'parent="YSorted/Entities/{name}/Right"' in farm
    assert 'name="Door_' in farm and 'name="Roof_' in farm and "metadata/kit" in farm
    # the farm's edge is the pack's fence, by its sides; the yard's fence its segments
    view = _map_view(target, godot_exe, "game/maps/farm.tscn")
    tiles = _kit_tiles(target)
    edge = {tiles[tile][0][:-1] for tile in _cells(view, "Props").values()}
    assert edge == {"iso_kit.png.wood_fence_01_"}, "a farm is fenced where the pack has a fence"
    assert 'name="Fence_coop_' in farm and "BorderCollision" not in farm
    fence = farm[farm.index('[node name="Fence_coop_') :]
    assert '[node name="Sprite" type="Sprite2D"' in fence


# --------------------------------------------------------------------------- the dock (T17.27)
#
# The asset dock's placement, run where its undo exists: in the editor. A test-only plugin
# (tests/integration/dock_probe) is copied into a copy of *Stone isle* and the editor is started
# headless; the plugin opens the starter map, places library scenes with the dock's own code
# (`Placement.place_new`, the double click, and the dock's own `_fix_dropped`, what follows a
# drop), undoes and redoes each through the editor's history and saves the scene; then the
# dock's world tools add a trigger area, a gate and a floor switch, which are not saved. Nobody
# moves a mouse: the 2D view's own drag and drop is not run. The run (tests/integration/
# dock_probe_run.py) also holds the dock's three old faults mended: Ctrl+Z logs nothing, a
# double click is saved as an instance of its scene, a second copy has a readable name.

ISLE_OBJECTS = "res://generated/scenes/objects/sample_pack_iso__"
ISLE_PEOPLE = "res://generated/scenes/actors/characters/sample_pack_iso__characters__"
# (the scene, the diamond the mouse is over, where on it, how it is placed, the node's name: a
# second copy of one asset gets the name the editor gives one, T17.27's third fault mended; the
# scene of a person has a root called Npc, so the fisher is the second Npc)
DOCK_PLACES = [
    (ISLE_OBJECTS + "png__treepine.tscn", (4, 3), (6, -3), "double_click", "treepine"),
    (ISLE_OBJECTS + "png__treeoak.tscn", (9, 5), (-9, 2), "drop", "treeoak"),
    (ISLE_OBJECTS + "png__rock.tscn", (30, 3), (15, 0), "drop", "rock"),
    (ISLE_OBJECTS + "png__house_1.tscn", (20, 20), (-7, 4), "drop", "house_1"),
    (ISLE_OBJECTS + "png__house_2.tscn", (31, 5), (0, -9), "double_click", "house_2"),
    (ISLE_PEOPLE + "villager_mason.tscn", (21, 21), (8, -4), "drop", "Npc"),
    (ISLE_PEOPLE + "villager_fisher.tscn", (7, 5), (-6, -4), "double_click", "Npc2"),
    (ISLE_OBJECTS + "items__chest.tscn", (5, 20), (-10, 0), "drop", "Chest"),
    # a second copy of a tree, dropped and double-clicked
    (ISLE_OBJECTS + "png__treeoak.tscn", (11, 8), (4, 2), "drop", "treeoak2"),
    (ISLE_OBJECTS + "png__treepine.tscn", (13, 10), (-5, -1), "double_click", "treepine2"),
]


def test_the_dock_places_on_the_diamonds_of_stone_isle(
    isle,  # noqa: ANN001
    godot_exe: Path,
    tmp_path: Path,
) -> None:
    """What the dock places in the generated isometric map stands on the middle of the diamond
    under the mouse, among the Y-sorted entities, as one step of the editor's undo history
    that Ctrl+Z takes back and redo brings again; a house covers its four cells; the saved map
    has them where the builder would have put them, and the game still plays its whole
    sequence."""
    from rpggen.core import godot
    from tests.integration import dock_probe_run

    target, _result = isle
    plan = _isle_plan(target)
    taken = {
        tuple(c)
        for key in ("decorations", "npcs", "chests", "enemies", "path", "exit_path")
        for c in plan[key]
    }
    places = []
    for scene, cell, off, how, _name in DOCK_PLACES:
        assert cell not in taken, "a free diamond of the plan"
        x, y = iso_math.cell_to_screen(*cell, *ISLE_FOOT)
        assert iso_math.screen_to_cell(x + off[0], y + off[1], *ISLE_FOOT) == cell
        places.append({"scene": scene, "at": [x + off[0], y + off[1]], "how": how})
    wanted = {"map": "res://" + MAPS[0], "snap": 16, "save": True, "places": places}
    run = dock_probe_run.run_probe(target, tmp_path / "proj", godot_exe, wanted)
    project, report = run.project, run.report
    exe = godot.find_console_exe(godot_exe)
    logs = project / "rpggen/logs"
    # the three old faults of the dock (Ctrl+Z, the saved instance, the name), mended
    dock_probe_run.check_the_faults_are_mended(run, MAPS[0])
    assert [seen["placed"]["name"] for seen in report["places"]] == [p[4] for p in DOCK_PLACES], (
        "a second copy is named as the editor names one"
    )
    assert report["footprint"] == list(ISLE_FOOT), "the dock asks the map for its diamond"
    assert report["saved"] == 0, "the editor saved the scene"
    assert len(report["places"]) == len(DOCK_PLACES)
    for seen, (scene, cell, off, how, _name) in zip(report["places"], DOCK_PLACES, strict=True):
        middle = list(iso_math.cell_to_screen(*cell, *ISLE_FOOT))
        mouse = [middle[0] + off[0], middle[1] + off[1]]
        placed = seen["placed"]
        assert [placed["x"], placed["y"]] == middle, f"{scene} on the diamond {cell}"
        assert placed["cell"] == list(cell) and placed["middle"] == middle
        assert placed["parent"] == "YSorted/Entities" and placed["owner"] is True
        assert seen["action"].startswith("Place ") and seen["one_step"] is True
        assert seen["undo_ok"] is True and seen["redo_ok"] is True
        if how == "double_click":  # Ctrl+Z takes the new node out of the map
            assert seen["undone_in_tree"] is False
        else:  # ... and puts a dropped one back where the editor dropped it
            undone = seen["undone"]
            assert (undone["parent"], [undone["x"], undone["y"]]) == (".", mouse)
            assert seen["status"].startswith("Placed ")
            assert seen["status"].endswith(f" on the diamond ({cell[0]}, {cell[1]}).")
        again = seen["redone"]
        assert (again["parent"], [again["x"], again["y"]]) == ("YSorted/Entities", middle)
    by_scene = {seen["scene"]: seen for seen in report["places"]}
    house = by_scene[ISLE_OBJECTS + "png__house_1.tscn"]
    assert house["stands_on"] == [2, 2]
    assert sorted(map(tuple, house["cells"])) == [(19, 19), (19, 20), (20, 19), (20, 20)], (
        "the diamond under the mouse is the one of its four cells nearest the camera"
    )
    chest = by_scene[ISLE_OBJECTS + "items__chest.tscn"]
    assert chest["placed"]["entity_id"] == "starter_map_chest_002", "the id a square map gives"
    assert by_scene[ISLE_OBJECTS + "png__treeoak.tscn"]["placed"]["entity_id"] == ""
    # the world tools: on the middle of a diamond, and what blocks or triggers is the diamond
    unit = iso_math.unit(*ISLE_FOOT)
    middle = iso_math.cell_to_screen(0, 0, *ISLE_FOOT)
    diamond = [[x - middle[0], y - middle[1]] for x, y in iso_math.diamond(0, 0, *ISLE_FOOT)]
    assert report["unit"] == unit
    trigger, gate, plate = report["tools"]
    assert [tool["kind"] for tool in report["tools"]] == ["trigger", "gate", "plate"]
    for tool in report["tools"]:
        assert [tool["x"], tool["y"]] == tool["middle"], f"{tool['kind']}: on its diamond"
        assert tool["one_step"] is True and tool["undo_ok"] is True and tool["redo_ok"] is True
        assert tool["owner"] is True
    assert (trigger["parent"], trigger["shape"]) == ("Triggers", "ConvexPolygonShape2D")
    assert (gate["parent"], gate["shape"]) == ("YSorted/Entities", "ConvexPolygonShape2D")
    assert trigger["points"] == diamond and gate["points"] == diamond
    assert trigger["shape_owner"] is True and gate["shape_owner"] is True
    assert gate["size"] == [unit, unit], "a tile is one step on the diamonds"
    assert (plate["shape"], plate["size"]) == ("", [unit * 0.75, unit * 0.75])
    # the saved map: what was there is where it was, what was placed is on its diamond
    before = _view(target)
    after = _map_view(project, godot_exe, MAPS[0])
    was = {e["name"]: (e["x"], e["y"]) for e in before["entities"]}
    now = {e["name"]: (e["x"], e["y"]) for e in after["entities"]}
    assert {name: now.get(name) for name in was} == was
    added = sorted(at for name, at in now.items() if name not in was)
    wanted = sorted(
        iso_math.cell_to_screen(*cell, *ISLE_FOOT) for _s, cell, _o, _h, _n in DOCK_PLACES
    )
    assert added == wanted
    for layer in ("Ground", "Props"):
        assert _cells(after, layer) == _cells(before, layer), "no tile moved"
    # and the game plays as it did, with them in it
    (project / paths.RESULTS_SMOKE).unlink()
    smoke = godot.run_godot(
        exe,
        project,
        orchestrator.smoke_args("turn_based", "dock_on_diamonds"),
        timeout_s=godot.SMOKE_TIMEOUT_S,
        log_name="dock_smoke",
        log_dir=logs,
    )
    assert smoke.returncode == 0, smoke.stdout[-3000:]
    assert _smoke(project) == SHARED_STEPS + TURN_BASED_STEPS


# --------------------------------------------------------------------------- added maps (T17.23)


@pytest.fixture(scope="module")
def iso_forest(godot_exe: Path, cache: Path, tmp_path_factory: pytest.TempPathFactory):  # noqa: ANN201
    """The isometric farm with a forest and a beach among its added maps."""
    cfg = _farm_config()
    cfg.starter_map["added_maps"] = [{"name": "Old woods"}, {"name": "North shore"}]
    return _generated(godot_exe, tmp_path_factory.mktemp("iso_forest"), cfg)


def test_an_isometric_farm_with_a_forest_and_a_beach(iso_forest, godot_exe: Path) -> None:  # noqa: ANN001
    """The same recipe on diamonds: the farmer walks to the forest and back, and fishes from
    the beach of a farm that has a well. The added maps are painted with the project's tile
    set, their markers lie on the diamonds of the plan's cells, and the door of every trail
    is a diamond on the farm."""
    from rpggen.core import added_map_plan, farm_plan

    target, result = iso_forest
    assert not _errors(result)
    assert _smoke(target) == FARM_SEQUENCE
    # the two steps of the added maps are played; the pond's step is not (a well)
    _passed_for_real(target, (*ABSENT, "catch_a_fish", *FARM_ANIMAL_STEPS, *FARM_CAVE_STEPS))
    plan = _farm_plan(target)
    assert farm_plan.check(plan) == [] and plan["water"]["kind"] == "well"
    assert [(e["id"], e["kind"]) for e in plan["added"]] == [
        ("farm_map_1", "forest"),
        ("farm_map_2", "beach"),
    ]
    forage = jsonio.read(target / "rpggen/world_plan.json")["farm"]["forage"]
    assert forage["fishing"] is True, "the rod is sold for the beach"
    trails = (target / "generated/scenes/farm/trails.tscn").read_text(encoding="utf-8")
    assert "ConvexPolygonShape2D" in trails and "RectangleShape2D" not in trails
    farm_scene = (target / FARM_MAPS[0]).read_text(encoding="utf-8")
    assert '[node name="Trails" parent="."' in farm_scene
    for entry in plan["added"]:
        scene = (target / entry["map"]).read_text(encoding="utf-8")
        assert 'path="res://generated/tilesets/iso.tres"' in scene
        assert f'metadata/farm_kind = "{entry["kind"]}"' in scene
        view = _map_view(target, godot_exe, entry["map"])
        cols, rows = entry["size"]
        ground = _cells(view, "Ground")
        inside = {(x, y) for x in range(1, cols - 1) for y in range(1, rows - 1)}
        assert inside <= set(ground), "the whole map has ground under it"
        # every marker stands on the middle of the diamond of its cell
        trail = plan["trails"][entry["trail"]]
        x, y = iso_math.cell_to_screen(trail["cell"][0], trail["cell"][1], *FOOT)
        door = trails.split(f'[node name="to_{entry["id"]}"')[1].split("[node")[0]
        assert f"position = Vector2({x:g}, {y:g})" in door
        lines = scene.splitlines()
        spots = []
        for at, line in enumerate(lines):
            if line.startswith('[node name="Spot') and 'parent="Forage"' in line:
                px, py = lines[at + 1].removeprefix("position = Vector2(").rstrip(")").split(", ")
                spots.append(iso_math.screen_to_cell(float(px), float(py), *FOOT))
        assert spots == [tuple(c) for c in entry["spots"]]
        assert set(spots) <= added_map_plan.reached_cells(entry)
    beach = plan["added"][1]
    beach_scene = (target / beach["map"]).read_text(encoding="utf-8")
    soil = _cells(_map_view(target, godot_exe, beach["map"]), "Soil")
    wet = {tuple(c) for c in beach["water"]["cells"]}
    assert set(soil) == wet, "the cells of the sea say they are water, and no other cell does"
    assert 'metadata/farm_water = "sea"' in beach_scene and '[node name="Sand"' in beach_scene


@pytest.fixture(scope="module")
def iso_cave(godot_exe: Path, cache: Path, tmp_path_factory: pytest.TempPathFactory):  # noqa: ANN201
    """The isometric farm with Combat on (T17.24): it has a cave."""
    cfg = _farm_config()
    cfg.features["combat"] = True
    return _generated(godot_exe, tmp_path_factory.mktemp("iso_cave"), cfg)


def test_an_isometric_farm_that_fights_has_a_cave_on_diamonds(iso_cave) -> None:  # noqa: ANN001
    """The cave on diamonds: the farmer buys the sword, walks into the cave, defeats an enemy,
    picks up what it left and carries it home, and is defeated once and wakes at the bed."""
    target, result = iso_cave
    assert not _errors(result)
    assert _smoke(target) == FARM_SEQUENCE
    # the cave's steps are played; the forest's and the beach's are not (there are none)
    _passed_for_real(
        target,
        (*ABSENT, "catch_a_fish", *FARM_ANIMAL_STEPS, "visit_the_forest", "fish_at_the_beach"),
    )
    plan = _farm_plan(target)
    assert [(e["id"], e["kind"], e["name"]) for e in plan["added"]] == [
        ("farm_map_1", "cave", "Cave")
    ]
    cave = plan["added"][0]
    scene = (target / cave["map"]).read_text(encoding="utf-8")
    assert 'path="res://generated/tilesets/iso.tres"' in scene
    assert 'metadata/farm_kind = "cave"' in scene and "is_interior = true" in scene
    assert '[node name="RockWall" type="StaticBody2D"' in scene
    assert "ConvexPolygonShape2D" in scene, "the rock blocks diamonds"
    assert scene.count('entity_id = "farm_map_1_enemy_') == len(cave["enemies"])
    archetypes = target / "addons/rpg_runtime/archetypes"
    assert sorted(p.name for p in archetypes.iterdir()) == ["arpg", "farm"]
    assert (target / "game/data/items/farm_sword.tres").is_file()
