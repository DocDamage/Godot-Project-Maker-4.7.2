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
    # the wall rises, so it is painted where it is sorted with who stands by it: the Y-sorted
    # Props layer, a ring of the plan's size with a gap for the way to the field
    view = _view(target)
    plan = _plan(target, "turn_based")
    w, h = plan["size"]
    props = next(layer for layer in view["layers"] if layer["name"] == "Props")
    ring = {(x, y) for x in range(w) for y in range(h) if x in (0, w - 1) or y in (0, h - 1)}
    assert {(c[0], c[1]) for c in props["cells"]} == ring - {tuple(plan["exit_gap"])}
    assert not next(layer for layer in view["layers"] if layer["name"] == "Walls")["cells"]
    starter = (target / MAPS[0]).read_text(encoding="utf-8")
    assert "BorderCollision" not in starter, "the wall tiles block by their own diamonds"


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
