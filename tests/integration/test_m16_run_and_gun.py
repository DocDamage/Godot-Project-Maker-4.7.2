"""Milestone M16, the run and gun (T16.08): the synthetic `platformer` pack as a game with a
soldier on a flat first stage, and the same with a forgiving soldier and a left edge that is a
wall."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from rpggen import jsonio, paths
from rpggen.core import arcade_kit, config, orchestrator

pytestmark = [pytest.mark.integration, pytest.mark.run_and_gun]

REPO = Path(__file__).resolve().parents[2]
PLATFORMER = REPO / "test_packs" / "synthetic" / "platformer"
GUNNER = REPO / "test_packs" / "synthetic" / "gunner"
STEPS = [
    "title_new_game",
    "soldier_runs_and_the_camera_follows",
    "camera_never_goes_back",
    "soldier_jumps",
    "soldier_aims_and_shoots",
    "soldier_crouches",
    "grenade_goes_off",
    "soldier_dies_and_drops_back_in",
    "wave_is_fought",
    "weapon_is_picked_up",
    "trap_stops_the_camera",
    "boss_is_beaten",
    "run_reaches_the_credits",
]
SCENES = [
    "generated/scenes/run_and_gun/soldier.tscn",
    "generated/scenes/run_and_gun/grenade.tscn",
    "generated/scenes/run_and_gun/explosion.tscn",
    "generated/scenes/stages/stage_01.tscn",
    "generated/scenes/combat/combat_mode.tscn",
    "generated/scenes/ui/hud_arcade.tscn",
    "generated/scenes/run_and_gun/weapon_pickup.tscn",
    "generated/scenes/run_and_gun/enemies/runner.tscn",
    "generated/scenes/run_and_gun/enemies/sniper.tscn",
    "generated/scenes/run_and_gun/enemies/turret.tscn",
    "generated/scenes/run_and_gun/enemies/jumper.tscn",
    "generated/scenes/run_and_gun/enemies/wall_cannon.tscn",
    "generated/scenes/run_and_gun/boss_wall.tscn",
    "generated/scenes/run_and_gun/boss_walker.tscn",
    "generated/scenes/run_and_gun/boss_flyer.tscn",
    "generated/scenes/stages/stage_02.tscn",
    "generated/scenes/stages/stage_03.tscn",
]


def _config(**starter_map) -> config.GeneratorConfig:
    cfg = config.default_for(
        "Hard Corps",
        [config.pack_ref_from_source(PLATFORMER, "platformer")],
        archetype="run_and_gun",
    )
    cfg.starter_map = dict(starter_map)
    return cfg


def _errors(result) -> list[str]:
    return [f"{i.code}: {i.message}" for i in result.issues if i.severity.value != "info"]


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


@pytest.fixture(scope="module")
def game(godot_exe: Path, cache: Path, tmp_path_factory: pytest.TempPathFactory):
    target = tmp_path_factory.mktemp("m16_gun") / "out"
    result = orchestrator.run_in_memory(_config(), None, target, godot_exe)
    assert result.ok, _errors(result)
    return target, result


def _smoke(target: Path) -> list[str]:
    smoke = jsonio.read(target / "rpggen/results/smoke_results.json")
    assert smoke["ok"] is True, smoke["issues"]
    assert all(i["ok"] for i in smoke["items"])
    return [i["name"] for i in smoke["items"]]


def _text(target: Path, rel: str) -> str:
    return (target / rel).read_text(encoding="utf-8")


def test_the_platformer_pack_is_a_run_and_gun(game) -> None:
    target, result = game
    assert _smoke(target) == STEPS
    for rel in SCENES:
        assert (target / rel).is_file(), rel
    saved = jsonio.read(target / paths.CONFIG)
    assert saved["archetype"] == "run_and_gun" and "starter_map" not in saved
    assert {"jump", "shoot", "grenade", "aim_lock"} <= set(saved["input"])
    drawn = sorted(i.detail["role"] for i in result.issues if i.code == "ASSET-031")
    assert drawn == ["EXPLOSION", "POWERUP", "PROJECTILE"], "the pack has no bullet of its own"
    assert (target / arcade_kit.KIT_DIR / "bullet.png").is_file()
    stages = jsonio.read(target / "game/data/stages.json")["stages"]
    assert len(stages) == 3
    stage = stages[0]
    assert (stage["axis"], stage["speed"], stage["exit"]) == ("right", 0.0, "reach_end")
    assert stage["length"] == (14 * 20 - 40) * 16, "fourteen chunks; the last screen is the arena"
    assert stage["scene"] == "res://generated/scenes/stages/stage_01.tscn"
    assert "tiles" not in stage, "the tiles are painted into the scene, not listed"


def test_the_scenes_are_a_soldier_on_the_packs_ground(game) -> None:
    target, _result = game
    soldier = _text(target, "generated/scenes/run_and_gun/soldier.tscn")
    assert "archetypes/run_and_gun/soldier.gd" in soldier
    assert "sprite_frames/platformer." in soldier, "the hero of the pack"
    for part in ('name="Visual"', 'name="Body"', 'name="Gun"', 'name="Input"', 'name="Muzzle"'):
        assert part in soldier, part
    assert "max_health" not in soldier, "one hit is a death: the default is not written"
    assert "run_and_gun/grenade.tscn" in soldier and "run_and_gun/explosion.tscn" in soldier
    stage = _text(target, "generated/scenes/stages/stage_01.tscn")
    assert "archetypes/arcade/stage.gd" in stage and "archetypes/arcade/bullet_pool.gd" in stage
    assert 'name="Ground"' in stage and 'type="TileMapLayer"' in stage
    assert "generated/tilesets/" in stage, "painted with the tile set of the packs"
    assert "wall_mask = 1" in stage, "bullets stop at the ground"
    assert 'type="Parallax2D"' in stage, "the parallax pictures of the pack"
    assert "generated/scenes/run_and_gun/soldier.tscn" in stage
    mode = _text(target, "generated/scenes/combat/combat_mode.tscn")
    assert "archetypes/run_and_gun/run_and_gun_mode.gd" in mode
    hud = _text(target, "generated/scenes/ui/hud_arcade.tscn")
    assert "archetypes/run_and_gun/ui/run_and_gun_hud.gd" in hud
    assert "res://generated/scenes/stages/stage_01.tscn" in _text(target, "game/data/new_game.tres")
    strings = _text(target, "game/i18n/strings.tsv")
    assert "RNG_GRENADES\t" in strings and "ARC_GAME_OVER\t" in strings
    settings = _text(target, "project.godot")
    assert "layer_11" in settings, "the one-way platforms have their physics layer"


def test_the_project_has_the_platform_code_it_is_built_on_and_no_other_kind(game) -> None:
    target, _result = game
    archetypes = target / "addons/rpg_runtime/archetypes"
    assert sorted(p.name for p in archetypes.iterdir()) == ["arcade", "metroidvania", "run_and_gun"]
    recipes = target / "generated/builder/recipes"
    assert (recipes / "run_and_gun/soldier_recipe.gd").is_file()
    assert (recipes / "metroidvania/side_kit.gd").is_file()
    assert not (recipes / "shmup").exists() and not (recipes / "arpg").exists()
    smoke = sorted(p.name for p in (target / "generated/builder/smoke").glob("smoke_steps_*.gd"))
    assert "smoke_steps_run_and_gun.gd" in smoke and "smoke_steps_metroidvania.gd" not in smoke
    # a run of stages, not a world of rooms
    assert not (target / "game/maps/rooms").exists()
    assert not (target / "game/maps/starter_map.tscn").exists()
    assert not (target / "generated/scenes/actors/player.tscn").exists()


def test_a_second_run_changes_nothing(game, godot_exe: Path) -> None:
    target, _result = game
    kept = {rel: (target / rel).read_bytes() for rel in [*SCENES, "game/data/stages.json"]}
    again = orchestrator.run_in_memory(_config(), None, target, godot_exe)
    assert again.ok, _errors(again)
    assert [i.code for i in again.issues if i.code == orchestrator.REPEAT_CODE]
    for rel, data in kept.items():
        assert (target / rel).read_bytes() == data, rel


def test_a_forgiving_soldier_and_a_left_edge_that_is_a_wall(
    godot_exe: Path, cache: Path, tmp_path: Path
) -> None:
    target = tmp_path / "out"
    result = orchestrator.run_in_memory(
        _config(health=3, lives=5, left_edge_kills=False), None, target, godot_exe
    )
    assert result.ok, _errors(result)
    assert _smoke(target) == STEPS
    soldier = _text(target, "generated/scenes/run_and_gun/soldier.tscn")
    assert "max_health = 3" in soldier and "left_edge_kills = false" in soldier
    assert "start_lives = 5" in _text(target, "generated/scenes/combat/combat_mode.tscn")
    saved = jsonio.read(target / paths.CONFIG)
    assert (saved["starter_map"]["health"], saved["starter_map"]["lives"]) == (3, 5)
    assert saved["starter_map"]["left_edge_kills"] is False


# ---------------------------------------------------------------- weapons and enemies (T16.09)


@pytest.fixture(scope="module")
def gunner(godot_exe: Path, cache: Path, tmp_path_factory: pytest.TempPathFactory):
    target = tmp_path_factory.mktemp("m16_gunner") / "out"
    cfg = config.default_for(
        "Gunner", [config.pack_ref_from_source(GUNNER, "gunner")], archetype="run_and_gun"
    )
    result = orchestrator.run_in_memory(cfg, None, target, godot_exe)
    assert result.ok, _errors(result)
    return target, result


def test_the_gunner_pack_plays_with_its_soldier_its_enemies_and_its_weapons(gunner) -> None:
    target, result = gunner
    assert _smoke(target) == STEPS
    assert not [i for i in result.issues if i.severity.value == "error"]
    soldier = _text(target, "generated/scenes/run_and_gun/soldier.tscn")
    assert "sprite_frames/gunner.soldier.soldier_idle.tres" in soldier, "the soldier of the pack"
    assert "weapons/machine_gun.gd" in soldier, "it starts with the machine gun"
    # the pack calls no picture a bullet (its pickups only mention one): a drawn one is used
    drawn = sorted(i.detail["role"] for i in result.issues if i.code == "ASSET-031")
    assert "PROJECTILE" in drawn
    assert "arcade_kit/bullet.png" in _text(target, "generated/scenes/stages/stage_01.tscn")
    enemies = target / "generated/scenes/run_and_gun/enemies"
    assert sorted(p.name for p in enemies.glob("*.tscn")) == [
        "jumper.tscn",
        "runner.tscn",
        "sniper.tscn",
        "turret.tscn",
        "wall_cannon.tscn",
    ]
    # the three soldiers of the pack are the three that walk; its turret is both fixed guns
    walkers = {
        name: _text(target, f"generated/scenes/run_and_gun/enemies/{name}.tscn")
        for name in ("runner", "sniper", "jumper")
    }
    pictures = [
        next(w for w in ("commando", "gunner_walk", "trooper") if w in text)
        for text in walkers.values()
    ]
    assert sorted(pictures) == ["commando", "gunner_walk", "trooper"], "one picture each"
    for name, script in (("runner", "runner.gd"), ("sniper", "sniper.gd"), ("jumper", "jumper.gd")):
        assert f"run_and_gun/enemies/{script}" in walkers[name]
    for name in ("turret", "wall_cannon"):
        text = _text(target, f"generated/scenes/run_and_gun/enemies/{name}.tscn")
        assert "gunner.enemies.turret" in text or "enemies/turret.png" in text, name
    pickup = _text(target, "generated/scenes/run_and_gun/weapon_pickup.tscn")
    for weapon in ("machinegun", "spread", "laser", "flame"):
        assert f"pickups/weapon_pickup_{weapon}.png" in pickup, "the pickups of the pack, by name"


def test_the_stages_are_those_of_the_stored_plan_painted_from_its_tiles(gunner) -> None:
    from rpggen.core import stage_plan, world_plan

    target, _result = gunner
    stored = world_plan.load(target)["stages"]
    saved = jsonio.read(target / paths.CONFIG)
    assert stored == stage_plan.plan(
        {}, saved["seed"], stage_plan.facts_of(saved["resolution"], 16)
    )
    assert stage_plan.check(stored) == []
    stages = jsonio.read(target / "game/data/stages.json")["stages"]
    assert [s["scene"] for s in stages] == [s["scene"] for s in stored["list"]]
    kinds = set()
    for planned, listed in zip(stored["list"], stages, strict=True):
        assert [w["id"] for w in listed["waves"]] == [w["id"] for w in planned["waves"]]
        assert [w["at"] for w in listed["waves"]] == [w["at"] for w in planned["waves"]]
        (trap,) = [w for w in listed["waves"] if w.get("blocking")]
        assert trap["enemy"] == "turret", "a trap that stops the camera in every stage"
        for wave in listed["waves"]:
            assert (target / wave["scene"].removeprefix("res://")).is_file(), wave["scene"]
        kind = listed["boss"]["kind"]
        kinds.add(kind)
        assert listed["boss"]["scene"] == f"res://generated/scenes/run_and_gun/boss_{kind}.tscn"
        scene = _text(target, listed["scene"].removeprefix("res://"))
        for layer in ("Ground", "Platforms", "Hazards", "Decoration"):
            assert f'name="{layer}" type="TileMapLayer"' in scene, layer
        assert "generated/scenes/run_and_gun/soldier.tscn" in scene
    assert len(kinds) >= 2, "not the same boss in every stage"
    boss = _text(target, "generated/scenes/run_and_gun/boss_wall.tscn")
    assert "run_and_gun/boss.gd" in boss and "gunner.boss." in boss, "the boss of the pack"
    hud = _text(target, "generated/scenes/ui/hud_arcade.tscn")
    assert "run_and_gun/ui/run_and_gun_hud.gd" in hud
    assert "RNG_WEAPON_SPREAD\t" in _text(target, "game/i18n/strings.tsv")


def test_an_added_stage_grows_the_run(godot_exe: Path, cache: Path, tmp_path: Path) -> None:
    from rpggen.core import world_plan

    target = tmp_path / "out"
    first = orchestrator.run_in_memory(_config(stages=1, length="short"), None, target, godot_exe)
    assert first.ok, _errors(first)
    assert len(jsonio.read(target / "game/data/stages.json")["stages"]) == 1
    second = orchestrator.run_in_memory(
        _config(stages=5, length="short", added_stages=[{"name": "The Docks"}]),
        None,
        target,
        godot_exe,
    )
    assert second.ok, _errors(second)
    stored = world_plan.load(target)["stages"]
    assert [s["id"] for s in stored["list"]] == ["stage_01", "stage_02"], "the stored plan counts"
    assert stored["added"] == ["The Docks"]
    planned = jsonio.read(target / "generated/data/stages.json")["stages"]
    assert [s["title"] for s in planned] == ["", "The Docks"]
    assert (target / "generated/scenes/stages/stage_02.tscn").is_file()
    assert _smoke(target)[-1] == "run_reaches_the_credits"
